"""
Модуль для конвертации словарных .docx файлов в CSV формат.
Читает split-файлы по буквам, извлекает статьи и формирует CSV для WP All Import.
"""
import csv
import os
import re
from pathlib import Path
from docx import Document
from docx.text.run import Run


class TextProcessor:
    @staticmethod
    def is_roman_numeral(text):
        """Проверяет, является ли текст римской цифрой."""
        return bool(re.match(r'^(I|II|III|IV|V|VI|VII|VIII|IX|X)$', text.strip()))

    @staticmethod
    def normalize_text(text):
        """Нормализует текст, удаляя лишние пробелы."""
        return re.sub(r'\s+', ' ', text).strip()

    @staticmethod
    def clean_first_word(word):
        """Очищает первое слово от знаков препинания."""
        return re.sub(r'[,:]+$', '', word).strip()


class FormatProcessor:
    @staticmethod
    def get_run_formatting(run):
        """Определяет форматирование текстового фрагмента."""
        if run.bold and run.italic:
            return 'bold italic'
        elif run.bold:
            return 'bold'
        elif run.italic:
            return 'italic'
        return None

    def process_runs(self, paragraph, skip_words=0):
        """Обрабатывает форматирование текстовых фрагментов параграфа."""
        formatted_text = []
        current_format = None
        current_text = []
        words_processed = 0

        for run in paragraph.runs:
            run_text = run.text
            if not run_text.strip():
                if current_text and run_text.isspace():
                    current_text.append(' ')
                continue

            if words_processed < skip_words:
                words = run_text.split()
                if len(words) + words_processed <= skip_words:
                    words_processed += len(words)
                    continue
                else:
                    remaining_words = skip_words - words_processed
                    run_text = ' '.join(words[remaining_words:])
                    words_processed = skip_words

            run_format = self.get_run_formatting(run)

            if run_format != current_format:
                if current_text:
                    text = ''.join(current_text).strip()
                    if current_format:
                        text = f'<span class="{current_format}">{text}</span>'
                    formatted_text.append(text)
                    current_text = []
                current_format = run_format

            last_char = current_text[-1][-1] if current_text and current_text[-1] else ''
            next_char = run_text[0] if run_text else ''
            needs_space = (
                current_text
                and not last_char.endswith(' ')
                and not next_char.startswith(' ')
                and last_char != '('
                and next_char not in (')', ',', '.', ';', ':', '!', '?')
            )
            if needs_space:
                current_text.append(' ')
            current_text.append(run_text)

        if current_text:
            text = ''.join(current_text).strip()
            if current_format:
                text = f'<span class="{current_format}">{text}</span>'
            formatted_text.append(text)

        parts = [p for p in formatted_text if p.strip()]
        if not parts:
            return ''
        result = parts[0]
        for part in parts[1:]:
            last_visible = re.sub(r'<[^>]+>', '', result)
            last_char = last_visible[-1] if last_visible else ''
            first_visible = re.sub(r'<[^>]+>', '', part)
            first_char = first_visible[0] if first_visible else ''
            if last_char != '(' and first_char not in (')', ',', '.', ';', ':', '!', '?'):
                result += ' ' + part
            else:
                result += part
        return result


class DocumentProcessor:
    def __init__(self):
        self.text_processor = TextProcessor()
        self.format_processor = FormatProcessor()

    def process_paragraph(self, paragraph):
        """Обрабатывает параграф документа. Возвращает (title, content)."""
        text = self.text_processor.normalize_text(paragraph.text)
        words = text.split()
        if not words:
            return "", ""

        first_word = self.text_processor.clean_first_word(words[0].upper())
        skip_words = 1
        has_punctuation = None

        if len(words) > 1:
            second_word = words[1]
            second_word_clean = self.text_processor.clean_first_word(second_word)

            if self.text_processor.is_roman_numeral(second_word_clean):
                first_word = f"{first_word} {second_word_clean}"
                skip_words = 2

                if second_word.endswith(':'):
                    has_punctuation = ':'
                elif second_word.endswith(','):
                    has_punctuation = ','
                elif len(words) > 2 and (words[2] == ':' or words[2] == ','):
                    has_punctuation = words[2]
                    skip_words = 3
        else:
            if words[0].endswith(':'):
                has_punctuation = ':'
            elif words[0].endswith(','):
                has_punctuation = ','

        formatted_content = self.format_processor.process_runs(paragraph, skip_words)
        formatted_content = re.sub(r'\b(I|II|III|IV|V|VI|VII|VIII|IX|X)\b[:, ]?', '', formatted_content)
        formatted_content = re.sub(r'<(?!/?span)[^>]+>', '', formatted_content)

        if has_punctuation:
            if '<span' in formatted_content:
                formatted_content = re.sub(
                    r'(<span[^>]*>)(.*?)(</span>)',
                    rf'\1\2{has_punctuation}\3',
                    formatted_content,
                    count=1
                )
            else:
                formatted_content = f'{has_punctuation} {formatted_content}'

        formatted_content = re.sub(r'\s+', ' ', formatted_content).strip()
        formatted_content = re.sub(r':{2,}', ':', formatted_content)
        formatted_content = re.sub(r',{2,}', ',', formatted_content)

        return first_word, formatted_content


def convert_single_file(doc_path, output_dir, letter, doc_processor, log):
    """Конвертирует один .docx файл в CSV."""
    output_path = os.path.join(output_dir, f"{letter}.csv")
    log(f"Начало конвертации: {os.path.basename(doc_path)}", 'info')

    doc = Document(doc_path)

    rows = []
    article_id = 0

    for para in doc.paragraphs:
        text = doc_processor.text_processor.normalize_text(para.text)
        if not text:
            continue
        title, content = doc_processor.process_paragraph(para)
        if title:
            article_id += 1
            rows.append([article_id, letter, title, f"<p>{content}</p>"])

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL, quotechar='"')
        writer.writerow(['articleid', 'articlecat', 'articletitle', 'articleintrotext'])
        writer.writerows(rows)

    log(f"Буква {letter} — {article_id} записей → {os.path.basename(output_path)}", 'success')
    return {'letter': letter, 'count': article_id, 'file': output_path}


def convert_dictionary(input_dir, output_dir, log=None):
    """
    Конвертирует .docx файлы из input_dir в CSV файлы в output_dir.

    Args:
        input_dir: папка с .docx файлами (split/)
        output_dir: папка для CSV файлов (output/)
        log: callback — log(message, level), level: 'info', 'success', 'error'
    Returns:
        dict: {'files': int, 'details': [{'letter', 'count', 'file'}]}
    """
    if log is None:
        log = lambda msg, level='info': None

    os.makedirs(output_dir, exist_ok=True)

    docx_files = sorted(Path(input_dir).glob('*.docx'))
    if not docx_files:
        log("Файлы .docx не найдены в папке split", 'error')
        return None

    log(f"Найдено файлов для конвертации: {len(docx_files)}", 'info')

    doc_processor = DocumentProcessor()
    results = {'files': 0, 'details': []}

    for doc_path in docx_files:
        letter = doc_path.stem
        try:
            detail = convert_single_file(str(doc_path), output_dir, letter, doc_processor, log)
            results['details'].append(detail)
            results['files'] += 1
        except Exception as e:
            log(f"Ошибка при обработке файла {doc_path.name}: {str(e)}", 'error')

    log(f"Конвертация завершена. Создано файлов: {results['files']}", 'success')
    return results

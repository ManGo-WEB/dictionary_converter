"""
Ищет в output/*.csv следы "разорванных" слов — лишние пробелы внутри слова.

Эвристика: ищем паттерн "буква + пробел + 1-2 буквы + пробел + буква",
где справа/слева от короткого осколка стоят кириллические буквы.
Особое внимание буквам с font fallback: ѳ Ѳ Ү ү Һ һ Ӧ ӧ.
"""
import csv
import io
import os
import re
import sys
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, 'output')
REPORT = os.path.join(os.path.dirname(__file__), '_csv_report.txt')

# Кириллица + расширения для бурятского
CYR = r'[А-Яа-яЁёѲѳҮүҺһӦӧ]'
RARE = set('ѲѳҮүҺһӦӧ')

# Слово с короткой "вставкой" посередине: длинный_фрагмент пробел короткий пробел длинный
# Длина короткого фрагмента 1..3 символа — типичный сигнал разрыва.
PATTERN = re.compile(rf'({CYR}{{2,}})\s({CYR}{{1,3}})\s({CYR}{{2,}})')

# Контекст для отображения
CTX = 30


def strip_html(s):
    return re.sub(r'<[^>]+>', '', s)


def is_suspicious(left, mid, right):
    """
    Истинно подозрительное: либо короткий фрагмент содержит редкий символ,
    либо краевые символы соседних фрагментов — редкие.
    """
    if any(c in RARE for c in mid):
        return True
    if left and left[-1] in RARE:
        return True
    if right and right[0] in RARE:
        return True
    return False


def scan_file(path):
    findings = []          # все (suspicious) — для отчёта
    counter_letters = Counter()  # частота редких символов в найденном
    examples_by_pattern = defaultdict(list)  # пример → счётчик уникальных
    total_rows = 0
    rows_with_hits = 0

    with open(path, 'r', encoding='utf-8', newline='') as f:
        reader = csv.reader(f, delimiter=';', quotechar='"')
        header = next(reader, None)
        for row in reader:
            if len(row) < 4:
                continue
            total_rows += 1
            article_id, _cat, title, body = row[0], row[1], row[2], row[3]
            text = strip_html(body)
            hits = PATTERN.findall(text)
            row_marked = False
            for left, mid, right in hits:
                if not is_suspicious(left, mid, right):
                    continue
                row_marked = True
                snippet = f"{left} {mid} {right}"
                examples_by_pattern[snippet].append((article_id, title))
                for c in snippet:
                    if c in RARE:
                        counter_letters[c] += 1
                # сохраняем компактную запись
                # (для отчёта по топ-словам, не по всем строкам)
            if row_marked:
                rows_with_hits += 1

    return {
        'rows': total_rows,
        'rows_with_hits': rows_with_hits,
        'examples': examples_by_pattern,
        'rare_chars': counter_letters,
    }


def main():
    csvs = sorted(p for p in os.listdir(OUTPUT) if p.lower().endswith('.csv'))

    grand_rows = 0
    grand_hits = 0
    grand_rare = Counter()
    per_letter = []  # (letter, rows, hits, top_examples)

    with open(REPORT, 'w', encoding='utf-8') as out:
        out.write("# Анализ CSV на лишние пробелы внутри слов\n\n")
        out.write("Эвристика: 'длинный_фрагмент пробел 1-3-буквы пробел длинный_фрагмент',\n")
        out.write("где хотя бы один из фрагментов содержит редкие символы (ѳ Ѳ Ү ү Һ һ Ӧ ӧ).\n\n")

        for name in csvs:
            path = os.path.join(OUTPUT, name)
            r = scan_file(path)
            grand_rows += r['rows']
            grand_hits += r['rows_with_hits']
            grand_rare.update(r['rare_chars'])

            uniq_examples = sorted(
                r['examples'].items(),
                key=lambda kv: -len(kv[1])
            )

            per_letter.append((name, r['rows'], r['rows_with_hits'], uniq_examples))

            out.write(f"\n## {name}\n")
            out.write(f"Всего записей: {r['rows']}\n")
            out.write(f"Записей с подозрительными разрывами: {r['rows_with_hits']}\n")
            if uniq_examples:
                out.write(f"Уникальных паттернов: {len(uniq_examples)}\n")
                out.write("Топ-15 примеров (паттерн × кол-во статей):\n")
                for snippet, occurrences in uniq_examples[:15]:
                    sample_titles = ', '.join(sorted({t for _, t in occurrences})[:3])
                    out.write(f"  {len(occurrences):4d}× '{snippet}'   (напр. в: {sample_titles})\n")

        out.write("\n\n# Сводная таблица\n\n")
        out.write(f"{'Буква':<8} {'Записи':>8} {'С разрывами':>14} {'%':>7}\n")
        for name, rows, hits, _ in per_letter:
            pct = (100.0 * hits / rows) if rows else 0
            out.write(f"{name:<8} {rows:>8d} {hits:>14d} {pct:>6.2f}%\n")
        gpct = (100.0 * grand_hits / grand_rows) if grand_rows else 0
        out.write(f"{'ИТОГО':<8} {grand_rows:>8d} {grand_hits:>14d} {gpct:>6.2f}%\n")

        out.write("\n# Частота редких символов в найденных разрывах\n")
        for ch, cnt in grand_rare.most_common():
            out.write(f"  {ch} (U+{ord(ch):04X}): {cnt}\n")

    # Краткая сводка в stdout
    print(f"Отчёт: {REPORT}")
    print(f"Всего записей: {grand_rows}")
    print(f"Записей с разрывами: {grand_hits} ({(100.0*grand_hits/grand_rows):.2f}%)")
    print("Редкие символы в разрывах:")
    for ch, cnt in grand_rare.most_common():
        print(f"  {ch} (U+{ord(ch):04X}): {cnt}")
    print()
    print("По буквам:")
    for name, rows, hits, _ in per_letter:
        if hits:
            pct = 100.0 * hits / rows
            print(f"  {name:<8} {rows:>5d} записей, {hits:>4d} с разрывами ({pct:.1f}%)")


if __name__ == '__main__':
    main()

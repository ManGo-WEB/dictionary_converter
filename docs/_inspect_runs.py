"""
Анализирует сырые runs в split/*.docx.

Цели:
  1) Подтвердить, что слова типа 'ѳѳрѳѳ', 'үнѳѳхи' приходят как несколько runs
     ОДНОГО формата (bold/italic) без пробелов на стыке -> эвристика вставки
     пробела вредит.
  2) Найти контр-примеры: случаи, где между двумя run-ами одного формата
     пробела НЕТ в тексте, но он реально должен быть (т.е. убирать вставку
     нельзя огульно).

Метод:
  Для каждого параграфа смотрим пары соседних runs (i, i+1):
    - оба не пустые
    - run[i] не заканчивается пробелом, run[i+1] не начинается с пробела
    - оба имеют одинаковые bold/italic
  Это и есть точки, где converter.py:79-88 добавляет пробел.
  Сохраняем стык: run[i].text[-15:] + '|' + run[i+1].text[:15]
  Плюс отмечаем шрифт каждого run-а (font.name).
"""
import io
import os
import sys
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from docx import Document  # type: ignore

SPLIT = os.path.join(ROOT, 'split')
REPORT = os.path.join(os.path.dirname(__file__), '_runs_report.txt')


def fmt(run):
    return ('B' if run.bold else '-') + ('I' if run.italic else '-')


def join_text(left_tail, right_head):
    return f"{left_tail}|{right_head}"


PUNCT_BLOCK_RIGHT = {')', ',', '.', ';', ':', '!', '?'}
PUNCT_BLOCK_LEFT = {'('}


def converter_inserts_space(left_char, right_char):
    """Воспроизводит условие из converter.py:79-85."""
    if left_char.isspace() or right_char.isspace():
        return False
    if left_char in PUNCT_BLOCK_LEFT:
        return False
    if right_char in PUNCT_BLOCK_RIGHT:
        return False
    return True


def analyze_doc(path):
    doc = Document(path)
    joint_chars_all = Counter()        # все same_fmt_no_space стыки
    joint_chars_inserted = Counter()    # только стыки, где converter вставит пробел
    examples_inserted = []
    same_fmt_joins = 0
    diff_fmt_joins = 0
    space_joins = 0
    inserted_joins = 0

    for para in doc.paragraphs:
        runs = [r for r in para.runs if r.text != '']
        for i in range(len(runs) - 1):
            a, b = runs[i], runs[i + 1]
            ta, tb = a.text, b.text
            if not ta or not tb:
                continue
            la, fb = ta[-1], tb[0]
            if la.isspace() or fb.isspace():
                space_joins += 1
                continue
            same_fmt = (bool(a.bold) == bool(b.bold)) and (bool(a.italic) == bool(b.italic))
            if same_fmt:
                same_fmt_joins += 1
                joint_chars_all[(la, fb)] += 1
                if converter_inserts_space(la, fb):
                    inserted_joins += 1
                    joint_chars_inserted[(la, fb)] += 1
                    if len(examples_inserted) < 200:
                        fa = a.font.name or '?'
                        fbn = b.font.name or '?'
                        examples_inserted.append((ta[-20:], tb[:20], fa, fbn))
            else:
                diff_fmt_joins += 1

    return {
        'same_fmt_joins': same_fmt_joins,
        'diff_fmt_joins': diff_fmt_joins,
        'space_joins': space_joins,
        'inserted_joins': inserted_joins,
        'joint_chars_all': joint_chars_all,
        'joint_chars_inserted': joint_chars_inserted,
        'examples_inserted': examples_inserted,
    }


def main():
    targets = sorted(p for p in os.listdir(SPLIT) if p.endswith('.docx') and not p.startswith('~$'))

    grand_same = 0
    grand_diff = 0
    grand_space = 0
    grand_inserted = 0
    grand_chars_all = Counter()
    grand_chars_inserted = Counter()
    grand_examples = []

    with open(REPORT, 'w', encoding='utf-8') as out:
        out.write("# Анализ стыков run-ов в split/*.docx\n")
        out.write("Стык = пара соседних run-ов с непустым текстом.\n")
        out.write("same_fmt_no_space = стыки одного формата (bold/italic), без пробела на границе.\n")
        out.write("inserted = подмножество same_fmt_no_space, где converter РЕАЛЬНО вставит пробел\n")
        out.write("           (т.е. left != '(' и right не из {),.;:!?}).\n\n")

        for name in targets:
            path = os.path.join(SPLIT, name)
            try:
                r = analyze_doc(path)
            except Exception as e:
                out.write(f"\n## {name}\nОШИБКА: {e}\n")
                continue
            grand_same += r['same_fmt_joins']
            grand_diff += r['diff_fmt_joins']
            grand_space += r['space_joins']
            grand_inserted += r['inserted_joins']
            grand_chars_all.update(r['joint_chars_all'])
            grand_chars_inserted.update(r['joint_chars_inserted'])
            if len(grand_examples) < 80:
                grand_examples.extend(r['examples_inserted'][:5])

            out.write(f"\n## {name}\n")
            out.write(f"  same_fmt_no_space:                {r['same_fmt_joins']}\n")
            out.write(f"  -> inserted (real false spaces):  {r['inserted_joins']}\n")
            out.write(f"  diff_fmt_no_space:                {r['diff_fmt_joins']}\n")
            out.write(f"  edge_has_space:                   {r['space_joins']}\n")

            top = r['joint_chars_inserted'].most_common(15)
            if top:
                out.write("  топ-стыков среди inserted (left|right -> count):\n")
                for (l, rr), c in top:
                    out.write(f"    {l!r}|{rr!r}  count={c}\n")

            out.write("  примеры inserted (last20|first20  fontL -> fontR):\n")
            for left, right, fa, fb in r['examples_inserted'][:20]:
                out.write(f"    {left!r}|{right!r}    {fa} -> {fb}\n")

        out.write("\n\n# ИТОГО\n")
        out.write(f"  same_fmt_no_space:                                {grand_same}\n")
        out.write(f"  -> inserted (real false spaces inserted by code): {grand_inserted}\n")
        out.write(f"  diff_fmt_no_space:                                {grand_diff}\n")
        out.write(f"  edge_has_space (пробел уже есть):                 {grand_space}\n")

        out.write("\n## Топ-30 пар символов среди inserted\n")
        for (l, r), c in grand_chars_inserted.most_common(30):
            out.write(f"  {l!r}|{r!r}  count={c}\n")

    # Краткая сводка в stdout
    print(f"Отчёт: {REPORT}")
    print(f"same_fmt_no_space:           {grand_same}")
    print(f"-> inserted by converter:    {grand_inserted}")
    print(f"diff_fmt_no_space:           {grand_diff}")
    print(f"edge_has_space:              {grand_space}")
    print("Топ-15 пар символов среди inserted:")
    for (l, r), c in grand_chars_inserted.most_common(15):
        print(f"  {l!r}|{r!r}  {c}")


if __name__ == '__main__':
    main()

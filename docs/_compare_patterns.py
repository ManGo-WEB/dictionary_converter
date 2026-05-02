"""
Прямая проверка: ищем в CSV конкретные ложные паттерны разрывов,
которые были массовыми ДО фикса.
"""
import csv
import io
import os
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, 'output')

# Конкретные паттерны разрывов, которые мы хотим увидеть = 0
PATTERNS = [
    r'\bѳѳ р ѳѳ\b',
    r'\bѳѳ д ѳѳ\b',
    r'\bѳѳ рт ѳѳ\b',
    r'\bѳѳ г ѳѳ\b',
    r'\bѳѳ рг ѳѳ\b',
    r'\bѳѳ рыг ѳѳ\b',
    r'\bүн ѳѳ хи\b',
    r'\bзүбш ѳѳ хэ\b',
    r'\bүр ѳѳ һэн\b',
    r'\bхүл х ѳѳ\b',
    r'\bѳѳ си\b',
    r'\bүг ѳѳ р\b',
    r'\bмүн ѳѳ\b',
    # И аналоги для ү/һ:
    r'\bтэмдэ глэ дэг\b',
    r'\bпредполож ит\.',
    r'\bподтвержде ния\b',
    r'\bвынуж денным\b',
    r'\bхабта һануудай\b',
    r'\bасуу h а\b',
]


def strip_html(s):
    return re.sub(r'<[^>]+>', '', s)


def main():
    counters = Counter()
    examples = {p: [] for p in PATTERNS}

    for name in sorted(os.listdir(OUTPUT)):
        if not name.endswith('.csv'):
            continue
        path = os.path.join(OUTPUT, name)
        with open(path, encoding='utf-8', newline='') as f:
            r = csv.reader(f, delimiter=';', quotechar='"')
            next(r, None)
            for row in r:
                if len(row) < 4:
                    continue
                text = strip_html(row[3])
                title = row[2]
                for p in PATTERNS:
                    hits = re.findall(p, text)
                    if hits:
                        counters[p] += len(hits)
                        if len(examples[p]) < 3:
                            examples[p].append((name, title))

    print(f"{'Паттерн':<35} {'Найдено':>10}  Примеры")
    for p in PATTERNS:
        c = counters[p]
        ex = ', '.join(f"{n}/{t}" for n, t in examples[p][:3]) if c else '-'
        print(f"  {p:<33} {c:>10}  {ex}")


if __name__ == '__main__':
    main()

"""Запускает convert_dictionary напрямую и пишет лог в файл."""
import sys
import os
import io

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Принудительно переключаем stdout на utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from converter import convert_dictionary

SPLIT = os.path.join(ROOT, 'split')
OUTPUT = os.path.join(ROOT, 'output')
LOG_PATH = os.path.join(os.path.dirname(__file__), '_convert_log.txt')

with open(LOG_PATH, 'w', encoding='utf-8') as f:
    def log(msg, level='info'):
        line = f"[{level}] {msg}\n"
        f.write(line)
        f.flush()

    result = convert_dictionary(SPLIT, OUTPUT, log=log)
    f.write("---\n")
    if result:
        f.write(f"files: {result['files']}\n")
        for d in result['details']:
            f.write(f"  {d['letter']}: {d['count']} записей\n")

print(f"OK -> {LOG_PATH}")

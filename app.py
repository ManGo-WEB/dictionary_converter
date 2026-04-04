"""
Flask-сервер для обработки словарных файлов.
Точка входа приложения.
"""
import json
import os
import subprocess
import threading
from queue import Queue, Empty

from flask import Flask, request, jsonify, render_template, Response

from splitter import split_dictionary
from converter import convert_dictionary

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, 'input')
SPLIT_DIR = os.path.join(BASE_DIR, 'split')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

ALLOWED_FOLDERS = {
    'input': INPUT_DIR,
    'split': SPLIT_DIR,
    'output': OUTPUT_DIR,
}

# Глобальное состояние для SSE
log_queue = Queue()
operation_running = False
operation_lock = threading.Lock()


def ensure_dirs():
    for d in (INPUT_DIR, SPLIT_DIR, OUTPUT_DIR):
        os.makedirs(d, exist_ok=True)


def make_log_callback(queue):
    """Создаёт callback для передачи логов в очередь."""
    def log(message, level='info'):
        queue.put({'message': message, 'level': level})
    return log


# --- Маршруты ---

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'Файл не выбран'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'status': 'error', 'message': 'Файл не выбран'}), 400

    if not file.filename.lower().endswith('.docx'):
        return jsonify({'status': 'error', 'message': 'Допустимы только файлы .docx'}), 400

    filepath = os.path.join(INPUT_DIR, file.filename)
    file.save(filepath)

    return jsonify({'status': 'ok', 'filename': file.filename})


@app.route('/split', methods=['POST'])
def split():
    return _start_operation('split')


@app.route('/convert', methods=['POST'])
def convert():
    return _start_operation('convert')


@app.route('/run-all', methods=['POST'])
def run_all():
    return _start_operation('run-all')


@app.route('/open-folder', methods=['POST'])
def open_folder():
    data = request.get_json(silent=True) or {}
    folder = data.get('folder', '')

    if folder not in ALLOWED_FOLDERS:
        return jsonify({'status': 'error', 'message': 'Недопустимая папка'}), 400

    path = ALLOWED_FOLDERS[folder]
    os.makedirs(path, exist_ok=True)

    try:
        subprocess.Popen(['explorer', os.path.normpath(path)])
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/stream')
def stream():
    def generate():
        while True:
            try:
                item = log_queue.get(timeout=30)
            except Empty:
                # Keepalive
                yield f"data: {json.dumps({'keepalive': True})}\n\n"
                continue

            if item.get('done'):
                yield f"data: {json.dumps(item)}\n\n"
                break

            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


# --- Логика операций ---

def _start_operation(op_type):
    global operation_running

    with operation_lock:
        if operation_running:
            return jsonify({'status': 'error', 'message': 'Операция уже выполняется'}), 409
        operation_running = True

    # Очищаем очередь от старых сообщений
    while not log_queue.empty():
        try:
            log_queue.get_nowait()
        except Empty:
            break

    thread = threading.Thread(target=_run_operation, args=(op_type,), daemon=True)
    thread.start()

    return jsonify({'status': 'started'})


def _run_operation(op_type):
    global operation_running
    log = make_log_callback(log_queue)

    try:
        if op_type == 'split':
            _do_split(log)
        elif op_type == 'convert':
            _do_convert(log)
        elif op_type == 'run-all':
            result = _do_split(log)
            if result is not None:
                _do_convert(log)
    except Exception as e:
        log(f"Критическая ошибка: {str(e)}", 'error')
    finally:
        log_queue.put({'done': True})
        with operation_lock:
            operation_running = False


def _do_split(log):
    docx_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith('.docx')]

    if not docx_files:
        log("Файлы .docx не найдены в папке input", 'error')
        return None

    input_file = os.path.join(INPUT_DIR, docx_files[0])
    if len(docx_files) > 1:
        log(f"Найдено несколько файлов, используется: {docx_files[0]}", 'info')

    return split_dictionary(input_file, SPLIT_DIR, log=log)


def _do_convert(log):
    return convert_dictionary(SPLIT_DIR, OUTPUT_DIR, log=log)


if __name__ == '__main__':
    ensure_dirs()
    app.run(debug=True, host='127.0.0.1', port=5000, threaded=True)

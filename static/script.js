document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('file-input');
    const uploadLabel = document.getElementById('upload-label');
    const btnUpload = document.getElementById('btn-upload');
    const btnSplit = document.getElementById('btn-split');
    const btnConvert = document.getElementById('btn-convert');
    const btnRunAll = document.getElementById('btn-run-all');
    const logArea = document.getElementById('log-area');
    const folderButtons = document.querySelectorAll('.btn-folder');

    const actionButtons = [btnSplit, btnConvert, btnRunAll];
    let operationRunning = false;

    // --- Загрузка файла ---

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            uploadLabel.textContent = fileInput.files[0].name;
            uploadLabel.classList.add('has-file');
            btnUpload.disabled = false;
        } else {
            uploadLabel.textContent = 'Выберите .docx файл или перетащите сюда';
            uploadLabel.classList.remove('has-file');
            btnUpload.disabled = true;
        }
    });

    btnUpload.addEventListener('click', async () => {
        if (!fileInput.files.length) return;

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        btnUpload.disabled = true;
        btnUpload.textContent = 'Загрузка...';

        try {
            const res = await fetch('/upload', { method: 'POST', body: formData });
            const data = await res.json();

            if (data.status === 'ok') {
                addLog(`Файл загружен: ${data.filename}`, 'success');
            } else {
                addLog(`Ошибка загрузки: ${data.message}`, 'error');
            }
        } catch (e) {
            addLog(`Ошибка сети: ${e.message}`, 'error');
        } finally {
            btnUpload.textContent = 'Загрузить';
            btnUpload.disabled = false;
        }
    });

    // --- Кнопки управления ---

    btnSplit.addEventListener('click', () => startOperation('/split'));
    btnConvert.addEventListener('click', () => startOperation('/convert'));
    btnRunAll.addEventListener('click', () => startOperation('/run-all'));

    async function startOperation(url) {
        if (operationRunning) return;

        try {
            const res = await fetch(url, { method: 'POST' });
            const data = await res.json();

            if (data.status === 'started') {
                setRunning(true);
                listenSSE();
            } else {
                addLog(`Ошибка: ${data.message}`, 'error');
            }
        } catch (e) {
            addLog(`Ошибка сети: ${e.message}`, 'error');
        }
    }

    // --- SSE ---

    function listenSSE() {
        const source = new EventSource('/stream');

        source.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.done) {
                source.close();
                setRunning(false);
                return;
            }

            if (data.keepalive) return;

            addLog(data.message, data.level);
        };

        source.onerror = () => {
            source.close();
            setRunning(false);
            addLog('Соединение с сервером потеряно', 'error');
        };
    }

    // --- Папки ---

    folderButtons.forEach(btn => {
        btn.addEventListener('click', async () => {
            const folder = btn.dataset.folder;
            try {
                await fetch('/open-folder', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ folder })
                });
            } catch (e) {
                addLog(`Не удалось открыть папку: ${e.message}`, 'error');
            }
        });
    });

    // --- Утилиты ---

    function addLog(message, level = 'info') {
        const line = document.createElement('div');
        line.className = `log-line log-${level}`;
        line.textContent = message;
        logArea.appendChild(line);
        logArea.scrollTop = logArea.scrollHeight;
    }

    function setRunning(running) {
        operationRunning = running;
        actionButtons.forEach(btn => btn.disabled = running);
    }
});

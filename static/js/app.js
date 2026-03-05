/* ── Panel toggle ─────────────────────────────────────────────────────────── */
function togglePanel(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.toggle('hidden');
}

/* ── Delete confirmation ──────────────────────────────────────────────────── */
function confirmDelete(name) {
  return window.confirm('Delete "' + name + '"?\nThis cannot be undone.');
}

/* ── Rename modal ─────────────────────────────────────────────────────────── */
function openRename(rel, currentName) {
  document.getElementById('rename-rel').value = rel;
  const input = document.getElementById('rename-input');
  input.value = currentName;
  document.getElementById('rename-modal').classList.remove('hidden');
  input.focus();
  input.select();
}

function closeModal() {
  document.getElementById('rename-modal').classList.add('hidden');
}

// Close modal on backdrop click
document.addEventListener('DOMContentLoaded', function () {
  const backdrop = document.getElementById('rename-modal');
  if (backdrop) {
    backdrop.addEventListener('click', function (e) {
      if (e.target === backdrop) closeModal();
    });
  }

  // ── Drag-and-drop upload ─────────────────────────────────────────────────
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const fileList = document.getElementById('file-list');

  if (dropZone && fileInput) {
    dropZone.addEventListener('click', function (e) {
      if (e.target !== fileInput && !e.target.closest('label')) {
        fileInput.click();
      }
    });

    fileInput.addEventListener('change', function () {
      updateFileList(fileInput.files);
    });

    dropZone.addEventListener('dragover', function (e) {
      e.preventDefault();
      dropZone.classList.add('drag-over');
    });
    dropZone.addEventListener('dragleave', function () {
      dropZone.classList.remove('drag-over');
    });
    dropZone.addEventListener('drop', function (e) {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
      const dt = e.dataTransfer;
      if (dt && dt.files.length) {
        fileInput.files = dt.files;
        updateFileList(dt.files);
      }
    });
  }

  function updateFileList(files) {
    if (!fileList) return;
    fileList.innerHTML = '';
    Array.from(files).forEach(function (f) {
      const div = document.createElement('div');
      div.className = 'fl-item';
      div.textContent = f.name + ' (' + humanSize(f.size) + ')';
      fileList.appendChild(div);
    });
  }

  function humanSize(bytes) {
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++; }
    return bytes.toFixed(1) + ' ' + units[i];
  }

  // ── Pretty timestamps ────────────────────────────────────────────────────
  document.querySelectorAll('.timestamp').forEach(function (el) {
    const ts = parseFloat(el.dataset.ts);
    if (!isNaN(ts)) {
      el.textContent = new Date(ts * 1000).toLocaleString();
    }
  });
});

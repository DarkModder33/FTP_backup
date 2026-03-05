"""FTP Backup — Flask web application."""

import os
import shutil
from dataclasses import dataclass
from datetime import timedelta
from functools import wraps
from pathlib import Path
from typing import Optional

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

import config as cfg

app = Flask(__name__)
app.secret_key = cfg.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = cfg.MAX_CONTENT_LENGTH
app.permanent_session_lifetime = timedelta(seconds=cfg.SESSION_LIFETIME)

UPLOAD_ROOT = Path(cfg.UPLOAD_FOLDER)
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class Entry:
    name: str
    rel: str
    is_dir: bool
    size: Optional[int]
    mtime: float


# ── Jinja filter ───────────────────────────────────────────────────────────────

@app.template_filter("human_size")
def human_size(size: int) -> str:
    if size < 1024:
        return f"{int(size)} B"
    for unit in ["KB", "MB", "GB", "TB"]:
        size /= 1024
        if size < 1024:
            return f"{size:.1f} {unit}"
    return f"{size:.1f} PB"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe_path(rel: str) -> Path:
    """Resolve *rel* under UPLOAD_ROOT; abort 403 on path traversal."""
    target = (UPLOAD_ROOT / rel).resolve()
    upload_root = UPLOAD_ROOT.resolve()
    if target != upload_root and upload_root not in target.parents:
        abort(403)
    return target


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            if not (cfg.ALLOW_PUBLIC_READ and request.method == "GET"):
                return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ── Auth ───────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == cfg.ADMIN_USERNAME and password == cfg.ADMIN_PASSWORD:
            session.permanent = True
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("browse"))
        flash("Invalid credentials.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── File browser ───────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    return redirect(url_for("browse"))


@app.route("/files/", defaults={"rel_path": ""})
@app.route("/files/<path:rel_path>")
@login_required
def browse(rel_path=""):
    target = _safe_path(rel_path)
    if not target.exists():
        abort(404)
    if target.is_file():
        return redirect(url_for("download", rel_path=rel_path))

    # Build sorted directory listing (dirs first, then files)
    entries = []
    children = [(child, child.is_dir()) for child in target.iterdir()]
    for child, is_dir in sorted(children, key=lambda t: (not t[1], t[0].name.lower())):
        child_rel = child.relative_to(UPLOAD_ROOT).as_posix()
        stat = child.stat()
        entries.append(Entry(
            name=child.name,
            rel=child_rel,
            is_dir=is_dir,
            size=stat.st_size if not is_dir else None,
            mtime=stat.st_mtime,
        ))

    # Build breadcrumb trail
    crumbs = []
    if rel_path:
        parts = Path(rel_path).parts
        for i, part in enumerate(parts):
            crumbs.append((part, "/".join(parts[: i + 1])))

    # Parent directory link (None at root)
    if rel_path:
        parent = str(Path(rel_path).parent)
        if parent == ".":
            parent = ""
    else:
        parent = None

    return render_template(
        "browse.html",
        entries=entries,
        rel_path=rel_path,
        crumbs=crumbs,
        parent=parent,
    )


# ── Upload ─────────────────────────────────────────────────────────────────────

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    dest = request.form.get("dest", "")
    dest_path = _safe_path(dest)
    if not dest_path.is_dir():
        abort(400)

    files = request.files.getlist("files")
    if not files or not any(f.filename for f in files):
        flash("No files selected.", "warning")
        return redirect(url_for("browse", rel_path=dest))

    for f in files:
        if f.filename:
            filename = secure_filename(f.filename)
            f.save(dest_path / filename)

    flash("Files uploaded successfully.", "success")
    return redirect(url_for("browse", rel_path=dest))


# ── Mkdir ──────────────────────────────────────────────────────────────────────

@app.route("/mkdir", methods=["POST"])
@login_required
def mkdir():
    parent = request.form.get("parent", "")
    name = request.form.get("name", "").strip()
    if not name:
        flash("Folder name cannot be empty.", "danger")
        return redirect(url_for("browse", rel_path=parent))

    parent_path = _safe_path(parent)
    new_dir = parent_path / secure_filename(name)
    if new_dir.exists():
        flash(f'Folder "{name}" already exists.', "warning")
        return redirect(url_for("browse", rel_path=parent))
    new_dir.mkdir(parents=False)

    flash(f'Folder "{name}" created.', "success")
    return redirect(url_for("browse", rel_path=parent))


# ── Delete ─────────────────────────────────────────────────────────────────────

@app.route("/delete", methods=["POST"])
@login_required
def delete():
    rel = request.form.get("rel", "")
    target = _safe_path(rel)
    if not target.exists():
        abort(404)

    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()

    flash("Deleted successfully.", "success")
    parent = str(Path(rel).parent)
    if parent == ".":
        parent = ""
    return redirect(url_for("browse", rel_path=parent))


# ── Rename ─────────────────────────────────────────────────────────────────────

@app.route("/rename", methods=["POST"])
@login_required
def rename():
    rel = request.form.get("rel", "")
    new_name = request.form.get("new_name", "").strip()

    parent = str(Path(rel).parent)
    if parent == ".":
        parent = ""

    if not new_name:
        flash("Name cannot be empty.", "danger")
        return redirect(url_for("browse", rel_path=parent))

    target = _safe_path(rel)
    if not target.exists():
        abort(404)

    new_target = target.parent / secure_filename(new_name)
    target.rename(new_target)

    flash("Renamed successfully.", "success")
    return redirect(url_for("browse", rel_path=parent))


# ── Download ───────────────────────────────────────────────────────────────────

@app.route("/download/<path:rel_path>")
@login_required
def download(rel_path):
    target = _safe_path(rel_path)
    if not target.is_file():
        abort(404)
    return send_file(target, as_attachment=True)


# ── JSON API ───────────────────────────────────────────────────────────────────

@app.route("/api/list", defaults={"rel_path": ""})
@app.route("/api/list/<path:rel_path>")
@login_required
def api_list(rel_path=""):
    target = _safe_path(rel_path)
    if not target.is_dir():
        abort(404)

    entries = []
    for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
        stat = child.stat()
        entries.append({
            "name": child.name,
            "rel": child.relative_to(UPLOAD_ROOT).as_posix(),
            "is_dir": child.is_dir(),
            "size": stat.st_size if child.is_file() else None,
            "mtime": stat.st_mtime,
        })
    return jsonify(entries)


# ── Health check ───────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=debug)
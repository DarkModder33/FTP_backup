"""
FTP Backup — self-hosted online file-backup server.

Provides:
  • Web UI  : directory browser, upload, download, rename, delete, mkdir
  • REST-ish: download / delete via direct URL for scripted access
  • Auth    : session-based login protecting all routes
"""

import os
import shutil
import mimetypes
from datetime import timedelta
from functools import wraps
from pathlib import Path, PurePosixPath

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

import config

# ── App setup ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(seconds=config.SESSION_LIFETIME)

UPLOAD_ROOT = Path(config.UPLOAD_FOLDER).resolve()
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe_path(rel: str) -> Path:
    """Resolve *rel* relative to UPLOAD_ROOT and raise 404 on path traversal."""
    # Normalise: strip leading slashes, collapse dots
    clean = PurePosixPath(rel.lstrip("/"))
    target = (UPLOAD_ROOT / clean).resolve()
    # Ensure resolved path is still inside UPLOAD_ROOT
    if not str(target).startswith(str(UPLOAD_ROOT)):
        abort(403)
    return target


def _rel(path: Path) -> str:
    """Return the UPLOAD_ROOT-relative string for *path*."""
    return str(path.relative_to(UPLOAD_ROOT))


def _entry(path: Path) -> dict:
    stat = path.stat()
    return {
        "name": path.name,
        "rel": _rel(path),
        "is_dir": path.is_dir(),
        "size": stat.st_size if path.is_file() else None,
        "mtime": stat.st_mtime,
    }


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            if config.ALLOW_PUBLIC_READ and request.method == "GET":
                return f(*args, **kwargs)
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated


def _human_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} PB"


app.jinja_env.filters["human_size"] = _human_size


# ── Auth routes ────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD:
            session.permanent = True
            session["logged_in"] = True
            session["username"] = username
            next_url = request.args.get("next") or url_for("browse")
            # Guard against open-redirect: only allow relative paths
            if not next_url.startswith("/"):
                next_url = url_for("browse")
            return redirect(next_url)
        flash("Invalid username or password.", "danger")
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
        return _serve_file(target)

    entries = sorted(
        [_entry(p) for p in target.iterdir()],
        key=lambda e: (not e["is_dir"], e["name"].lower()),
    )

    # Breadcrumb: list of (label, rel_path) tuples
    parts = Path(rel_path).parts if rel_path else []
    crumbs = []
    for i, part in enumerate(parts):
        crumbs.append((part, str(Path(*parts[: i + 1]))))

    parent = str(Path(rel_path).parent) if rel_path else None
    if parent == ".":
        parent = ""

    return render_template(
        "browse.html",
        entries=entries,
        rel_path=rel_path,
        crumbs=crumbs,
        parent=parent,
    )


# ── Download ───────────────────────────────────────────────────────────────────

def _serve_file(target: Path):
    mime, _ = mimetypes.guess_type(str(target))
    as_attachment = not (mime and mime.startswith(("text/", "image/", "application/pdf")))
    return send_file(target, mimetype=mime or "application/octet-stream", as_attachment=as_attachment)


@app.route("/download/<path:rel_path>")
@login_required
def download(rel_path):
    target = _safe_path(rel_path)
    if not target.is_file():
        abort(404)
    return send_file(target, as_attachment=True)


# ── Upload ─────────────────────────────────────────────────────────────────────

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    dest_rel = request.form.get("dest", "")
    dest = _safe_path(dest_rel)
    if not dest.is_dir():
        abort(400)

    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        flash("No files selected.", "warning")
        return redirect(url_for("browse", rel_path=dest_rel))

    saved = 0
    for f in files:
        if f.filename:
            name = secure_filename(f.filename)
            f.save(dest / name)
            saved += 1

    flash(f"{saved} file(s) uploaded successfully.", "success")
    return redirect(url_for("browse", rel_path=dest_rel))


# ── Mkdir ──────────────────────────────────────────────────────────────────────

@app.route("/mkdir", methods=["POST"])
@login_required
def mkdir():
    parent_rel = request.form.get("parent", "")
    dirname = request.form.get("name", "").strip()
    if not dirname:
        flash("Directory name cannot be empty.", "warning")
        return redirect(url_for("browse", rel_path=parent_rel))

    safe_name = secure_filename(dirname)
    if not safe_name:
        flash("Invalid directory name.", "danger")
        return redirect(url_for("browse", rel_path=parent_rel))

    new_dir = _safe_path(parent_rel) / safe_name
    new_dir.mkdir(exist_ok=True)
    flash(f"Directory '{safe_name}' created.", "success")
    return redirect(url_for("browse", rel_path=parent_rel))


# ── Rename ─────────────────────────────────────────────────────────────────────

@app.route("/rename", methods=["POST"])
@login_required
def rename():
    rel = request.form.get("rel", "")
    new_name = request.form.get("new_name", "").strip()
    target = _safe_path(rel)
    if not target.exists():
        abort(404)
    safe = secure_filename(new_name)
    if not safe:
        flash("Invalid name.", "danger")
        return redirect(url_for("browse", rel_path=str(Path(rel).parent)))
    dest = target.parent / safe
    target.rename(dest)
    flash(f"Renamed to '{safe}'.", "success")
    parent_rel = str(Path(rel).parent)
    if parent_rel == ".":
        parent_rel = ""
    return redirect(url_for("browse", rel_path=parent_rel))


# ── Delete ─────────────────────────────────────────────────────────────────────

@app.route("/delete", methods=["POST"])
@login_required
def delete():
    rel = request.form.get("rel", "")
    target = _safe_path(rel)
    # Refuse to delete the root
    if target == UPLOAD_ROOT:
        abort(403)
    if not target.exists():
        abort(404)
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    flash(f"'{target.name}' deleted.", "success")
    parent_rel = str(Path(rel).parent)
    if parent_rel == ".":
        parent_rel = ""
    return redirect(url_for("browse", rel_path=parent_rel))


# ── JSON API (scripted access) ─────────────────────────────────────────────────

@app.route("/api/list", defaults={"rel_path": ""})
@app.route("/api/list/<path:rel_path>")
@login_required
def api_list(rel_path=""):
    target = _safe_path(rel_path)
    if not target.is_dir():
        abort(404)
    entries = [_entry(p) for p in sorted(target.iterdir(), key=lambda p: p.name)]
    return jsonify(entries)


# ── Health-check (used by Docker / load-balancer) ──────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host=host, port=port, debug=debug)

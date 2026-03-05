"""
Tests for app.py — file backup web application.

Run with:  pytest tests/test_app.py -v
"""

import io
import os

import pytest

# Set env vars before importing app/config so config reads them
os.environ.setdefault("ADMIN_USERNAME", "testuser")
os.environ.setdefault("ADMIN_PASSWORD", "testpass")
os.environ.setdefault("SECRET_KEY", "testsecretkey1234567890")


@pytest.fixture()
def tmp_upload(tmp_path):
    """Temporary upload root."""
    return tmp_path


@pytest.fixture()
def client(tmp_upload):
    """Flask test client with an isolated upload folder."""
    import config as cfg
    cfg.UPLOAD_FOLDER = str(tmp_upload)
    cfg.ADMIN_USERNAME = "testuser"
    cfg.ADMIN_PASSWORD = "testpass"
    cfg.SECRET_KEY = "testsecretkey1234567890"
    cfg.ALLOW_PUBLIC_READ = False

    # Re-import app so UPLOAD_ROOT is recalculated with the new folder
    import importlib
    import app as app_module
    importlib.reload(app_module)

    app_module.app.config["TESTING"] = True
    app_module.app.config["WTF_CSRF_ENABLED"] = False

    with app_module.app.test_client() as c:
        yield c


def _login(client):
    return client.post(
        "/login",
        data={"username": "testuser", "password": "testpass"},
        follow_redirects=True,
    )


# ── Auth ───────────────────────────────────────────────────────────────────────

class TestAuth:
    def test_unauthenticated_redirects_to_login(self, client):
        r = client.get("/files/", follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_login_bad_credentials(self, client):
        r = client.post(
            "/login",
            data={"username": "wrong", "password": "bad"},
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert b"Invalid" in r.data

    def test_login_success(self, client):
        r = _login(client)
        assert r.status_code == 200
        # Should land on file browser
        assert b"Home" in r.data

    def test_logout(self, client):
        _login(client)
        r = client.get("/logout", follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]


# ── Browse ─────────────────────────────────────────────────────────────────────

class TestBrowse:
    def test_browse_root_empty(self, client):
        _login(client)
        r = client.get("/files/")
        assert r.status_code == 200
        assert b"empty" in r.data.lower()

    def test_browse_lists_entries(self, client, tmp_upload):
        _login(client)
        (tmp_upload / "hello.txt").write_text("hi")
        (tmp_upload / "mydir").mkdir()
        r = client.get("/files/")
        assert b"hello.txt" in r.data
        assert b"mydir" in r.data

    def test_browse_nonexistent_returns_404(self, client):
        _login(client)
        r = client.get("/files/doesnotexist")
        assert r.status_code == 404

    def test_path_traversal_blocked(self, client):
        _login(client)
        r = client.get("/files/../../etc/passwd")
        assert r.status_code in (403, 404)


# ── Upload ─────────────────────────────────────────────────────────────────────

class TestUpload:
    def test_upload_file(self, client, tmp_upload):
        _login(client)
        data = {
            "dest": "",
            "files": (io.BytesIO(b"hello world"), "test.txt"),
        }
        r = client.post(
            "/upload",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert (tmp_upload / "test.txt").read_bytes() == b"hello world"

    def test_upload_no_file(self, client):
        _login(client)
        r = client.post(
            "/upload",
            data={"dest": ""},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert b"No files" in r.data


# ── Mkdir ──────────────────────────────────────────────────────────────────────

class TestMkdir:
    def test_mkdir_creates_directory(self, client, tmp_upload):
        _login(client)
        r = client.post(
            "/mkdir",
            data={"parent": "", "name": "myfolder"},
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert (tmp_upload / "myfolder").is_dir()

    def test_mkdir_empty_name(self, client):
        _login(client)
        r = client.post(
            "/mkdir",
            data={"parent": "", "name": ""},
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert b"cannot be empty" in r.data


# ── Delete ─────────────────────────────────────────────────────────────────────

class TestDelete:
    def test_delete_file(self, client, tmp_upload):
        _login(client)
        f = tmp_upload / "todelete.txt"
        f.write_text("bye")
        r = client.post(
            "/delete",
            data={"rel": "todelete.txt"},
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert not f.exists()

    def test_delete_nonexistent_returns_404(self, client):
        _login(client)
        r = client.post("/delete", data={"rel": "ghost.txt"})
        assert r.status_code == 404


# ── Rename ─────────────────────────────────────────────────────────────────────

class TestRename:
    def test_rename_file(self, client, tmp_upload):
        _login(client)
        (tmp_upload / "old.txt").write_text("data")
        r = client.post(
            "/rename",
            data={"rel": "old.txt", "new_name": "new.txt"},
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert (tmp_upload / "new.txt").exists()
        assert not (tmp_upload / "old.txt").exists()


# ── Download ───────────────────────────────────────────────────────────────────

class TestDownload:
    def test_download_file(self, client, tmp_upload):
        _login(client)
        (tmp_upload / "grab.bin").write_bytes(b"\x00\x01\x02")
        r = client.get("/download/grab.bin")
        assert r.status_code == 200
        assert r.data == b"\x00\x01\x02"

    def test_download_nonexistent(self, client):
        _login(client)
        r = client.get("/download/nope.txt")
        assert r.status_code == 404


# ── API ────────────────────────────────────────────────────────────────────────

class TestAPI:
    def test_api_list_root(self, client, tmp_upload):
        _login(client)
        (tmp_upload / "a.txt").write_text("a")
        r = client.get("/api/list")
        assert r.status_code == 200
        data = r.get_json()
        names = [e["name"] for e in data]
        assert "a.txt" in names

    def test_api_list_requires_auth(self, client):
        r = client.get("/api/list")
        assert r.status_code == 302


# ── Health ─────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.get_json() == {"status": "ok"}

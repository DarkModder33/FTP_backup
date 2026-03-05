"""
Configuration for the FTP Backup web application.
All sensitive values should be set via environment variables (see .env.example).
"""

import os
import secrets

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(BASE_DIR, "uploads"))

# Maximum allowed upload size (default 10 GB)
MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_BYTES", 10 * 1024 * 1024 * 1024))

# ── Security ───────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# Login credentials (set in env; these defaults are intentionally weak —
# ALWAYS override them in production via environment variables)
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")

# Session cookie lifetime in seconds (default 8 hours)
SESSION_LIFETIME = int(os.environ.get("SESSION_LIFETIME", 8 * 3600))

# ── Feature flags ──────────────────────────────────────────────────────────────
# Allow anonymous (unauthenticated) read-only access to files
ALLOW_PUBLIC_READ = os.environ.get("ALLOW_PUBLIC_READ", "false").lower() == "true"

# FTP Backup — Self-Hosted Online File Repository

A lightweight, self-hosted web application for backing up personal files from any device. Access your files anywhere through a modern browser UI (HTTP/HTTPS) or push them from any machine using the bundled `rsync` helper script over SSH.

---

## Features

| Feature | Details |
|---|---|
| **Web UI** | Directory browser, upload (drag & drop), download, rename, delete, create folders |
| **Drag & Drop upload** | Select multiple files at once |
| **REST-style API** | `GET /api/list/<path>` — JSON directory listing for scripted access |
| **Session auth** | Username + password login protecting all routes |
| **Docker** | Single `docker compose up` deploys the app + Nginx reverse-proxy |
| **HTTPS** | Let's Encrypt / Certbot integration out of the box |
| **rsync helper** | `scripts/sync.sh` pushes local folders to the server over SSH |
| **Health-check** | `GET /health` — used by Docker and load-balancers |

---

## Quick Start (local dev)

```bash
# 1. Clone & enter the repo
git clone https://github.com/DarkModder33/FTP_backup.git
cd FTP_backup

# 2. Create a virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Copy the example env file and set your credentials
cp .env.example .env
#   → edit .env: set SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD

# 4. Run
python app.py
```

Open <http://localhost:5000> and log in with the credentials you set.

---

## Production Deployment (tradehax.net)

### Prerequisites

- A Linux server (Ubuntu 22.04+ recommended) with Docker + Docker Compose installed
- DNS A record for `tradehax.net` (and optionally `www.tradehax.net`) pointing to the server IP
- Ports 80 and 443 open in your firewall

### Step 1 — Copy files to the server

```bash
rsync -avz ./ user@tradehax.net:/opt/ftpbackup/
```

### Step 2 — Configure environment

```bash
cd /opt/ftpbackup
cp .env.example .env
nano .env   # set SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD
```

### Step 3 — Issue a TLS certificate (first time only)

```bash
# Temporarily bring up Nginx on port 80 for the ACME challenge
docker compose up -d nginx

docker compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d tradehax.net -d www.tradehax.net \
  --email your@email.com --agree-tos --non-interactive
```

### Step 4 — Start everything

```bash
docker compose up -d
```

The site is now live at <https://tradehax.net>.

### Certificate renewal

Certbot auto-renews certificates every 12 hours. Nginx will pick up new certificates on the next reload. You can trigger a manual reload with:

```bash
docker compose exec nginx nginx -s reload
```

---

## Pushing Files from Your Devices (rsync over SSH)

The `scripts/sync.sh` helper wraps `rsync` to push a local folder to the server.

```bash
# Make the script executable (once)
chmod +x scripts/sync.sh

# Push your Documents folder into a "documents" directory on the server
./scripts/sync.sh ~/Documents documents

# Dry-run first to preview what will be transferred
./scripts/sync.sh --dry-run ~/Photos photos

# Override server settings inline
BACKUP_HOST=tradehax.net BACKUP_USER=myuser ./scripts/sync.sh ~/Music music
```

**Default environment variables:**

| Variable | Default | Description |
|---|---|---|
| `BACKUP_HOST` | `tradehax.net` | Server hostname or IP |
| `BACKUP_USER` | `$USER` (current) | SSH username |
| `BACKUP_PORT` | `22` | SSH port |
| `BACKUP_DEST` | `/data/uploads` | Remote base directory |

> **Tip:** Add an SSH key pair (`ssh-keygen`) and copy your public key to the server (`ssh-copy-id user@tradehax.net`) so the sync script runs without a password prompt.

---

## SSH Access

Files are stored under `/data/uploads` on the server (mapped to the `uploads` Docker volume). To browse or manage files over SSH:

```bash
ssh user@tradehax.net
ls /data/uploads
```

Or mount the volume directly from the host:

```bash
# Find the volume mount point
docker volume inspect ftpbackup_uploads
```

---

## Environment Variables

See `.env.example` for all available options.

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | random | Flask session secret — **must be set in production** |
| `ADMIN_USERNAME` | `admin` | Login username |
| `ADMIN_PASSWORD` | `changeme` | Login password — **must be changed** |
| `UPLOAD_FOLDER` | `./uploads` | Path where files are stored |
| `MAX_UPLOAD_BYTES` | 10 GB | Maximum upload size |
| `SESSION_LIFETIME` | 28800 s | Session cookie lifetime |
| `ALLOW_PUBLIC_READ` | `false` | Allow unauthenticated read-only access |
| `FLASK_DEBUG` | `false` | **Never enable in production** |

---

## Project Structure

```
FTP_backup/
├── app.py                  # Flask application
├── config.py               # Configuration (reads from env vars)
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container image
├── docker-compose.yml      # Multi-service stack (app + nginx + certbot)
├── .env.example            # Environment variable template
├── nginx/
│   ├── nginx.conf          # Main Nginx config
│   └── conf.d/
│       └── tradehax.conf   # Virtual host for tradehax.net (HTTP→HTTPS + proxy)
├── scripts/
│   └── sync.sh             # rsync helper for client-side backups
├── static/
│   ├── css/app.css         # Stylesheet
│   ├── js/app.js           # Client-side JavaScript
│   └── favicon.svg
├── templates/
│   ├── base.html           # Base layout
│   ├── login.html          # Login page
│   └── browse.html         # File browser
└── uploads/                # Local dev storage (git-ignored)
```

---

## Security Notes

- Always set a strong, unique `SECRET_KEY` and `ADMIN_PASSWORD` in your `.env` file.
- The app runs as a non-root user inside Docker.
- TLS is required in production — the Nginx config redirects all HTTP traffic to HTTPS.
- Path traversal is prevented: all file operations are validated to stay within `UPLOAD_FOLDER`.
- Files are saved with `werkzeug.utils.secure_filename` to sanitise uploaded filenames.

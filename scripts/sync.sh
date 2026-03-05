#!/usr/bin/env bash
# sync.sh — push a local directory to the FTP Backup server via rsync over SSH.
#
# Usage:
#   ./scripts/sync.sh [options] <local_path> <remote_path>
#
# Examples:
#   ./scripts/sync.sh ~/Documents /documents
#   ./scripts/sync.sh --dry-run ~/Photos /photos
#
# Environment variables (or edit the defaults below):
#   BACKUP_HOST   — server hostname or IP  (default: tradehax.net)
#   BACKUP_USER   — SSH user               (default: your $USER)
#   BACKUP_PORT   — SSH port               (default: 22)
#   BACKUP_DEST   — remote base upload dir (default: /data/uploads)
#
set -euo pipefail

BACKUP_HOST="${BACKUP_HOST:-tradehax.net}"
BACKUP_USER="${BACKUP_USER:-$USER}"
BACKUP_PORT="${BACKUP_PORT:-22}"
BACKUP_DEST="${BACKUP_DEST:-/data/uploads}"

DRY_RUN=0
EXTRA_ARGS=()

usage() {
  echo "Usage: $0 [--dry-run] <local_path> [<remote_subpath>]"
  echo ""
  echo "Options:"
  echo "  --dry-run   Show what would be transferred without making changes"
  echo ""
  echo "Environment:"
  echo "  BACKUP_HOST   Server hostname  (default: tradehax.net)"
  echo "  BACKUP_USER   SSH username     (default: $USER)"
  echo "  BACKUP_PORT   SSH port         (default: 22)"
  echo "  BACKUP_DEST   Remote base dir  (default: /data/uploads)"
  exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --help|-h) usage ;;
    *)         EXTRA_ARGS+=("$1"); shift ;;
  esac
done

if [[ ${#EXTRA_ARGS[@]} -lt 1 ]]; then
  echo "Error: <local_path> is required." >&2
  usage
fi

LOCAL_PATH="${EXTRA_ARGS[0]}"
REMOTE_SUB="${EXTRA_ARGS[1]:-}"

REMOTE_PATH="${BACKUP_DEST}/${REMOTE_SUB#/}"

RSYNC_OPTS=(
  -avz
  --progress
  --stats
  -e "ssh -p ${BACKUP_PORT}"
)

if [[ $DRY_RUN -eq 1 ]]; then
  RSYNC_OPTS+=(--dry-run)
  echo "[dry-run] No files will be transferred."
fi

echo "Syncing  : ${LOCAL_PATH}"
echo "     →   ${BACKUP_USER}@${BACKUP_HOST}:${REMOTE_PATH}"
echo ""

rsync "${RSYNC_OPTS[@]}" "${LOCAL_PATH}/" "${BACKUP_USER}@${BACKUP_HOST}:${REMOTE_PATH}/"
echo ""
echo "✓ Sync complete."

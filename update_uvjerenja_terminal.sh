#!/usr/bin/env bash
set -euo pipefail

APP_ID="${APP_ID:-uvjerenja-terminal}"
APP_TITLE="${APP_TITLE:-Uvjerenja Terminal}"
DEFAULT_UPDATE_REPO_URL="https://github.com/velimirpaleksic/Raspberry-Pi.git"
REPO_URL="${POTVRDE_UPDATE_REPO_URL:-$DEFAULT_UPDATE_REPO_URL}"
SOURCE_DIR="${POTVRDE_UPDATE_SOURCE_DIR:-$HOME/Raspberry-Pi}"
BRANCH="${POTVRDE_UPDATE_BRANCH:-}"
TARGET="${POTVRDE_UPDATE_TARGET:-}"
ENV_FILE="${POTVRDE_ENV_FILE:-/etc/$APP_ID/$APP_ID.env}"
ENV_BACKUP_DIR="${POTVRDE_ENV_BACKUP_DIR:-/var/lib/$APP_ID/env-backups}"
UPDATE_TMP_DIR=""
SOURCE_ENV_SNAPSHOT=""
INSTALLED_ENV_SNAPSHOT=""
SOURCE_ENV_WAS_PRESENT=0
INSTALLED_ENV_WAS_PRESENT=0

log() {
  printf '[UPDATE] %s\n' "$1"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    printf '[UPDATE] Missing command: %s\n' "$1" >&2
    exit 1
  }
}

require_cmd git
require_cmd bash
require_cmd mktemp
require_cmd sudo

UPDATE_TMP_DIR="$(mktemp -d)"
SOURCE_ENV_SNAPSHOT="$UPDATE_TMP_DIR/source.env"
INSTALLED_ENV_SNAPSHOT="$UPDATE_TMP_DIR/installed.env"

restore_source_env() {
  if [[ "$SOURCE_ENV_WAS_PRESENT" != "1" || ! -f "$SOURCE_ENV_SNAPSHOT" || ! -d "$SOURCE_DIR" ]]; then
    return 0
  fi
  cp -p -- "$SOURCE_ENV_SNAPSHOT" "$SOURCE_DIR/.env"
}

cleanup_update_temp() {
  # Restore the source .env even when fetch/reset/install exits early.
  restore_source_env || true
  if [[ -n "$UPDATE_TMP_DIR" && -d "$UPDATE_TMP_DIR" ]]; then
    rm -rf -- "$UPDATE_TMP_DIR"
  fi
}
trap cleanup_update_temp EXIT

snapshot_env_files() {
  if [[ -f "$SOURCE_DIR/.env" ]]; then
    cp -p -- "$SOURCE_DIR/.env" "$SOURCE_ENV_SNAPSHOT"
    SOURCE_ENV_WAS_PRESENT=1
    log "Preserved source .env outside the Git work tree."
  fi

  if [[ -f "$ENV_FILE" ]]; then
    cp -p -- "$ENV_FILE" "$INSTALLED_ENV_SNAPSHOT"
    INSTALLED_ENV_WAS_PRESENT=1

    mkdir -p -- "$ENV_BACKUP_DIR"
    chmod 0700 "$ENV_BACKUP_DIR"
    local backup_path="$ENV_BACKUP_DIR/${APP_ID}.env.$(date +%Y%m%d-%H%M%S).$$.backup"
    cp -p -- "$ENV_FILE" "$backup_path"
    chmod 0600 "$backup_path"
    log "Backed up the installed env file to $backup_path"
  fi
}

restore_installed_env() {
  if [[ "$INSTALLED_ENV_WAS_PRESENT" != "1" || ! -f "$INSTALLED_ENV_SNAPSHOT" ]]; then
    return 0
  fi
  sudo cp -p -- "$INSTALLED_ENV_SNAPSHOT" "$ENV_FILE"
  sudo chmod 0600 "$ENV_FILE"
}

verify_existing_env_values_unchanged() {
  if [[ "$INSTALLED_ENV_WAS_PRESENT" != "1" ]]; then
    return 0
  fi
  if [[ ! -f "$ENV_FILE" ]]; then
    printf '[UPDATE] Installed env disappeared during update: %s\n' "$ENV_FILE" >&2
    restore_installed_env
    return 1
  fi

  local original_line key current_line
  while IFS= read -r original_line || [[ -n "$original_line" ]]; do
    if [[ ! "$original_line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
      continue
    fi
    key="${original_line%%=*}"
    current_line="$(grep -m1 -E "^${key}=" "$ENV_FILE" || true)"
    if [[ "$current_line" != "$original_line" ]]; then
      printf '[UPDATE] Refusing env change: existing value for %s was modified or removed.\n' "$key" >&2
      restore_installed_env
      return 1
    fi
  done < "$INSTALLED_ENV_SNAPSHOT"
  log "Verified that every pre-existing env value is unchanged."
}

commit_full() {
  git -C "$SOURCE_DIR" rev-parse --verify HEAD 2>/dev/null || true
}

commit_short() {
  git -C "$SOURCE_DIR" rev-parse --short HEAD 2>/dev/null || true
}

clean_source_tree() {
  git -C "$SOURCE_DIR" reset --hard >/dev/null
  if [[ -f "$SOURCE_DIR/.env" ]]; then
    git -C "$SOURCE_DIR" clean -fd -e .env
  else
    git -C "$SOURCE_DIR" clean -fd
  fi
}

if [[ -e "$SOURCE_DIR" && ! -d "$SOURCE_DIR/.git" ]]; then
  printf '[UPDATE] Source path exists but is not a Git repo: %s\n' "$SOURCE_DIR" >&2
  exit 1
fi

snapshot_env_files

PREVIOUS_COMMIT=""
if [[ -d "$SOURCE_DIR/.git" ]]; then
  PREVIOUS_COMMIT="$(commit_full)"
fi

if [[ ! -d "$SOURCE_DIR/.git" ]]; then
  log "Cloning $REPO_URL into $SOURCE_DIR ..."
  git clone "$REPO_URL" "$SOURCE_DIR"
else
  log "Using existing repo at $SOURCE_DIR ..."
  git -C "$SOURCE_DIR" remote set-url origin "$REPO_URL"
fi

if [[ -z "$BRANCH" ]]; then
  BRANCH="$(git -C "$SOURCE_DIR" branch --show-current || true)"
fi
if [[ -z "$BRANCH" ]]; then
  BRANCH="$(git -C "$SOURCE_DIR" remote show origin | awk '/HEAD branch/ {print $NF}' || true)"
fi
if [[ -z "$BRANCH" ]]; then
  BRANCH="main"
fi

log "Updating branch $BRANCH from origin ..."
git -C "$SOURCE_DIR" fetch --prune origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"
CHECKOUT_TARGET="origin/$BRANCH"
if [[ -n "$TARGET" ]]; then
  CHECKOUT_TARGET="$(git -C "$SOURCE_DIR" rev-parse --verify "$TARGET^{commit}")"
  log "Using explicitly verified target commit: $CHECKOUT_TARGET"
fi
log "Discarding local source changes before applying origin/$BRANCH ..."
clean_source_tree
git -C "$SOURCE_DIR" checkout -f -B "$BRANCH" "$CHECKOUT_TARGET"
git -C "$SOURCE_DIR" reset --hard "$CHECKOUT_TARGET"
clean_source_tree
restore_source_env

UPDATED_COMMIT="$(commit_full)"
UPDATED_SHORT="$(commit_short)"
UPDATED_SUBJECT="$(git -C "$SOURCE_DIR" log -1 --pretty=%s 2>/dev/null || true)"

if [[ -n "$PREVIOUS_COMMIT" ]]; then
  log "Previous commit: ${PREVIOUS_COMMIT:0:7} ($PREVIOUS_COMMIT)"
else
  log "Previous commit: none (fresh clone or unreadable source)"
fi
log "Updated branch: $BRANCH"
log "Updated commit: $UPDATED_SHORT ($UPDATED_COMMIT)"
if [[ -n "$UPDATED_SUBJECT" ]]; then
  log "Commit message: $UPDATED_SUBJECT"
fi

log "Running installer from $SOURCE_DIR ..."
chmod +x "$SOURCE_DIR/install_uvjerenja_terminal.sh"
APP_ID="$APP_ID" APP_TITLE="$APP_TITLE" "$SOURCE_DIR/install_uvjerenja_terminal.sh"
verify_existing_env_values_unchanged

log "Update complete. Updated to commit: $UPDATED_SHORT ($UPDATED_COMMIT)"

#!/usr/bin/env bash
set -euo pipefail

APP_ID="${APP_ID:-uvjerenja-terminal}"
APP_TITLE="${APP_TITLE:-Uvjerenja Terminal}"
DEFAULT_UPDATE_REPO_URL="https://github.com/velimirpaleksic/Raspberry-Pi.git"
REPO_URL="${POTVRDE_UPDATE_REPO_URL:-$DEFAULT_UPDATE_REPO_URL}"
SOURCE_DIR="${POTVRDE_UPDATE_SOURCE_DIR:-$HOME/Raspberry-Pi}"
BRANCH="${POTVRDE_UPDATE_BRANCH:-}"

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
log "Discarding local source changes before applying origin/$BRANCH ..."
clean_source_tree
git -C "$SOURCE_DIR" checkout -f -B "$BRANCH" "origin/$BRANCH"
git -C "$SOURCE_DIR" reset --hard "origin/$BRANCH"
clean_source_tree

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

log "Update complete. Updated to commit: $UPDATED_SHORT ($UPDATED_COMMIT)"

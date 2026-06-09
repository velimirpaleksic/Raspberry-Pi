#!/usr/bin/env bash
set -euo pipefail

APP_ID="${APP_ID:-uvjerenja-terminal}"
APP_TITLE="${APP_TITLE:-Uvjerenja Terminal}"
REPO_URL="${POTVRDE_UPDATE_REPO_URL:-https://github.com/velimirpaleksic/Raspberry-Pi.git}"
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
git -C "$SOURCE_DIR" fetch origin "$BRANCH"
log "Discarding local source changes before applying origin/$BRANCH ..."
clean_source_tree
git -C "$SOURCE_DIR" checkout -f -B "$BRANCH" "origin/$BRANCH"
git -C "$SOURCE_DIR" reset --hard "origin/$BRANCH"
clean_source_tree

log "Running installer from $SOURCE_DIR ..."
chmod +x "$SOURCE_DIR/install_uvjerenja_terminal.sh"
APP_ID="$APP_ID" APP_TITLE="$APP_TITLE" "$SOURCE_DIR/install_uvjerenja_terminal.sh"

log "Update complete."

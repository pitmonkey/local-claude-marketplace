#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$REPO_ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "No .env found at $ENV_FILE" >&2
  exit 1
fi

DATA_DIR=""
while IFS='=' read -r key val; do
  [[ "$key" =~ ^[[:space:]]*# ]] && continue
  [[ -z "$key" ]] && continue
  key="${key// /}"
  val="${val%%#*}"
  val="${val#"${val%%[![:space:]]*}"}"
  val="${val%"${val##*[![:space:]]}"}"
  if [[ "$key" == "DATA_DIR" ]]; then
    DATA_DIR="$val"
    break
  fi
done < "$ENV_FILE"

if [[ -z "$DATA_DIR" ]]; then
  echo "DATA_DIR not set in $ENV_FILE" >&2
  exit 1
fi

# Resolve relative path against repo root
if [[ "$DATA_DIR" != /* ]]; then
  DATA_DIR="$REPO_ROOT/$DATA_DIR"
fi
DATA_DIR="$(cd "$DATA_DIR" && pwd)"

if [[ ! -d "$DATA_DIR" ]]; then
  echo "DATA_DIR does not exist: $DATA_DIR" >&2
  exit 1
fi

read -r -p "Delete $DATA_DIR/* ? [y/N] " answer
if [[ "${answer,,}" != "y" ]]; then
  echo "Aborted."
  exit 0
fi

rm -rf "${DATA_DIR:?}"/*
echo "Deleted $DATA_DIR/*"


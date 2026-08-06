#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_URL="${REPO_URL:-https://github.com/EyalBriman/automation-book.git}"
BRANCH="${BRANCH:-main}"
COMMIT_MESSAGE="${COMMIT_MESSAGE:-Update automation book from Word}"

for command_name in git rsync; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "ERROR: $command_name is required but was not found." >&2
    exit 1
  fi
done

"$PROJECT_DIR/BUILD_SITE.sh" "${1:-$PROJECT_DIR/private-source/Automation_book4Aug2026.docx}"

UPLOAD_TEMP="$(mktemp -d "${TMPDIR:-/tmp}/automation-book-upload-XXXXXX")"
cleanup() {
  rm -rf -- "$UPLOAD_TEMP"
}
trap cleanup EXIT

git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$UPLOAD_TEMP/repository"
rsync -a --delete \
  --exclude '.git/' \
  --exclude 'private-source/' \
  --exclude '*.docx' \
  --exclude '~$*.docx' \
  "$PROJECT_DIR/" "$UPLOAD_TEMP/repository/"

cd "$UPLOAD_TEMP/repository"
git add -A
if git diff --cached --quiet; then
  echo "No public changes to upload."
  exit 0
fi

git commit -m "$COMMIT_MESSAGE"
git push origin "$BRANCH"
echo "Upload completed: $REPO_URL ($BRANCH)"


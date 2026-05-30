#!/bin/bash
# Upload media files to R2 bucket ielts-assets
# Usage: ./scripts/upload-to-r2.sh [audio|images|all]

BUCKET="ielts-assets"
MODE="${1:-all}"

if ! command -v wrangler &> /dev/null; then
  echo "wrangler not found. Run: npm install -g wrangler"
  exit 1
fi

upload_dir() {
  local dir="$1"
  local r2_prefix="$2"
  local mime="$3"
  local files
  files=$(find "$dir" -type f)
  local total
  total=$(echo "$files" | wc -l | tr -d ' ')
  local count=0
  echo "$files" | while read -r file; do
    local rel="${file#$dir/}"
    local key="$r2_prefix/$rel"
    wrangler r2 object put "$BUCKET/$key" --file="$file" --content-type="$mime" --remote 2>/dev/null
    count=$((count + 1))
    echo "[$count/$total] $key"
  done
  echo "Done: $total files → r2://$BUCKET/$r2_prefix/"
}

if [[ "$MODE" == "audio" || "$MODE" == "all" ]]; then
  echo "=== Uploading audio ==="
  upload_dir "public/audio" "listening" "audio/mpeg"
fi

if [[ "$MODE" == "images" || "$MODE" == "all" ]]; then
  echo "=== Uploading reading images ==="
  upload_dir "public/reading-img" "reading-img" "image/png"
  echo "=== Uploading listening images ==="
  upload_dir "public/listening-img" "listening-img" "image/png"
  echo "=== Uploading writing images ==="
  upload_dir "public/writing-img" "writing-img" "image/png"
fi

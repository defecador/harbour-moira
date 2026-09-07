#!/bin/bash
# Fetch the upstream yt-dlp zipapp into python/vendor/.
#
# The zipapp is a single file that Python imports directly from sys.path, so
# the app ships one ~3 MB artifact instead of an unpacked tree of extractors.
# Run this before packaging, and re-run it whenever YouTube breaks extraction.
set -euo pipefail

VERSION="${1:-latest}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$ROOT/python/vendor"
DEST="$VENDOR/yt-dlp.zip"

if [ "$VERSION" = "latest" ]; then
    URL="https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
else
    URL="https://github.com/yt-dlp/yt-dlp/releases/download/$VERSION/yt-dlp"
fi

mkdir -p "$VENDOR"
echo "Fetching $URL"
curl -fL --progress-bar -o "$DEST.tmp" "$URL"

# The release artifact is a zipapp; refuse anything that is not.
if ! python3 -c "import zipfile,sys; sys.exit(0 if zipfile.is_zipfile('$DEST.tmp') else 1)"; then
    rm -f "$DEST.tmp"
    echo "Downloaded file is not a zipapp - aborting." >&2
    exit 1
fi

mv "$DEST.tmp" "$DEST"
ROOT="$ROOT" python3 - <<'PY'
import os, sys
vendor = os.path.join(os.environ["ROOT"], "python", "vendor")
zipapp = os.path.join(vendor, "yt-dlp.zip")
sys.path.insert(0, zipapp)
from yt_dlp.version import __version__
print("Vendored yt-dlp %s (%.1f MB)" % (__version__, os.path.getsize(zipapp) / 1048576.0))
PY

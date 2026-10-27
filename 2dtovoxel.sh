#!/usr/bin/env sh
# Starts the 2DtoVoxel web UI on macOS / Linux (opens in the browser).
cd "$(dirname "$0")" || exit 1
exec python3 -m voxtool ui "$@"

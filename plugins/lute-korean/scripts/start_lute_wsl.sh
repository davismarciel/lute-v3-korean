#!/usr/bin/env bash
# The Windows Desktop shortcut runs this inside the Ubuntu WSL distribution.
set -Eeuo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
data_dir="${LUTE_KOREAN_DATA_DIR:-/home/davi/lute-korean-data}"
venv_dir="$repo_dir/.venv"
bridge="$repo_dir/plugins/lute-korean/scripts/wsl_ankiconnect_bridge.py"

if [[ ! -x "$venv_dir/bin/lute" || ! -x "$venv_dir/bin/python" ]]; then
    echo "Persistent Lute environment missing at $venv_dir" >&2
    exit 1
fi
if [[ ! -f "$data_dir/config.yml" ]]; then
    echo "Lute configuration missing at $data_dir/config.yml" >&2
    exit 1
fi
if ! command -v powershell.exe >/dev/null; then
    echo "Windows PowerShell is unavailable from WSL; the Anki bridge cannot start." >&2
    exit 1
fi

"$venv_dir/bin/python" "$bridge" &
bridge_pid=$!
cleanup() {
    kill "$bridge_pid" 2>/dev/null || true
    wait "$bridge_pid" 2>/dev/null || true
}
trap cleanup EXIT

ready=false
for _ in {1..30}; do
    if ! kill -0 "$bridge_pid" 2>/dev/null; then
        wait "$bridge_pid" || true
        echo "Anki bridge could not bind WSL 127.0.0.1:18765." >&2
        exit 1
    fi
    if "$venv_dir/bin/python" -c 'import socket; s=socket.socket(); s.settimeout(0.2); result=s.connect_ex(("127.0.0.1", 18765)); s.close(); raise SystemExit(result)' 2>/dev/null; then
        ready=true
        break
    fi
    sleep 0.1
done
if [[ "$ready" != true ]]; then
    echo "Anki bridge did not become ready on WSL 127.0.0.1:18765." >&2
    exit 1
fi

echo "Starting Lute with its local, read-only Windows Anki transport."
"$venv_dir/bin/lute" --local --config "$data_dir/config.yml" "$@"

#!/usr/bin/env sh
set -eu
BASE_URL="${1:-http://127.0.0.1:8000}"
python - "$BASE_URL" <<'PY'
import json, sys, time, urllib.request
base_url = sys.argv[1]
for attempt in range(20):
    try:
        with urllib.request.urlopen(base_url + "/health/ready", timeout=3) as response:
            payload = json.load(response)
        print(f"ShopPilot readiness={payload['status']}; runtime={payload['runtime']['runtime_mode']}")
        raise SystemExit(0)
    except Exception:
        if attempt == 19:
            raise
        time.sleep(2)
PY

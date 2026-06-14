#!/usr/bin/env python3
"""Background runner: uploads 1 TikTok video every 10 minutes."""
import subprocess, sys, time, signal
from pathlib import Path

INTERVAL = 600
script = Path(__file__).parent / "upload_tiktok_local.py"

def handler(sig, frame):
    sys.exit(0)

signal.signal(signal.SIGTERM, handler)

while True:
    subprocess.run([sys.executable, str(script)])
    time.sleep(INTERVAL)

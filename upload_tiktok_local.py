"""
Local TikTok upload script — runs on Mac where TikTok session is valid.
Reads credentials from .env, extracts sessionid from Chrome automatically.
Tracks state in state.json (same file as GitHub Actions for YouTube).
"""
import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

STATE_FILE = Path(__file__).parent / "state.json"
LOG_FILE = Path(__file__).parent / "tiktok_local.log"
LOCK_FILE = Path(__file__).parent / "tiktok.lock"
MAX_PER_RUN = 1


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def load_state() -> dict:
    if STATE_FILE.exists():
        s = json.loads(STATE_FILE.read_text())
        if "last_tiktok_message_id" not in s:
            s["last_tiktok_message_id"] = s.get("last_message_id", 0)
        return s
    return {"last_message_id": 0, "last_tiktok_message_id": 0, "total_uploaded": 0, "uploads_today": 0, "last_upload_date": ""}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_tiktok_sessionid() -> str:
    from pycookiecheat import BrowserType, chrome_cookies
    cookies = chrome_cookies("https://www.tiktok.com", browser=BrowserType.CHROME)
    return cookies.get("sessionid", "")


async def upload_to_tiktok(filepath: Path, description: str, sessionid: str) -> bool:
    uploader = Path(__file__).parent / "tiktok_upload_pw.py"
    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(uploader), str(filepath), description, sessionid,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    for line in (stdout.decode() + stderr.decode()).strip().splitlines():
        print(line, flush=True)
    return proc.returncode == 0


def is_video(msg) -> bool:
    if msg.video:
        return True
    if msg.document and msg.document.mime_type and msg.document.mime_type.startswith("video/"):
        return True
    return False


async def main():
    if LOCK_FILE.exists():
        log("Another instance is running. Skipping.")
        return
    LOCK_FILE.touch()
    try:
        await _main()
    finally:
        LOCK_FILE.unlink(missing_ok=True)


async def _main():
    load_dotenv(Path(__file__).parent / ".env")

    sessionid = get_tiktok_sessionid()
    if not sessionid:
        log("ERROR: No TikTok sessionid found in Chrome. Log in to tiktok.com and retry.")
        return

    state = load_state()

    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    session_str = os.environ["TELEGRAM_SESSION"]
    group_str = os.environ["TELEGRAM_GROUP"]
    group = int(group_str) if group_str.lstrip("-").isdigit() else group_str
    _raw = int(os.environ["TELEGRAM_TOPIC_ID"])
    topic_id = _raw % (2**32)
    if topic_id > 2**31 - 1:
        topic_id -= 2**32

    async with TelegramClient(StringSession(session_str), api_id, api_hash) as client:
        await client.get_dialogs()
        entity = await client.get_entity(group)

        msgs = []
        async for msg in client.iter_messages(entity, reply_to=topic_id, min_id=state["last_tiktok_message_id"]):
            if is_video(msg):
                msgs.append(msg)
        msgs.sort(key=lambda m: m.id)

        if not msgs:
            log("No new videos for TikTok.")
            return

        log(f"Found {len(msgs)} new video(s), processing up to {MAX_PER_RUN}.")

        for msg in msgs[:MAX_PER_RUN]:
            caption = (msg.message or "").strip()
            n = state["total_uploaded"] + 1
            title = caption if caption else f"DortmannKids Berlin #{n}"
            description = f"{title} #DortmannKids #Shorts"

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp_path = Path(tmp.name)

            try:
                size_mb = (msg.document.size if msg.document else 0) / 1024 / 1024
                log(f"Downloading message {msg.id} ({size_mb:.0f} MB)...")
                await client.download_media(msg, file=str(tmp_path))

                log(f"Uploading to TikTok: '{title}'...")
                ok = await upload_to_tiktok(tmp_path, description, sessionid)
                log(f"TikTok: {'uploaded OK' if ok else 'FAILED'}")

                if ok:
                    state["last_tiktok_message_id"] = msg.id
                    save_state(state)
                else:
                    log("Upload failed — stopping. Check TikTok session.")
                    break

            except Exception as e:
                log(f"Error on message {msg.id}: {e}")
                break
            finally:
                tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

STATE_FILE = Path("state.json")
MAX_DAILY_UPLOADS = 5
MAX_TIKTOK_PER_RUN = 10


def load_state() -> dict:
    if STATE_FILE.exists():
        s = json.loads(STATE_FILE.read_text())
        # migrate: seed last_tiktok_message_id from last_message_id
        if "last_tiktok_message_id" not in s:
            s["last_tiktok_message_id"] = s.get("last_message_id", 0)
        return s
    return {
        "last_message_id": 0,
        "last_tiktok_message_id": 0,
        "total_uploaded": 0,
        "uploads_today": 0,
        "last_upload_date": "",
    }


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_youtube_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


async def upload_tiktok(filepath: Path, description: str, sessionid: str) -> bool:
    # Run in a subprocess to avoid Playwright Sync API / asyncio loop conflict
    script = (
        "from tiktok_uploader.upload import upload_video; import sys; "
        "failed = upload_video(sys.argv[1], description=sys.argv[2], sessionid=sys.argv[3], headless=True, browser='chromium'); "
        "sys.exit(0 if not failed else 1)"
    )
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c", script, str(filepath), description, sessionid,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if stdout:
        print(stdout.decode().strip(), flush=True)
    if stderr:
        print(stderr.decode().strip(), flush=True)
    return proc.returncode == 0


def upload_youtube(youtube, filepath: Path, title: str) -> str:
    body = {
        "snippet": {
            "title": title,
            "description": "#Shorts #DortmannKids",
            "tags": ["shorts", "DortmannKids"],
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(filepath), chunksize=10 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    retries = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"  {int(status.progress() * 100)}%", flush=True)
            retries = 0
        except Exception as e:
            retries += 1
            if retries > 5:
                raise
            print(f"  Upload error (retry {retries}/5): {e}", flush=True)
    return response["id"]


def is_video(msg) -> bool:
    if msg.video:
        return True
    if msg.document and msg.document.mime_type and msg.document.mime_type.startswith("video/"):
        return True
    return False


async def fetch_videos(client, entity, topic_id: int, min_id: int) -> list:
    msgs = []
    async for msg in client.iter_messages(entity, reply_to=topic_id, min_id=min_id):
        if is_video(msg):
            msgs.append(msg)
    msgs.sort(key=lambda m: m.id)
    return msgs


async def run_tiktok(client, entity, topic_id: int, state: dict, tiktok_sessionid: str):
    msgs = await fetch_videos(client, entity, topic_id, state["last_tiktok_message_id"])
    if not msgs:
        print("TikTok: no new videos.")
        return

    print(f"TikTok: {len(msgs)} new video(s), processing up to {MAX_TIKTOK_PER_RUN} per run.")
    for msg in msgs[:MAX_TIKTOK_PER_RUN]:
        caption = (msg.message or "").strip()
        n = state["total_uploaded"] + 1
        title = caption if caption else f"DortmannKids Berlin #{n}"
        tiktok_desc = f"{title} #DortmannKids #Shorts"

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            size_mb = (msg.document.size if msg.document else 0) / 1024 / 1024
            print(f"TikTok: downloading message {msg.id} ({size_mb:.0f} MB)...", flush=True)
            await client.download_media(msg, file=str(tmp_path))

            ok = await upload_tiktok(tmp_path, tiktok_desc, tiktok_sessionid)
            print(f"TikTok: {'uploaded' if ok else 'failed'}")
            if not ok:
                await client.send_message(
                    "@alexanderdortmann",
                    "TikTok session expired. Please log in to tiktok.com in Chrome and tell me to refresh the cookie.",
                )

            state["last_tiktok_message_id"] = msg.id
            save_state(state)

        except Exception as e:
            print(f"TikTok error on message {msg.id} (non-fatal): {e}")
            await client.send_message(
                "@alexanderdortmann",
                f"TikTok upload error: {e}\nPlease log in to tiktok.com in Chrome and tell me to refresh the cookie.",
            )
        finally:
            tmp_path.unlink(missing_ok=True)


async def run_youtube(client, entity, topic_id: int, state: dict, youtube):
    if state["uploads_today"] >= MAX_DAILY_UPLOADS:
        print(f"YouTube: daily limit reached ({MAX_DAILY_UPLOADS}/day). Skipping.")
        return

    msgs = await fetch_videos(client, entity, topic_id, state["last_message_id"])
    if not msgs:
        print("YouTube: no new videos.")
        return

    print(f"YouTube: {len(msgs)} new video(s).")
    for msg in msgs:
        if state["uploads_today"] >= MAX_DAILY_UPLOADS:
            print("YouTube: daily limit reached mid-run. Will continue tomorrow.")
            break

        n = state["total_uploaded"] + 1
        caption = (msg.message or "").strip()
        title = caption if caption else f"DortmannKids Berlin #{n}"

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            size_mb = (msg.document.size if msg.document else 0) / 1024 / 1024
            print(f"YouTube: downloading message {msg.id} ({size_mb:.0f} MB)...", flush=True)
            await client.download_media(msg, file=str(tmp_path))

            print(f"YouTube: uploading '{title}'...", flush=True)
            video_id = upload_youtube(youtube, tmp_path, title)
            print(f"YouTube: done https://youtube.com/shorts/{video_id}")

            state["last_message_id"] = msg.id
            state["total_uploaded"] += 1
            state["uploads_today"] += 1
            save_state(state)

        except Exception as e:
            print(f"YouTube error on message {msg.id}: {e}")
            break
        finally:
            tmp_path.unlink(missing_ok=True)


async def main():
    state = load_state()
    today = date.today().isoformat()

    if state.get("last_upload_date") != today:
        state["uploads_today"] = 0
        state["last_upload_date"] = today
        save_state(state)

    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    session_str = os.environ["TELEGRAM_SESSION"]
    group_str = os.environ["TELEGRAM_GROUP"]
    group = int(group_str) if group_str.lstrip("-").isdigit() else group_str
    _raw = int(os.environ["TELEGRAM_TOPIC_ID"])
    topic_id = _raw % (2**32)
    if topic_id > 2**31 - 1:
        topic_id -= 2**32

    tiktok_sessionid = os.environ.get("TIKTOK_SESSIONID", "")
    youtube = get_youtube_service()

    async with TelegramClient(StringSession(session_str), api_id, api_hash) as client:
        await client.get_dialogs()
        entity = await client.get_entity(group)

        await run_youtube(client, entity, topic_id, state, youtube)

        if tiktok_sessionid:
            await run_tiktok(client, entity, topic_id, state, tiktok_sessionid)


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import json
import os
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


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_message_id": 0, "total_uploaded": 0, "uploads_today": 0, "last_upload_date": ""}


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


def upload_tiktok(filepath: Path, description: str, sessionid: str) -> bool:
    from tiktok_uploader.upload import upload_video as tiktok_upload_video
    failed = tiktok_upload_video(
        str(filepath),
        description=description,
        sessionid=sessionid,
        headless=True,
        browser="chromium",
    )
    return not failed


def upload_video(youtube, filepath: Path, title: str) -> str:
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


async def main():
    state = load_state()
    today = date.today().isoformat()

    if state.get("last_upload_date") != today:
        state["uploads_today"] = 0
        state["last_upload_date"] = today

    if state["uploads_today"] >= MAX_DAILY_UPLOADS:
        print(f"Daily limit reached ({MAX_DAILY_UPLOADS}/day). Skipping.")
        return

    youtube = get_youtube_service()
    tiktok_sessionid = os.environ.get("TIKTOK_SESSIONID", "")

    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    session_str = os.environ["TELEGRAM_SESSION"]
    group_str = os.environ["TELEGRAM_GROUP"]
    group = int(group_str) if group_str.lstrip("-").isdigit() else group_str
    # Telegram Web sometimes encodes topic IDs > 2^32; convert to signed 32-bit
    _raw = int(os.environ["TELEGRAM_TOPIC_ID"])
    topic_id = _raw % (2**32)
    if topic_id > 2**31 - 1:
        topic_id -= 2**32

    async with TelegramClient(StringSession(session_str), api_id, api_hash) as client:
        # Must load dialogs first so Telethon knows the entity type (chat vs channel)
        await client.get_dialogs()
        entity = await client.get_entity(group)

        video_messages = []
        async for msg in client.iter_messages(
            entity,
            reply_to=topic_id,
            min_id=state["last_message_id"],
        ):
            if is_video(msg):
                video_messages.append(msg)

        video_messages.sort(key=lambda m: m.id)

        if not video_messages:
            print("No new videos.")
            return

        print(f"Found {len(video_messages)} new video(s).")

        for msg in video_messages:
            if state["uploads_today"] >= MAX_DAILY_UPLOADS:
                print("Daily limit reached mid-run. Will continue tomorrow.")
                break

            n = state["total_uploaded"] + 1
            caption = (msg.message or "").strip()
            title = caption if caption else f"DortmannKids Berlin #{n}"

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp_path = Path(tmp.name)

            try:
                size_mb = (msg.document.size if msg.document else 0) / 1024 / 1024
                print(f"Downloading message {msg.id} ({size_mb:.0f} MB)...", flush=True)
                await client.download_media(msg, file=str(tmp_path))

                print(f"Uploading '{title}'...", flush=True)
                video_id = upload_video(youtube, tmp_path, title)
                print(f"Done: https://youtube.com/shorts/{video_id}")

                if tiktok_sessionid:
                    tiktok_desc = f"{title} #DortmannKids #Shorts"
                    try:
                        ok = upload_tiktok(tmp_path, tiktok_desc, tiktok_sessionid)
                        print(f"TikTok: {'uploaded' if ok else 'failed'}")
                    except Exception as e:
                        print(f"TikTok error (non-fatal): {e}")

                state["last_message_id"] = msg.id
                state["total_uploaded"] += 1
                state["uploads_today"] += 1
                save_state(state)

            except Exception as e:
                print(f"Error on message {msg.id}: {e}")
                # don't advance last_message_id so we retry next run
                break
            finally:
                tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())

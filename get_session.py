"""
Run once to generate and save Telegram session string to .env.
"""
import re
from pathlib import Path

from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

ENV_FILE = Path(__file__).parent / ".env"

load_dotenv(ENV_FILE)

api_id = int(input("TELEGRAM_API_ID: ").strip())
api_hash = input("TELEGRAM_API_HASH: ").strip()

with TelegramClient(StringSession(), api_id, api_hash) as client:
    session = client.session.save()

print("\n--- Session string ---")
print(session)
print("----------------------")

# Write to .env
content = ENV_FILE.read_text() if ENV_FILE.exists() else ""

if "TELEGRAM_SESSION=" in content:
    content = re.sub(r"TELEGRAM_SESSION=.*", f"TELEGRAM_SESSION={session}", content)
else:
    content += f"\nTELEGRAM_SESSION={session}\n"

if "TELEGRAM_API_ID=" not in content:
    content = f"TELEGRAM_API_ID={api_id}\n" + content
if "TELEGRAM_API_HASH=" not in content:
    content = f"TELEGRAM_API_HASH={api_hash}\n" + content

ENV_FILE.write_text(content)
print(f"\nSaved to {ENV_FILE}")

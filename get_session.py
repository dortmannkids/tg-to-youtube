"""
Run this script ONCE on your local machine to generate a Telegram session string.
Save the output as the TELEGRAM_SESSION GitHub secret.
"""
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("TELEGRAM_API_ID: "))
api_hash = input("TELEGRAM_API_HASH: ")

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\n--- Copy this as TELEGRAM_SESSION secret ---")
    print(client.session.save())
    print("--------------------------------------------")

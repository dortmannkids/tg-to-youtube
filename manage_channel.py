"""
Manage YouTube channel: description, keywords, banner.
Run locally with: python3 manage_channel.py
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

load_dotenv(Path(__file__).parent / ".env")


def get_youtube():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def show_channel(yt):
    resp = yt.channels().list(part="snippet,brandingSettings", mine=True).execute()
    ch = resp["items"][0]
    s = ch["snippet"]
    b = ch.get("brandingSettings", {}).get("channel", {})
    print(f"\nКанал: {s['title']}")
    print(f"ID: {ch['id']}")
    print(f"Описание:\n  {s.get('description', '(пусто)').replace(chr(10), chr(10) + '  ')}")
    print(f"Ключевые слова: {b.get('keywords', '(нет)')}")
    return ch["id"]


def update_description(yt, channel_id):
    print("\nВведи новое описание (Enter дважды для завершения):")
    lines = []
    while True:
        line = input()
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)
    description = "\n".join(lines[:-1] if lines and lines[-1] == "" else lines)

    yt.channels().update(
        part="snippet",
        body={
            "id": channel_id,
            "snippet": {"description": description, "country": "DE"},
        },
    ).execute()
    print("Описание обновлено.")


def update_keywords(yt, channel_id):
    print("\nВведи ключевые слова через запятую:")
    kw = input().strip()
    yt.channels().update(
        part="brandingSettings",
        body={
            "id": channel_id,
            "brandingSettings": {"channel": {"keywords": kw}},
        },
    ).execute()
    print("Ключевые слова обновлены.")


def upload_banner(yt, channel_id):
    print("\nПуть к файлу баннера (min 2048x1152px, max 6MB, JPG/PNG):")
    path = input().strip().strip('"')
    if not Path(path).exists():
        print("Файл не найден.")
        return
    media = MediaFileUpload(path, mimetype="image/png", resumable=True)
    resp = yt.channelBanners().insert(media_body=media).execute()
    banner_url = resp["url"]
    yt.channels().update(
        part="brandingSettings",
        body={
            "id": channel_id,
            "brandingSettings": {"image": {"bannerExternalUrl": banner_url}},
        },
    ).execute()
    print(f"Баннер загружен: {banner_url}")


def main():
    yt = get_youtube()
    channel_id = show_channel(yt)

    while True:
        print("\nЧто делаем?")
        print("  1 — обновить описание")
        print("  2 — обновить ключевые слова")
        print("  3 — загрузить баннер")
        print("  4 — показать текущие данные")
        print("  0 — выход")
        choice = input("Выбор: ").strip()

        if choice == "1":
            update_description(yt, channel_id)
        elif choice == "2":
            update_keywords(yt, channel_id)
        elif choice == "3":
            upload_banner(yt, channel_id)
        elif choice == "4":
            show_channel(yt)
        elif choice == "0":
            break
        else:
            print("Неверный выбор.")


if __name__ == "__main__":
    main()

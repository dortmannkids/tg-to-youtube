# tg-to-youtube

Автоматически загружает видео из темы Telegram-группы на YouTube-канал.
Запускается каждые 10 минут через GitHub Actions. Лимит: 5 видео в день.

---

## Шаг 1 — Создать публичный репозиторий на GitHub

1. Зайди на github.com, создай новый **публичный** репозиторий (например, `tg-to-youtube`).
2. Загрузи все файлы из этой папки в репозиторий.

> Публичный репозиторий = бесплатные неограниченные минуты GitHub Actions.

---

## Шаг 2 — Получить Telegram API credentials

1. Зайди на https://my.telegram.org
2. Войди в свой аккаунт → "API development tools"
3. Создай приложение, получи `api_id` (число) и `api_hash` (строка)

---

## Шаг 3 — Сгенерировать Telegram session string

На своём компьютере:

```bash
pip install telethon
python get_session.py
```

Введи `api_id` и `api_hash`. Telegram попросит код из SMS.
Скопируй длинную строку — это `TELEGRAM_SESSION`.

---

## Шаг 4 — Найти ID группы и темы

**Группа (`TELEGRAM_GROUP`):**
- Если у группы есть @username — используй его (например, `@mygroupname`)
- Если нет — открой группу в Telegram Web (web.telegram.org), в URL будет число вроде `-1001234567890` — это и есть ID

**Тема (`TELEGRAM_TOPIC_ID`):**
1. Открой группу в Telegram Web (web.telegram.org)
2. Кликни на нужную тему
3. В URL появится `?thread=12345` — число `12345` и есть `TELEGRAM_TOPIC_ID`

---

## Шаг 5 — Получить YouTube credentials

1. Зайди на https://console.cloud.google.com
2. Создай новый проект
3. Перейди в "APIs & Services" → "Enable APIs" → найди и включи **YouTube Data API v3**
4. Перейди в "APIs & Services" → "Credentials" → "Create Credentials" → **OAuth client ID**
   - Application type: **Desktop app**
   - Скопируй `client_id` и `client_secret`
5. В "OAuth consent screen" добавь свой Google-аккаунт в "Test users"

Теперь запусти на своём компьютере:

```bash
python get_youtube_token.py
```

Откроется браузер, войди в свой Google-аккаунт (тот, что привязан к YouTube-каналу).
Скопируй `YOUTUBE_REFRESH_TOKEN` из вывода.

---

## Шаг 6 — Добавить secrets в GitHub

В репозитории: **Settings → Secrets and variables → Actions → New repository secret**

Добавь 8 секретов:

| Имя | Значение |
|-----|---------|
| `TELEGRAM_API_ID` | число из шага 2 |
| `TELEGRAM_API_HASH` | строка из шага 2 |
| `TELEGRAM_SESSION` | длинная строка из шага 3 |
| `TELEGRAM_GROUP` | @username или -100... из шага 4 |
| `TELEGRAM_TOPIC_ID` | число из шага 4 |
| `YOUTUBE_CLIENT_ID` | из шага 5 |
| `YOUTUBE_CLIENT_SECRET` | из шага 5 |
| `YOUTUBE_REFRESH_TOKEN` | из шага 5 |

---

## Шаг 7 — Запустить вручную первый раз

В репозитории: **Actions → "Upload Telegram videos to YouTube" → Run workflow**

Проверь логи. Если всё ок — дальше будет запускаться автоматически каждые 10 минут.

---

## Как это работает

- Скрипт запоминает ID последнего обработанного сообщения в `state.json`
- При каждом запуске берёт только новые видео
- Название на YouTube: `DortmannKids #1`, `DortmannKids #2` и т.д.
- Лимит 5 видео в день (квота YouTube API: ~6/день)
- Если в день постишь больше 5 видео, остальные встанут в очередь на следующий день

import os
import time
import hashlib
import requests
from bs4 import BeautifulSoup

# ================== НАЛАШТУВАННЯ ==================
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = int(os.environ["CHAT_ID"])

EN_URL = "https://www.counter-strike.net/news/updates?l=english"
UA_URL = "https://www.counter-strike.net/news/updates?l=ukrainian"

CHECK_INTERVAL_SECONDS = 30
STATE_FILE = "last_update_hash.txt"
# ==================================================


def send_message(text: str) -> None:
    """Надіслати повідомлення в Telegram-групу."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, data=payload, timeout=15)
    if not resp.ok:
        print("Telegram error:", resp.status_code, resp.text)


def split_into_parts(text: str, max_len: int = 3800):
    """Ділимо довгий текст на частини, щоб вмістити в Telegram (4096 символів)."""
    parts = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break

        cut = text.rfind("\n", 0, max_len)
        if cut == -1 or cut < max_len * 0.5:
            cut = max_len

        parts.append(text[:cut])
        text = text[cut:].lstrip("\n ")
    return parts


def fetch_update_text(url: str) -> str:
    """Завантажує HTML сторінки оновлення та витягує видимий текст."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Прибираємо службові блоки
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned = "\n".join(lines)
    return cleaned


def load_last_hash() -> str | None:
    """Зчитуємо хеш останнього оновлення з файлу."""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            v = f.read().strip()
            return v or None
    except FileNotFoundError:
        return None


def save_last_hash(h: str) -> None:
    """Зберігаємо новий хеш у файл."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(h)


def check_for_update() -> None:
    """Перевіряємо, чи змінився текст оновлення. Якщо так — надсилаємо EN+UA."""
    print("Checking for updates...")

    en_text = fetch_update_text(EN_URL)
    en_hash = hashlib.sha256(en_text.encode("utf-8")).hexdigest()

    last_hash = load_last_hash()
    if last_hash == en_hash:
        print("No new update.")
        return

    print("New update detected! Sending to Telegram...")

    ua_text = None
    try:
        ua_text = fetch_update_text(UA_URL)
    except Exception as e:
        print("Error while fetching Ukrainian version, will send English only:", e)

    if ua_text:
        final_text = (
            "🔥 <b>NEW COUNTER-STRIKE UPDATE</b>\n\n"
            "🇬🇧 <b>English:</b>\n"
            f"{en_text}\n\n"
            "🇺🇦 <b>Українською:</b>\n"
            f"{ua_text}"
        )
    else:
        final_text = (
            "🔥 <b>NEW COUNTER-STRIKE UPDATE</b>\n\n"
            "⚠️ Не вдалося завантажити українську версію — надсилаю англійську.\n\n"
            "🇬🇧 <b>English:</b>\n"
            f"{en_text}"
        )

    parts = split_into_parts(final_text)
    total = len(parts)

    for i, part in enumerate(parts, start=1):
        prefix = f"(Part {i}/{total})\n" if total > 1 else ""
        send_message(prefix + part)
        time.sleep(1)

    save_last_hash(en_hash)
    print("Update sent and hash saved.")


def main() -> None:
    print("Bot started. Monitoring Counter-Strike updates...")

    # Якщо запускаємось у GitHub Actions — робимо ОДНУ перевірку і виходимо
    if os.environ.get("RUN_ONCE") == "1":
        check_for_update()
        return

    # Локальний/серверний режим (якщо колись знадобиться)
    while True:
        try:
            check_for_update()
        except Exception as e:
            print("Error in check_for_update():", e)
        time.sleep(CHECK_INTERVAL_SECONDS)

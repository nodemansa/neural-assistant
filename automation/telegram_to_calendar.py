
import os
import re
import logging
import subprocess
import unicodedata
from datetime import datetime, timedelta

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# -------- logging --------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("bot")
VERSION = "tgcal-0.4"
log.warning("STARTUP %s running_file=%s", VERSION, __file__)

# -------- env --------
load_dotenv()

BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
ALLOWED_CHAT_ID = (os.getenv("TELEGRAM_ALLOWED_CHAT_ID") or "").strip()  # optional
DEFAULT_CALENDAR_NAME = (os.getenv("APPLE_CALENDAR_NAME") or "Home").strip() or "Home"
DEFAULT_DURATION_MINUTES = 60


# -------- helpers --------
def is_allowed_chat(update: Update) -> bool:
    """If TELEGRAM_ALLOWED_CHAT_ID is set, only allow that chat_id."""
    if not ALLOWED_CHAT_ID:
        return True
    try:
        chat_id = str(update.effective_chat.id)
    except Exception:
        return False
    return chat_id == ALLOWED_CHAT_ID


def normalize_text(s: str) -> str:
    """Normalize Telegram text by removing invisible formatting chars and normalizing whitespace."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u00A0", " ").replace("\u202F", " ")
    for ch in (
        "\u200b", "\u200c", "\u200d", "\ufeff",
        "\u200e", "\u200f",
        "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
    ):
        s = s.replace(ch, "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _escape_applescript_string(s: str) -> str:
    return s.replace('"', '\\"')


def create_calendar_event_applescript(
    calendar_name: str,
    title: str,
    start_dt: datetime,
    end_dt: datetime,
) -> None:
    """Create an Apple Calendar event using AppleScript (locale-safe)."""
    safe_title = _escape_applescript_string(title)
    safe_calendar = _escape_applescript_string(calendar_name)

    start_month = start_dt.strftime("%B")
    end_month = end_dt.strftime("%B")

    script = f'''
tell application "Calendar"
  set calName to "{safe_calendar}"

  set startDate to (current date)
  set year of startDate to {start_dt.year}
  set month of startDate to {start_month}
  set day of startDate to {start_dt.day}
  set hours of startDate to {start_dt.hour}
  set minutes of startDate to {start_dt.minute}
  set seconds of startDate to 0

  set endDate to (current date)
  set year of endDate to {end_dt.year}
  set month of endDate to {end_month}
  set day of endDate to {end_dt.day}
  set hours of endDate to {end_dt.hour}
  set minutes of endDate to {end_dt.minute}
  set seconds of endDate to 0

  tell calendar calName
    make new event with properties {{summary:"{safe_title}", start date:startDate, end date:endDate}}
  end tell
end tell
'''

    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "osascript failed").strip())


def parse_add_command(text: str) -> tuple[datetime, datetime, str]:
    """
    Accepts either:
      /add YYYY-MM-DD HH:MM Title...
      /add YYYY-MM-DD HH:MM HH:MM Title...
      YYYY-MM-DD HH:MM Title...
      YYYY-MM-DD HH:MM HH:MM Title...
      MM/DD HH:MM Title...        (assumes current year)
      MM/DD HH:MM HH:MM Title...  (assumes current year)
    """
    text = normalize_text(text or "")
    parts = text.split()
    if not parts:
        raise ValueError("empty")

    if parts[0].lower() == "/add":
        parts = parts[1:]

    if len(parts) < 3:
        raise ValueError("Usage: /add YYYY-MM-DD HH:MM [HH:MM] Title")

    date_part = parts[0]
    start_part = parts[1]

    # Date
    if "-" in date_part:
        date_obj = datetime.strptime(date_part, "%Y-%m-%d").date()
    elif "/" in date_part:
        m, d = date_part.split("/")
        y = datetime.now().year
        date_obj = datetime(year=y, month=int(m), day=int(d)).date()
    else:
        raise ValueError("Date must be YYYY-MM-DD or MM/DD")

    # Start time
    start_time = datetime.strptime(start_part, "%H:%M").time()
    start_dt = datetime.combine(date_obj, start_time)

    # Optional end time
    end_dt = start_dt + timedelta(minutes=DEFAULT_DURATION_MINUTES)
    title_start_idx = 2

    if len(parts) >= 4 and re.fullmatch(r"\d{1,2}:\d{2}", parts[2]):
        end_time = datetime.strptime(parts[2], "%H:%M").time()
        end_dt = datetime.combine(date_obj, end_time)
        title_start_idx = 3

    title = " ".join(parts[title_start_idx:]).strip()
    if not title:
        raise ValueError("Missing title")

    if end_dt <= start_dt:
        raise ValueError("End time must be after start time")

    return start_dt, end_dt, title


# -------- telegram handlers --------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed_chat(update):
        return
    await update.message.reply_text("✅ bot is alive")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed_chat(update):
        return
    await update.message.reply_text(
        "Commands:\n"
        "/start - health check\n"
        "/help - show this help\n"
        "/add 2026-03-06 15:00 Teammeeting\n"
        "/add 2026-03-06 15:00 17:00 Teammeeting\n"
        "Also works without /add:\n"
        "2026-03-06 15:00 Teammeeting\n"
    )


async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed_chat(update):
        return
    if update.message is None:
        return

    raw_text = update.message.text or ""
    text = normalize_text(raw_text)

    try:
        start_dt, end_dt, title = parse_add_command(text)
        create_calendar_event_applescript(
            calendar_name=DEFAULT_CALENDAR_NAME,
            title=title,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        await update.message.reply_text(
            f"✅ Added: {start_dt.strftime('%Y-%m-%d %H:%M')}–{end_dt.strftime('%H:%M')} {title}\n"
            f"(Calendar: {DEFAULT_CALENDAR_NAME})"
        )
    except Exception as e:
        await update.message.reply_text(
            "❌ Failed.\n"
            "Usage:\n"
            "/add 2026-03-06 15:00 Teammeeting\n"
            "/add 2026-03-06 15:00 17:00 Teammeeting\n"
            "or\n"
            "2026-03-06 15:00 Teammeeting\n"
            f"\nError: {e}"
        )


async def echo_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed_chat(update):
        return

    # Some update types may not include a message; avoid crashes.
    if update.message is None:
        log.info("ECHO_SKIP update_has_no_message update=%s", type(update))
        return

    chat_id = update.effective_chat.id
    raw_text = update.message.text or ""
    text = normalize_text(raw_text)

    log.warning("ECHO_ENTER chat_id=%s raw=%r normalized=%r", chat_id, raw_text, text)

    # Always try parse first. If parse fails -> echo.
    try:
        start_dt, end_dt, title = parse_add_command(text)
        log.warning("PARSE_OK start=%s end=%s title=%r", start_dt, end_dt, title)
    except Exception as e:
        log.warning("PARSE_SKIP reason=%s", e)
        await update.message.reply_text(
            f"chat_id: {chat_id}\n"
            f"you said: {text}"
        )
        return

    # Parsed OK -> create event
    try:
        create_calendar_event_applescript(
            calendar_name=DEFAULT_CALENDAR_NAME,
            title=title,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        await update.message.reply_text(
            f"✅ Added: {start_dt.strftime('%Y-%m-%d %H:%M')}–{end_dt.strftime('%H:%M')} {title}\n"
            f"(Calendar: {DEFAULT_CALENDAR_NAME})"
        )
    except Exception as e:
        log.exception("CREATE_FAIL")
        await update.message.reply_text(
            "❌ Calendar add failed (after parse).\n"
            f"Error: {e}"
        )


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("❌ Missing TELEGRAM_BOT_TOKEN in .env")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_msg))

    log.info("Bot started (polling). Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()

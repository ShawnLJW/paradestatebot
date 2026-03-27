import logging
import os
import sqlite3
from datetime import date, time
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


async def send_parade_state(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    lines: list[str] = []
    lines.append(f"*Parade state for {date.today().strftime('%y%m%d')}*")
    lines.append("Total strength: /")

    with sqlite3.connect("bot.db") as connection:
        cursor = connection.cursor()
        rows = cursor.execute("SELECT rank, name FROM personnel")
        personnel = [(row[0], row[1]) for row in rows.fetchall()]

    for rank, name in personnel:
        lines.append(f"- {rank} {name} ✅")

    _ = await context.bot.send_message(
        chat_id=chat_id,
        text="\n".join(lines),
    )


async def send_parade_state_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    assert job is not None
    chat_id = job.chat_id
    assert chat_id is not None
    await send_parade_state(context, chat_id)


async def send_parade_state_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    assert chat is not None
    chat_id = chat.id
    await send_parade_state(context, chat_id)


async def add_personnel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    assert message is not None

    args = context.args or []

    if len(args) < 2:
        _ = await message.reply_text("Usage: /addpersonnel <rank> <name...>")
        return

    rank = args[0].strip()
    name = " ".join(args[1:]).strip()

    if not rank or not name:
        _ = await message.reply_text("Usage: /addpersonnel <rank> <name...>")
        return

    with sqlite3.connect("bot.db") as connection:
        cursor = connection.cursor()
        _ = cursor.execute(
            "CREATE TABLE IF NOT EXISTS personnel (rank TEXT, name TEXT)"
        )
        _ = cursor.execute(
            "INSERT INTO personnel (rank, name) VALUES (?, ?)",
            (rank, name),
        )
        connection.commit()

    _ = await message.reply_text(f"Added {rank} {name} to personnel.")


def schedule_job(chat_id: int, job_queue):
    _ = job_queue.run_daily(
        send_parade_state_job,
        time(hour=8, minute=0, second=0, tzinfo=ZoneInfo("Asia/Singapore")),
        days=(1, 2, 3, 4, 5),
        chat_id=chat_id,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    assert chat is not None
    chat_id = chat.id
    schedule_job(chat_id, context.job_queue)
    with sqlite3.connect("bot.db") as connection:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO jobs VALUES (?)", (str(chat_id),))
    _ = await context.bot.send_message(
        chat_id=chat_id,
        text="Parade state is scheduled at 8am",
    )


def load_jobs(job_queue):
    with sqlite3.connect("bot.db") as connection:
        cursor = connection.cursor()
        _ = cursor.execute("CREATE TABLE IF NOT EXISTS jobs (chat_id INTEGER)")
        _ = cursor.execute(
            "CREATE TABLE IF NOT EXISTS personnel (rank TEXT, name TEXT)"
        )
        rows = cursor.execute("SELECT chat_id FROM jobs")
        chat_ids = [row[0] for row in rows.fetchall()]
    for chat_id in chat_ids:
        schedule_job(chat_id, job_queue)


if __name__ == "__main__":
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    assert BOT_TOKEN, "No token in environment variables"

    application = ApplicationBuilder().token(BOT_TOKEN).build()
    load_jobs(application.job_queue)

    start_handler = CommandHandler("start", start)
    send_handler = CommandHandler("send", send_parade_state_command)
    add_personnel_handler = CommandHandler("addpersonnel", add_personnel_command)

    application.add_handler(start_handler)
    application.add_handler(send_handler)
    application.add_handler(add_personnel_handler)

    application.run_polling()

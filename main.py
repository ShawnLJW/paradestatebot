import logging
import os
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from db import (
    add_absence,
    add_personnel,
    get_personnel_id,
    init_db,
    list_absences_for_date,
    list_job_chat_ids,
    list_personnel,
    remove_personnel,
    remove_absence,
    save_job,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


async def send_parade_state(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    personnel = list_personnel("bot.db")
    absences = list_absences_for_date("bot.db", date.today().isoformat())
    lines: list[str] = []

    lines.append(f"*Parade state for {date.today().strftime('%d%m%y')}*")
    lines.append(f"Total strength: {len(personnel) - len(absences)}/{len(personnel)}")
    lines.append("")
    for personnel_id, rank, name in personnel:
        reason = absences.get(personnel_id)
        if reason:
            lines.append(f"- {rank} {name} ❌ {reason}")
        else:
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

    add_personnel("bot.db", rank, name)

    _ = await message.reply_text(f"Added {rank} {name} to personnel.")


async def remove_personnel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    assert message is not None

    args = context.args or []

    if len(args) < 2:
        _ = await message.reply_text("Usage: /removepersonnel <rank> <name...>")
        return

    rank = args[0].strip()
    name = " ".join(args[1:]).strip()

    if not rank or not name:
        _ = await message.reply_text("Usage: /removepersonnel <rank> <name...>")
        return

    removed = remove_personnel("bot.db", rank, name)

    if removed:
        _ = await message.reply_text(f"Removed {rank} {name} from personnel.")
    else:
        _ = await message.reply_text(f"No personnel found for {rank} {name}.")


async def absent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    assert message is not None

    args = context.args or []

    if len(args) < 3:
        _ = await message.reply_text(
            "Usage: /absent <rank> <name...> <DDMMYY> <reason...>"
        )
        return

    rank = args[0].strip()
    date_index = None
    for index in range(1, len(args)):
        try:
            date.fromisoformat(args[index])
        except ValueError:
            continue
        date_index = index
        break

    if date_index is None or date_index == 1 or date_index == len(args) - 1:
        _ = await message.reply_text(
            "Usage: /absent <rank> <name...> <DDMMYY> <reason...>"
        )
        return

    name = " ".join(args[1:date_index]).strip()
    date_text = args[date_index].strip()
    reason = " ".join(args[date_index + 1 :]).strip()

    if not rank or not name or not date_text or not reason:
        _ = await message.reply_text(
            "Usage: /absent <rank> <name...> <DDMMYY> <reason...>"
        )
        return

    try:
        absent_date = datetime.strptime(date_text, "%d%m%y").date()
    except ValueError:
        _ = await message.reply_text("Date must be in DDMMYY format.")
        return

    personnel_id = get_personnel_id("bot.db", rank, name)
    if personnel_id is None:
        _ = await message.reply_text(f"No personnel found for {rank} {name}.")
        return

    add_absence("bot.db", personnel_id, absent_date.isoformat(), reason)
    _ = await message.reply_text(
        f"Marked {rank} {name} absent on {absent_date.strftime('%d%m%y')}."
    )


async def present_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    assert message is not None

    args = context.args or []

    if len(args) < 3:
        _ = await message.reply_text("Usage: /present <rank> <name...> <DDMMYY>")
        return

    rank = args[0].strip()
    date_index = None
    for index in range(1, len(args)):
        try:
            date.fromisoformat(args[index])
        except ValueError:
            continue
        date_index = index
        break

    if date_index is None or date_index == 1:
        _ = await message.reply_text("Usage: /present <rank> <name...> <DDMMYY>")
        return

    name = " ".join(args[1:date_index]).strip()
    date_text = args[date_index].strip()

    if not rank or not name or not date_text:
        _ = await message.reply_text("Usage: /present <rank> <name...> <DDMMYY>")
        return

    try:
        absent_date = datetime.strptime(date_text, "%d%m%y").date()
    except ValueError:
        _ = await message.reply_text("Date must be in DDMMYY format.")
        return

    personnel_id = get_personnel_id("bot.db", rank, name)
    if personnel_id is None:
        _ = await message.reply_text(f"No personnel found for {rank} {name}.")
        return

    removed = remove_absence("bot.db", personnel_id, absent_date.isoformat())
    if removed:
        _ = await message.reply_text(
            f"Marked {rank} {name} present on {absent_date.strftime('%d%m%y')}."
        )
    else:
        _ = await message.reply_text(
            f"No absence found for {rank} {name} on {absent_date.strftime('%d%m%y')}."
        )


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
    save_job("bot.db", chat_id)
    _ = await context.bot.send_message(
        chat_id=chat_id,
        text="Parade state is scheduled at 8am",
    )


def load_jobs(job_queue):
    chat_ids = list_job_chat_ids("bot.db")
    for chat_id in chat_ids:
        schedule_job(chat_id, job_queue)


if __name__ == "__main__":
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    assert BOT_TOKEN, "No token in environment variables"

    init_db("bot.db")

    application = ApplicationBuilder().token(BOT_TOKEN).build()
    load_jobs(application.job_queue)

    start_handler = CommandHandler("start", start)
    send_handler = CommandHandler("send", send_parade_state_command)
    add_personnel_handler = CommandHandler("addpersonnel", add_personnel_command)
    remove_personnel_handler = CommandHandler(
        "removepersonnel", remove_personnel_command
    )
    absent_handler = CommandHandler("absent", absent_command)
    present_handler = CommandHandler("present", present_command)

    application.add_handler(start_handler)
    application.add_handler(send_handler)
    application.add_handler(add_personnel_handler)
    application.add_handler(remove_personnel_handler)
    application.add_handler(absent_handler)
    application.add_handler(present_handler)

    application.run_polling()

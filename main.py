import logging
import os
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from db import (
    add_absence,
    add_personnel,
    get_personnel_id,
    init_db,
    list_absences_for_date,
    list_absences_for_personnel,
    list_job_chat_ids,
    list_personnel,
    remove_absence,
    remove_personnel,
    save_job,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


CATEGORIES = ["OFFICER", "WOSPEC", "TROOPER"]
RANK_TO_CATEGORY: dict[str, str] = {
    "PTE": "TROOPER",
    "LCP": "TROOPER",
    "CPL": "TROOPER",
    "CFC": "TROOPER",
    "3SG": "WOSPEC",
    "2SG": "WOSPEC",
    "1SG": "WOSPEC",
    "SSG": "WOSPEC",
    "MSG": "WOSPEC",
    "3WO": "WOSPEC",
    "2WO": "WOSPEC",
    "1WO": "WOSPEC",
    "MWO": "WOSPEC",
    "SWO": "WOSPEC",
    "CWO": "WOSPEC",
    "2LT": "OFFICER",
    "LTA": "OFFICER",
    "CPT": "OFFICER",
    "MAJ": "OFFICER",
    "LTC": "OFFICER",
    "SLTC": "OFFICER",
    "COL": "OFFICER",
    "BG": "OFFICER",
    "MG": "OFFICER",
    "LG": "OFFICER",
}


async def send_parade_state(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    personnel = list_personnel(DB_PATH)
    absences = list_absences_for_date(DB_PATH, date.today().isoformat())

    category_totals: dict[str, int] = {category: 0 for category in CATEGORIES}
    category_present: dict[str, int] = {category: 0 for category in CATEGORIES}
    for personnel_id, rank, _name in personnel:
        category = RANK_TO_CATEGORY.get(rank, "TROOPER")
        category_totals[category] += 1
        if personnel_id not in absences:
            category_present[category] += 1

    total_count = len(personnel)
    present_count = total_count - len(absences)

    lines: list[str] = []
    lines.append("SAT POOL")
    lines.append("")
    lines.append(date.today().strftime("%d%m%y"))
    lines.append("")
    lines.append(f"[QM PLT]: {present_count:02d}/{total_count:02d}")
    for category in CATEGORIES:
        if category_totals[category] == 0:
            continue
        lines.append(
            f"[{category}]: {category_present[category]:02d}/{category_totals[category]:02d}"
        )
    lines.append("")
    for personnel_id, rank, name in personnel:
        absence = absences.get(personnel_id)
        if absence is None:
            status = "In Camp"
        else:
            reason, start_text, end_text = absence
            start_date = date.fromisoformat(start_text)
            end_date = date.fromisoformat(end_text)
            status = reason
            if start_date != end_date:
                status = f"{reason} {format_date_range(start_date, end_date)}"
        lines.append(f"{rank} {name} ({status})")

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

    add_personnel(DB_PATH, rank, name)

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

    removed = remove_personnel(DB_PATH, rank, name)

    if removed:
        _ = await message.reply_text(f"Removed {rank} {name} from personnel.")
    else:
        _ = await message.reply_text(f"No personnel found for {rank} {name}.")


def parse_date_or_range(text: str) -> tuple[date, date] | None:
    parts = text.split("-")
    if len(parts) not in (1, 2):
        return None
    try:
        parsed = [datetime.strptime(part, "%d%m%y").date() for part in parts]
    except ValueError:
        return None
    return (parsed[0], parsed[-1])


def format_date_range(start_date: date, end_date: date) -> str:
    if start_date == end_date:
        return start_date.strftime("%d%m%y")
    return f"{start_date.strftime('%d%m%y')}-{end_date.strftime('%d%m%y')}"


async def absent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    assert message is not None

    args = context.args or []

    if len(args) < 3:
        _ = await message.reply_text(
            "Usage: /absent <rank> <name...> <DDMMYY[-DDMMYY]> <reason...>"
        )
        return

    rank = args[0].strip()
    date_index = None
    for index in range(1, len(args)):
        if parse_date_or_range(args[index]) is None:
            continue
        date_index = index
        break

    if date_index is None or date_index == 1 or date_index == len(args) - 1:
        _ = await message.reply_text(
            "Usage: /absent <rank> <name...> <DDMMYY[-DDMMYY]> <reason...>"
        )
        return

    name = " ".join(args[1:date_index]).strip()
    date_text = args[date_index].strip()
    reason = " ".join(args[date_index + 1 :]).strip()

    if not rank or not name or not date_text or not reason:
        _ = await message.reply_text(
            "Usage: /absent <rank> <name...> <DDMMYY[-DDMMYY]> <reason...>"
        )
        return

    date_range = parse_date_or_range(date_text)
    if date_range is None:
        _ = await message.reply_text("Date must be in DDMMYY or DDMMYY-DDMMYY format.")
        return

    start_date, end_date = date_range
    if end_date < start_date:
        _ = await message.reply_text("End date must not be before start date.")
        return

    day_count = (end_date - start_date).days + 1
    if day_count > 366:
        _ = await message.reply_text("Range too long - check the dates.")
        return

    personnel_id = get_personnel_id(DB_PATH, rank, name)
    if personnel_id is None:
        _ = await message.reply_text(f"No personnel found for {rank} {name}.")
        return

    add_absence(
        DB_PATH, personnel_id, start_date.isoformat(), end_date.isoformat(), reason
    )
    if start_date == end_date:
        _ = await message.reply_text(
            f"Marked {rank} {name} absent on {start_date.strftime('%d%m%y')}."
        )
    else:
        _ = await message.reply_text(
            f"Marked {rank} {name} absent from {start_date.strftime('%d%m%y')} "
            f"to {end_date.strftime('%d%m%y')} ({day_count} days)."
        )


def build_absence_list(
    personnel_id: int, rank: str, name: str
) -> tuple[str, InlineKeyboardMarkup | None]:
    rows = list_absences_for_personnel(
        DB_PATH, personnel_id, date.today().isoformat()
    )
    if not rows:
        return (f"No upcoming absences for {rank} {name}.", None)

    buttons = [
        [
            InlineKeyboardButton(
                f"❌ {format_date_range(date.fromisoformat(start_text), date.fromisoformat(end_text))} {reason}",
                callback_data=f"del:{personnel_id}:{absence_id}",
            )
        ]
        for absence_id, start_text, end_text, reason in rows
    ]
    return (
        f"{rank} {name} (tap an absence to delete it):",
        InlineKeyboardMarkup(buttons),
    )


async def absences_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    assert message is not None

    args = context.args or []

    if len(args) < 2:
        _ = await message.reply_text("Usage: /absences <rank> <name...>")
        return

    rank = args[0].strip()
    name = " ".join(args[1:]).strip()

    if not rank or not name:
        _ = await message.reply_text("Usage: /absences <rank> <name...>")
        return

    personnel_id = get_personnel_id(DB_PATH, rank, name)
    if personnel_id is None:
        _ = await message.reply_text(f"No personnel found for {rank} {name}.")
        return

    text, keyboard = build_absence_list(personnel_id, rank, name)
    _ = await message.reply_text(text, reply_markup=keyboard)


async def delete_absence_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    assert query is not None
    assert query.data is not None

    parts = query.data.split(":")
    if len(parts) != 3:
        await query.answer("This list is outdated, run /absences again.")
        return
    _, personnel_id_text, absence_id_text = parts
    try:
        personnel_id = int(personnel_id_text)
        absence_id = int(absence_id_text)
    except ValueError:
        await query.answer("This list is outdated, run /absences again.")
        return

    removed = remove_absence(DB_PATH, absence_id)
    if removed:
        await query.answer("Deleted absence.")
    else:
        await query.answer("Absence already deleted.")

    person = next(
        (row for row in list_personnel(DB_PATH) if row[0] == personnel_id), None
    )
    if person is None:
        _ = await query.edit_message_text("Personnel no longer exists.")
        return

    _, rank, name = person
    text, keyboard = build_absence_list(personnel_id, rank, name)
    _ = await query.edit_message_text(text, reply_markup=keyboard)


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
    save_job(DB_PATH, chat_id)
    _ = await context.bot.send_message(
        chat_id=chat_id,
        text="Parade state is scheduled at 8am",
    )


def load_jobs(job_queue):
    chat_ids = list_job_chat_ids(DB_PATH)
    for chat_id in chat_ids:
        schedule_job(chat_id, job_queue)


if __name__ == "__main__":
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    DB_PATH = os.getenv("DB_PATH", "bot.db")
    assert BOT_TOKEN, "No token in environment variables"

    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    init_db(DB_PATH)

    application = ApplicationBuilder().token(BOT_TOKEN).build()
    load_jobs(application.job_queue)

    start_handler = CommandHandler("start", start)
    send_handler = CommandHandler("send", send_parade_state_command)
    add_personnel_handler = CommandHandler("addpersonnel", add_personnel_command)
    remove_personnel_handler = CommandHandler(
        "removepersonnel", remove_personnel_command
    )
    absent_handler = CommandHandler("absent", absent_command)
    absences_handler = CommandHandler("absences", absences_command)
    delete_absence_handler = CallbackQueryHandler(
        delete_absence_callback, pattern=r"^del:"
    )

    application.add_handler(start_handler)
    application.add_handler(send_handler)
    application.add_handler(add_personnel_handler)
    application.add_handler(remove_personnel_handler)
    application.add_handler(absent_handler)
    application.add_handler(absences_handler)
    application.add_handler(delete_absence_handler)

    application.run_polling()

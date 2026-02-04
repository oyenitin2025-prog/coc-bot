import os
import json
import re
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =====================================
# ENV
# =====================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
DATA_FILE = "data.json"


# =====================================
# STORAGE
# =====================================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"accounts": {}}

    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# =====================================
# TIME PARSER (UNLIMITED FLEXIBLE)
# =====================================

def parse_time(text):
    """
    Accepts ANY format:
    2h
    30m
    1d
    5d16h
    10d22h
    14H53m
    1d2h30m
    1D 2H 30M
    """

    text = text.lower().replace(" ", "")

    days = hours = minutes = 0

    d = re.search(r"(\d+)d", text)
    h = re.search(r"(\d+)h", text)
    m = re.search(r"(\d+)m", text)

    if d:
        days = int(d.group(1))
    if h:
        hours = int(h.group(1))
    if m:
        minutes = int(m.group(1))

    return timedelta(days=days, hours=hours, minutes=minutes)


# =====================================
# KEYBOARDS
# =====================================

def home_keyboard(data):
    rows = []

    for name in data["accounts"]:
        rows.append([InlineKeyboardButton(name, callback_data=f"acc:{name}")])

    rows.append([InlineKeyboardButton("➕ Add Account", callback_data="add")])

    return InlineKeyboardMarkup(rows)


def section_keyboard(name):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧱 Builders", callback_data=f"builders:{name}")],
        [InlineKeyboardButton("🧪 Lab", callback_data=f"lab:{name}")],
        [InlineKeyboardButton("🐶 Pet House", callback_data=f"pet:{name}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="home")]
    ])


# =====================================
# COMMANDS
# =====================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()

    await update.message.reply_text(
        "🏰 Clash Builder Tracker\n\nSelect account:",
        reply_markup=home_keyboard(data)
    )


# =====================================
# BUTTON HANDLER
# =====================================

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = load_data()
    d = query.data

    if d == "home":
        await query.edit_message_text("Select account:", reply_markup=home_keyboard(data))

    elif d == "add":
        context.user_data["mode"] = "add"
        await query.edit_message_text("Send account name:")

    elif d.startswith("acc:"):
        name = d.split(":")[1]
        await query.edit_message_text(f"📌 {name}", reply_markup=section_keyboard(name))

    elif d.startswith("builders:"):
        name = d.split(":")[1]
        context.user_data = {"mode": "builders", "account": name}
        await query.edit_message_text(
            "Send 6 builder times separated by space.\n\nExample:\n2h 1d 5d16h 0 3h 45m"
        )

    elif d.startswith("lab:"):
        name = d.split(":")[1]
        context.user_data = {"mode": "lab", "account": name}
        await query.edit_message_text("Send lab time (example: 3d5h or 0)")

    elif d.startswith("pet:"):
        name = d.split(":")[1]
        context.user_data = {"mode": "pet", "account": name}
        await query.edit_message_text("Send pet time (example: 2d or 0)")


# =====================================
# TEXT HANDLER
# =====================================

async def text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    mode = context.user_data.get("mode")
    data = load_data()

    now = datetime.utcnow()

    # ADD ACCOUNT
    if mode == "add":
        data["accounts"][text] = {
            "builders": [None] * 6,
            "lab": None,
            "pet": None,
        }
        save_data(data)
        context.user_data.clear()

        await update.message.reply_text("✅ Added!\nUse /start")

    # BUILDERS
    elif mode == "builders":
        name = context.user_data["account"]
        parts = text.split()

        if len(parts) != 6:
            await update.message.reply_text("Please send exactly 6 times.")
            return

        times = []

        for p in parts:
            if p == "0":
                times.append(None)
                continue

            finish = now + parse_time(p)
            times.append(finish.isoformat())

            schedule(context, finish, f"🧱 Builder finished for {name}")

        data["accounts"][name]["builders"] = times
        save_data(data)
        context.user_data.clear()

        await update.message.reply_text("✅ Builders updated!")

    # LAB
    elif mode == "lab":
        name = context.user_data["account"]

        if text != "0":
            finish = now + parse_time(text)
            schedule(context, finish, f"🧪 Lab finished for {name}")
            data["accounts"][name]["lab"] = finish.isoformat()
        else:
            data["accounts"][name]["lab"] = None

        save_data(data)
        context.user_data.clear()

        await update.message.reply_text("✅ Lab updated!")

    # PET
    elif mode == "pet":
        name = context.user_data["account"]

        if text != "0":
            finish = now + parse_time(text)
            schedule(context, finish, f"🐶 Pet House finished for {name}")
            data["accounts"][name]["pet"] = finish.isoformat()
        else:
            data["accounts"][name]["pet"] = None

        save_data(data)
        context.user_data.clear()

        await update.message.reply_text("✅ Pet updated!")


# =====================================
# REMINDERS
# =====================================

def schedule(context, finish, message):
    seconds = (finish - datetime.utcnow()).total_seconds()

    context.job_queue.run_once(send_msg, seconds, data=message)

    if seconds > 3600:
        context.job_queue.run_once(send_msg, seconds - 3600, data=f"⏰ 1 hour left\n{message}")


async def send_msg(context):
    await context.bot.send_message(chat_id=CHAT_ID, text=context.job.data)


# =====================================
# MAIN (NO ASYNCIO BUGS)
# =====================================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_input))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()

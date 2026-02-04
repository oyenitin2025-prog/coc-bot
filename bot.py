import os
import json
import re
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

DATA_FILE = "data.json"


# =========================
# SAFE STORAGE (AUTO CREATE)
# =========================

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({"accounts": {}}, f)
        return {"accounts": {}}

    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


# =========================
# TIME PARSER
# =========================

def parse_time(t):
    t = t.lower()

    d = re.search(r"(\d+)d", t)
    h = re.search(r"(\d+)h", t)
    m = re.search(r"(\d+)m", t)

    return timedelta(
        days=int(d.group(1)) if d else 0,
        hours=int(h.group(1)) if h else 0,
        minutes=int(m.group(1)) if m else 0,
    )


# =========================
# KEYBOARDS
# =========================

def home_keyboard():
    data = load_data()

    buttons = [
        [InlineKeyboardButton(name, callback_data=f"acc:{name}")]
        for name in data["accounts"]
    ]

    buttons.append([InlineKeyboardButton("+ Add Account", callback_data="add")])

    return InlineKeyboardMarkup(buttons)


def menu_keyboard(name):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Builders", callback_data=f"builders:{name}")],
        [InlineKeyboardButton("Lab", callback_data=f"lab:{name}")],
        [InlineKeyboardButton("Pet House", callback_data=f"pet:{name}")],
        [InlineKeyboardButton("Back", callback_data="home")]
    ])


# =========================
# COMMANDS
# =========================

async def start(update, context):
    await update.message.reply_text(
        "Clash Builder Tracker\n\nSelect account:",
        reply_markup=home_keyboard()
    )


# =========================
# BUTTONS
# =========================

async def buttons(update, context):
    query = update.callback_query
    await query.answer()

    data = load_data()

    d = query.data

    if d == "home":
        await query.edit_message_text(
            "Select account:",
            reply_markup=home_keyboard()
        )

    elif d == "add":
        context.user_data["mode"] = "add"
        await query.edit_message_text("Send account name:")

    elif d.startswith("acc:"):
        name = d.split(":")[1]
        await query.edit_message_text(name, reply_markup=menu_keyboard(name))

    elif d.startswith("builders:"):
        name = d.split(":")[1]
        context.user_data = {"mode": "builders", "account": name}
        await query.edit_message_text("Send 6 builder times (example: 2h 1d 0 5h 3h 30m")

    elif d.startswith("lab:"):
        context.user_data = {"mode": "lab", "account": d.split(":")[1]}
        await query.edit_message_text("Send lab time or 0")

    elif d.startswith("pet:"):
        context.user_data = {"mode": "pet", "account": d.split(":")[1]}
        await query.edit_message_text("Send pet time or 0")


# =========================
# TEXT
# =========================

async def text(update, context):
    text = update.message.text
    mode = context.user_data.get("mode")
    data = load_data()

    now = datetime.utcnow()

    if mode == "add":
        data["accounts"][text] = {"builders": []}
        save_data(data)
        context.user_data.clear()
        await update.message.reply_text("Added!\n/start")

    elif mode == "builders":
        name = context.user_data["account"]
        parts = text.split()

        data["accounts"][name]["builders"] = [
            (now + parse_time(p)).isoformat() if p != "0" else None
            for p in parts
        ]

        save_data(data)
        context.user_data.clear()
        await update.message.reply_text("Builders saved!")


# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))

    print("RUNNING...")
    app.run_polling()


if __name__ == "__main__":
    main()

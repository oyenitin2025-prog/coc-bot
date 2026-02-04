import os
import json
import re
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ======================================================
# ENV
# ======================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

DATA_FILE = "data.json"


# ======================================================
# STORAGE (AUTO CREATE SAFE)
# ======================================================

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({"accounts": {}}, f)

    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ======================================================
# TIME PARSER (UNLIMITED FORMAT)
# ======================================================

def parse_time(text: str) -> timedelta:
    """
    Works for:
    2h
    30m
    1d
    5d16h
    10d22h
    1d2h30m
    """

    text = text.lower().replace(" ", "")

    d = re.search(r"(\d+)d", text)
    h = re.search(r"(\d+)h", text)
    m = re.search(r"(\d+)m", text)

    return timedelta(
        days=int(d.group(1)) if d else 0,
        hours=int(h.group(1)) if h else 0,
        minutes=int(m.group(1)) if m else 0,
    )


# ======================================================
# REMINDERS
# ======================================================

async def send_message(context):
    await context.bot.send_message(chat_id=CHAT_ID, text=context.job.data)


def schedule(context, finish_time, text):
    seconds = (finish_time - datetime.utcnow()).total_seconds()

    if seconds <= 0:
        return

    # finish reminder
    context.job_queue.run_once(send_message, seconds, data=text)

    # 1 hour reminder
    if seconds > 3600:
        context.job_queue.run_once(
            send_message,
            seconds - 3600,
            data=f"⏰ 1 hour left\n{text}",
        )


# ======================================================
# KEYBOARDS
# ======================================================

def home_keyboard():
    data = load_data()

    rows = []

    for name in data["accounts"]:
        rows.append([InlineKeyboardButton(f"🏰 {name}", callback_data=f"acc:{name}")])

    rows.append([InlineKeyboardButton("➕ Add Account", callback_data="add")])

    return InlineKeyboardMarkup(rows)


def menu_keyboard(name):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧱 Builders", callback_data=f"builders:{name}")],
        [InlineKeyboardButton("🧪 Lab", callback_data=f"lab:{name}")],
        [InlineKeyboardButton("🐶 Pet House", callback_data=f"pet:{name}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="home")],
    ])


# ======================================================
# COMMANDS
# ======================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏰 *Clash Builder Tracker*\n\nSelect account:",
        reply_markup=home_keyboard(),
        parse_mode="Markdown"
    )


# ======================================================
# BUTTON HANDLER
# ======================================================

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = load_data()
    action = query.data

    # HOME
    if action == "home":
        await query.edit_message_text("🏰 Select account:", reply_markup=home_keyboard())

    # ADD ACCOUNT
    elif action == "add":
        context.user_data["mode"] = "add"
        await query.edit_message_text("✏️ Send account name")

    # ACCOUNT MENU
    elif action.startswith("acc:"):
        name = action.split(":")[1]
        await query.edit_message_text(
            f"📌 *{name}*",
            reply_markup=menu_keyboard(name),
            parse_mode="Markdown"
        )

    # BUILDERS
    elif action.startswith("builders:"):
        name = action.split(":")[1]
        context.user_data = {"mode": "builders", "account": name}

        await query.edit_message_text(
            "🧱 Send 6 builder times\n\nExample:\n2h 1d 0 5h 3h 45m"
        )

    # LAB
    elif action.startswith("lab:"):
        name = action.split(":")[1]
        context.user_data = {"mode": "lab", "account": name}
        await query.edit_message_text("🧪 Send lab time or 0")

    # PET
    elif action.startswith("pet:"):
        name = action.split(":")[1]
        context.user_data = {"mode": "pet", "account": name}
        await query.edit_message_text("🐶 Send pet time or 0")


# ======================================================
# TEXT HANDLER
# ======================================================

async def text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.strip()
    mode = context.user_data.get("mode")
    data = load_data()
    now = datetime.utcnow()

    # ADD ACCOUNT
    if mode == "add":
        data["accounts"][msg] = {"builders": [], "lab": None, "pet": None}
        save_data(data)
        context.user_data.clear()

        await update.message.reply_text("✅ Account added!\nUse /start")

    # BUILDERS
    elif mode == "builders":
        name = context.user_data["account"]

        parts = msg.split()
        if len(parts) != 6:
            await update.message.reply_text("❌ Please send exactly 6 times")
            return

        finishes = []

        for p in parts:
            if p == "0":
                finishes.append(None)
                continue

            finish = now + parse_time(p)
            finishes.append(finish.isoformat())
            schedule(context, finish, f"🧱 Builder finished for {name}")

        data["accounts"][name]["builders"] = finishes
        save_data(data)
        context.user_data.clear()

        await update.message.reply_text("✅ Builders saved!")

    # LAB
    elif mode == "lab":
        name = context.user_data["account"]

        if msg != "0":
            finish = now + parse_time(msg)
            schedule(context, finish, f"🧪 Lab finished for {name}")
            data["accounts"][name]["lab"] = finish.isoformat()

        save_data(data)
        context.user_data.clear()

        await update.message.reply_text("✅ Lab saved!")

    # PET
    elif mode == "pet":
        name = context.user_data["account"]

        if msg != "0":
            finish = now + parse_time(msg)
            schedule(context, finish, f"🐶 Pet House finished for {name}")
            data["accounts"][name]["pet"] = finish.isoformat()

        save_data(data)
        context.user_data.clear()

        await update.message.reply_text("✅ Pet saved!")


# ======================================================
# MAIN
# ======================================================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))

    print("🚀 Bot running...")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

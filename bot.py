import os
import json
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
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================
# CONFIG
# =========================

DATA_FILE = "data.json"
CHAT_ID = os.getenv("CHAT_ID")


# =========================
# STORAGE
# =========================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"accounts": {}}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# =========================
# HELPERS
# =========================

def parse_time(text):
    """
    user types:
    2h
    3h30m
    45m
    """
    hours = 0
    minutes = 0

    if "h" in text:
        hours = int(text.split("h")[0])

    if "m" in text:
        minutes = int(text.split("m")[0].split("h")[-1])

    return timedelta(hours=hours, minutes=minutes)


def account_keyboard(data):
    buttons = []

    for name in data["accounts"]:
        buttons.append(
            [InlineKeyboardButton(name, callback_data=f"acc:{name}")]
        )

    buttons.append([InlineKeyboardButton("➕ Add Account", callback_data="add")])

    return InlineKeyboardMarkup(buttons)


def section_keyboard(name):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧱 Builders", callback_data=f"builders:{name}")],
        [InlineKeyboardButton("🧪 Lab", callback_data=f"lab:{name}")],
        [InlineKeyboardButton("🐶 Pet House", callback_data=f"pet:{name}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="home")]
    ])


# =========================
# COMMANDS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()

    await update.message.reply_text(
        "🏰 Clash Tracker Bot\n\nSelect account:",
        reply_markup=account_keyboard(data)
    )


# =========================
# CALLBACK HANDLER
# =========================

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = load_data()
    d = query.data

    # home
    if d == "home":
        await query.edit_message_text(
            "Select account:",
            reply_markup=account_keyboard(data)
        )

    # add account
    elif d == "add":
        context.user_data["mode"] = "add_account"
        await query.edit_message_text("Send account name:")

    # open account
    elif d.startswith("acc:"):
        name = d.split(":")[1]

        await query.edit_message_text(
            f"📌 {name}",
            reply_markup=section_keyboard(name)
        )

    # builders
    elif d.startswith("builders:"):
        name = d.split(":")[1]

        context.user_data["mode"] = "builder_time"
        context.user_data["account"] = name

        await query.edit_message_text(
            "Send builder times for 6 builders.\n\nExample:\n2h 1h 30m 0 5h 3h"
        )

    # lab
    elif d.startswith("lab:"):
        name = d.split(":")[1]

        context.user_data["mode"] = "lab_time"
        context.user_data["account"] = name

        await query.edit_message_text("Send lab time (example: 3h30m or 0)")

    # pet
    elif d.startswith("pet:"):
        name = d.split(":")[1]

        context.user_data["mode"] = "pet_time"
        context.user_data["account"] = name

        await query.edit_message_text("Send pet house time (example: 2h or 0)")


# =========================
# TEXT INPUT HANDLER
# =========================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    mode = context.user_data.get("mode")

    data = load_data()

    # =====================
    # ADD ACCOUNT
    # =====================
    if mode == "add_account":
        name = text

        data["accounts"][name] = {
            "builders": [None] * 6,
            "lab": None,
            "pet": None
        }

        save_data(data)
        context.user_data.clear()

        await update.message.reply_text("✅ Added!\n/start")

    # =====================
    # BUILDERS
    # =====================
    elif mode == "builder_time":
        name = context.user_data["account"]
        parts = text.split()

        times = []

        now = datetime.utcnow()

        for p in parts:
            if p == "0":
                times.append(None)
            else:
                finish = now + parse_time(p)
                times.append(finish.isoformat())

                schedule_reminder(context, finish, f"🧱 Builder finished for {name}")

        data["accounts"][name]["builders"] = times
        save_data(data)

        context.user_data.clear()

        await update.message.reply_text("✅ Builders updated!")

    # =====================
    # LAB
    # =====================
    elif mode == "lab_time":
        name = context.user_data["account"]

        if text == "0":
            data["accounts"][name]["lab"] = None
        else:
            finish = datetime.utcnow() + parse_time(text)
            data["accounts"][name]["lab"] = finish.isoformat()

            schedule_reminder(context, finish, f"🧪 Lab finished for {name}")

        save_data(data)
        context.user_data.clear()

        await update.message.reply_text("✅ Lab updated!")

    # =====================
    # PET
    # =====================
    elif mode == "pet_time":
        name = context.user_data["account"]

        if text == "0":
            data["accounts"][name]["pet"] = None
        else:
            finish = datetime.utcnow() + parse_time(text)
            data["accounts"][name]["pet"] = finish.isoformat()

            schedule_reminder(context, finish, f"🐶 Pet House finished for {name}")

        save_data(data)
        context.user_data.clear()

        await update.message.reply_text("✅ Pet updated!")


# =========================
# REMINDER SYSTEM
# =========================

def schedule_reminder(context, finish_time, message):
    seconds = (finish_time - datetime.utcnow()).total_seconds()

    if seconds <= 0:
        return

    context.job_queue.run_once(send_message, seconds, data=message)

    # 1 hour reminder
    if seconds > 3600:
        context.job_queue.run_once(send_message, seconds - 3600, data=f"⏰ 1 hour left\n{message}")


async def send_message(context):
    await context.bot.send_message(chat_id=CHAT_ID, text=context.job.data)


# =========================
# MAIN (NO ASYNCIO BUGS)
# =========================

def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()

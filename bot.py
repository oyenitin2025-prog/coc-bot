# ===============================
# Clash Builder Tracker – FINAL
# ===============================

import os
import json
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from apscheduler.schedulers.asyncio import AsyncIOScheduler


DATA_FILE = "data.json"
CHAT_ID = os.getenv("CHAT_ID")


# =====================================
# STORAGE
# =====================================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


# =====================================
# HELPERS
# =====================================

def parse_duration(text):
    total = timedelta()
    num = ""
    for c in text:
        if c.isdigit():
            num += c
        else:
            if c == "d":
                total += timedelta(days=int(num))
            elif c == "h":
                total += timedelta(hours=int(num))
            elif c == "m":
                total += timedelta(minutes=int(num))
            num = ""
    return total


def now():
    return datetime.utcnow()


def make_timer(finish):
    return {"finish": finish.isoformat(), "reminded": False}


def format_remaining(finish):
    diff = datetime.fromisoformat(finish) - now()
    if diff.total_seconds() <= 0:
        return "done"
    h = int(diff.total_seconds() // 3600)
    m = int((diff.total_seconds() % 3600) // 60)
    return f"{h}h {m}m"


# =====================================
# MENUS
# =====================================

async def main_menu(update_or_query):
    data = load_data()
    rows = [[InlineKeyboardButton(acc, callback_data=f"acc_{acc}")] for acc in data]
    rows.append([InlineKeyboardButton("➕ Add Account", callback_data="addacc")])

    markup = InlineKeyboardMarkup(rows)

    if isinstance(update_or_query, Update):
        await update_or_query.message.reply_text("🏰 Select account", reply_markup=markup)
    else:
        await update_or_query.edit_message_text("🏰 Select account", reply_markup=markup)


async def account_menu(query, acc):
    buttons = [
        [InlineKeyboardButton("🧱 Builders", callback_data=f"builders_{acc}")],
        [InlineKeyboardButton("🧪 Lab", callback_data=f"lab_{acc}")],
        [InlineKeyboardButton("🐾 Pet", callback_data=f"pet_{acc}")],
        [InlineKeyboardButton("📊 Status", callback_data=f"status_{acc}")],
        [InlineKeyboardButton("⬅ Back", callback_data="back")]
    ]

    await query.edit_message_text(f"🏰 {acc}", reply_markup=InlineKeyboardMarkup(buttons))


# =====================================
# STATUS VIEW
# =====================================

async def show_status(query, acc):
    data = load_data()[acc]
    text = f"🏰 {acc}\n\n"

    # Builders
    free = 7 - len(data["builders"])
    text += f"🧱 Builders\nFree: {free}\n"
    for b in data["builders"]:
        text += f"• {format_remaining(b['finish'])}\n"

    # Lab
    text += "\n🧪 Lab\n"
    if data["lab"]:
        text += f"• {format_remaining(data['lab']['finish'])}\n"
    else:
        text += "• Free\n"

    # Pet
    text += "\n🐾 Pet\n"
    if data["pet"]:
        text += f"• {format_remaining(data['pet']['finish'])}\n"
    else:
        text += "• Free\n"

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅ Back", callback_data=f"acc_{acc}")]
    ]))


# =====================================
# START
# =====================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await main_menu(update)


# =====================================
# BUTTON HANDLER
# =====================================

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    payload = query.data
    data = load_data()

    if payload == "back":
        await main_menu(query)
        return

    if payload == "addacc":
        context.user_data["state"] = "add_account"
        await query.edit_message_text("Send account name:")
        return

    if payload.startswith("acc_"):
        acc = payload.split("_", 1)[1]
        context.user_data["acc"] = acc
        await account_menu(query, acc)
        return

    # STATUS
    if payload.startswith("status_"):
        acc = payload.split("_", 1)[1]
        await show_status(query, acc)
        return

    # BUILDERS
    if payload.startswith("builders_"):
        acc = payload.split("_", 1)[1]
        context.user_data["acc"] = acc

        row = [InlineKeyboardButton(str(i), callback_data=f"busy_{i}") for i in range(7)]
        await query.edit_message_text("Busy builders?", reply_markup=InlineKeyboardMarkup([row]))
        return

    if payload.startswith("busy_"):
        context.user_data["busy"] = int(payload.split("_")[1])
        context.user_data["state"] = "builder_time"
        await query.edit_message_text("Enter time (2d6h):")
        return

    # LAB
    if payload.startswith("lab_"):
        context.user_data["acc"] = payload.split("_", 1)[1]
        context.user_data["state"] = "lab_time"
        await query.edit_message_text("Enter lab time:")
        return

    # PET
    if payload.startswith("pet_"):
        context.user_data["acc"] = payload.split("_", 1)[1]
        context.user_data["state"] = "pet_time"
        await query.edit_message_text("Enter pet time:")
        return


# =====================================
# TEXT INPUT
# =====================================

async def text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    state = context.user_data.get("state")
    data = load_data()

    if state == "add_account":
        data[msg] = {"builders": [], "lab": None, "pet": None}
        save_data(data)
        context.user_data["state"] = None
        await update.message.reply_text("✅ Added")
        await main_menu(update)
        return

    acc = context.user_data.get("acc")
    finish = now() + parse_duration(msg)

    if state == "builder_time":
        for _ in range(context.user_data["busy"]):
            data[acc]["builders"].append(make_timer(finish))

    elif state == "lab_time":
        data[acc]["lab"] = make_timer(finish)

    elif state == "pet_time":
        data[acc]["pet"] = make_timer(finish)

    save_data(data)
    context.user_data["state"] = None
    await update.message.reply_text("⏳ Timer set!")
    await main_menu(update)


# =====================================
# SCHEDULER
# =====================================

async def check_jobs(app):
    data = load_data()
    n = now()

    for acc in data:

        for t in data[acc]["builders"][:]:
            finish = datetime.fromisoformat(t["finish"])
            remaining = finish - n

            if remaining <= timedelta(hours=1) and not t["reminded"] and remaining.total_seconds() > 0:
                await app.bot.send_message(CHAT_ID, f"⏰ {acc} – Builder 1h left")
                t["reminded"] = True

            if n >= finish:
                await app.bot.send_message(CHAT_ID, f"🔥 {acc} – Builder free")
                data[acc]["builders"].remove(t)

        for key, label in [("lab", "Lab"), ("pet", "Pet")]:
            t = data[acc][key]
            if not t:
                continue

            finish = datetime.fromisoformat(t["finish"])
            remaining = finish - n

            if remaining <= timedelta(hours=1) and not t["reminded"] and remaining.total_seconds() > 0:
                await app.bot.send_message(CHAT_ID, f"⏰ {acc} – {label} 1h left")
                t["reminded"] = True

            if n >= finish:
                await app.bot.send_message(CHAT_ID, f"🔥 {acc} – {label} done")
                data[acc][key] = None

    save_data(data)


# =====================================
# MAIN
# =====================================

async def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_input))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: app.create_task(check_jobs(app)), "interval", seconds=60)
    scheduler.start()

    await app.run_polling()


import asyncio
asyncio.run(main())

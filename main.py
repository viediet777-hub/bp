"""
main.py - Bot + Mini App Backend - Sab ek hi script se
"""
import logging
import os
import threading

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, MessageHandler, filters,
)

from config import BOT_TOKEN, ADMIN_IDS
from database import get_user, create_user, get_all_orders
from app import app as flask_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("bot")


def is_admin(uid):
    return uid in ADMIN_IDS


# ═══════════════════════════════════════════════════════════════
# START - Mini App Button
# ═══════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid) or create_user(uid, update.effective_user.first_name)
    wallet = user.get("wallet", 0)

    WEBAPP_URL = os.environ.get("WEBAPP_URL", "http://localhost:5000")
    https = WEBAPP_URL.startswith("https://")

    text = (
        f"🛍️ <b>WELCOME TO SHOP</b>\n"
        f"{'━'*26}\n\n"
        f"💰 Wallet: <b>₹{wallet}</b>\n\n"
        f"👇 Mini App kholo ya neeche buttons dabao"
    )
    if https:
        rows = [
            [InlineKeyboardButton("🛍️ Open Shop", web_app=WebAppInfo(url=WEBAPP_URL))],
            [InlineKeyboardButton("🛒 My Cart", callback_data="cart"),
             InlineKeyboardButton("📦 My Orders", callback_data="orders")],
            [InlineKeyboardButton("👤 My Account", callback_data="account"),
             InlineKeyboardButton("💰 Add Wallet", callback_data="wallet")],
        ]
    else:
        rows = [
            [InlineKeyboardButton("🛒 My Cart", callback_data="cart"),
             InlineKeyboardButton("📦 My Orders", callback_data="orders")],
            [InlineKeyboardButton("👤 My Account", callback_data="account"),
             InlineKeyboardButton("💰 Add Wallet", callback_data="wallet")],
        ]
        text += "\n\n⚠️ <i>Mini App needs HTTPS URL. Set WEBAPP_URL env var.</i>"
    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(rows))


# ═══════════════════════════════════════════════════════════════
# CALLBACK - Bot buttons
# ═══════════════════════════════════════════════════════════════

async def cb_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    user = get_user(uid) or create_user(uid, q.from_user.first_name)
    d = q.data
    WEBAPP_URL = os.environ.get("WEBAPP_URL", "http://localhost:5000")
    https = WEBAPP_URL.startswith("https://")

    if d == "back":
        msg = f"🛍️ <b>SHOP</b>\n💰 Wallet: ₹{user.get('wallet',0)}\n\n👇 Mini App kholo:"
        btns = [[InlineKeyboardButton("🛍️ Open Shop", web_app=WebAppInfo(url=WEBAPP_URL))]] if https else []
        await q.edit_message_text(msg, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(btns))

    elif d == "cart":
        if https:
            btns = [[InlineKeyboardButton("🛒 Open Cart", web_app=WebAppInfo(url=WEBAPP_URL + "#cart"))]]
        else:
            btns = []
        btns.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])
        await q.edit_message_text("🛒 <b>My Cart</b>\n\nMini App mein dekho:",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btns))

    elif d == "orders":
        if https:
            btns = [[InlineKeyboardButton("📦 Open Orders", web_app=WebAppInfo(url=WEBAPP_URL + "#orders"))]]
        else:
            btns = []
        btns.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])
        await q.edit_message_text("📦 <b>My Orders</b>\n\nMini App mein dekho:",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btns))

    elif d == "account":
        if https:
            btns = [[InlineKeyboardButton("👤 Open Account", web_app=WebAppInfo(url=WEBAPP_URL + "#account"))]]
        else:
            btns = []
        btns.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])
        await q.edit_message_text("👤 <b>My Account</b>\n\nMini App mein dekho:",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btns))

    elif d == "wallet":
        if https:
            btns = [[InlineKeyboardButton("💰 Open Wallet", web_app=WebAppInfo(url=WEBAPP_URL + "#wallet"))]]
        else:
            btns = []
        btns.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])
        await q.edit_message_text("💰 <b>Add Wallet</b>\n\nMini App mein karo:",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btns))

    await q.answer()


# ═══════════════════════════════════════════════════════════════
# ADMIN COMMANDS
# ═══════════════════════════════════════════════════════════════

async def cmd_addproduct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    context.user_data["wait_prod"] = True
    await update.message.reply_text(
        "📦 <b>Product add karo:</b>\n\nFormat: name | price | stock | category\n\nExample:\nT-Shirt | 299 | 50 | clothing",
        parse_mode=ParseMode.HTML)


async def cmd_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    orders = get_all_orders()
    if not orders:
        await update.message.reply_text("📭 Koi orders nahi!")
        return
    text = f"📦 <b>ALL ORDERS ({len(orders)}):</b>\n\n"
    for o in orders[:20]:
        st = {"pending": "⏳", "confirmed": "✅", "delivered": "📦"}.get(o["status"], "❓")
        text += f"#{o['id']} | 👤{o['user_id']} | 💰₹{o['total']} | {st}\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def msg_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    text = update.message.text

    if context.user_data.get("wait_prod"):
        context.user_data["wait_prod"] = False
        parts = [p.strip() for p in text.split("|")]
        if len(parts) >= 2:
            from database import add_product
            name = parts[0]
            price = int(parts[1])
            stock = int(parts[2]) if len(parts) > 2 else 10
            cat = parts[3] if len(parts) > 3 else ""
            pid = add_product(name, price, stock, category=cat)
            await update.message.reply_text(f"✅ Product added! ID: {pid}")
        else:
            await update.message.reply_text("❌ Format: name | price | stock | category")


# ═══════════════════════════════════════════════════════════════
# START FLASK IN BACKGROUND
# ═══════════════════════════════════════════════════════════════

def run_flask():
    flask_app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print("Starting Bot + Mini App...")
    print(f"Admin: {ADMIN_IDS}")

    # Flask background
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("Flask running on port 5000")

    # Telegram Bot
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("addproduct", cmd_addproduct))
    app.add_handler(CommandHandler("orders", cmd_orders))
    app.add_handler(CallbackQueryHandler(cb_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_router))

    print("Bot running!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

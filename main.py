"""
main.py - Bot + Mini App Backend - Sab ek hi script se
Bot = standalone (wallet, offer, account, orders, export, refresh)
Mini App = shopping UI
"""
import json
import logging
import os
import threading
import time
import urllib.parse

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo,
    InputMediaPhoto,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, MessageHandler, filters,
)

from config import BOT_TOKEN, ADMIN_IDS, GW_UPI_ID, GW_UPI_NAME, WALLET_MIN, WALLET_MAX
from database import (
    get_user, create_user, get_all_orders, add_wallet,
    get_wallet_tx, create_wallet_tx,
    get_meesho_accounts, get_active_meesho_account, save_meesho_account,
    delete_meesho_account, get_user_offer, save_user_offer,
    get_orders, get_cart,
)
from gateway import generate_txn_id, create_upi_link, get_qr_url, verify_payment
from meesho import get_meesho_offer, send_otp, verify_otp, check_number

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("bot")


def is_admin(uid):
    return uid in ADMIN_IDS


def fmt_price(p):
    try:
        return f"Rs.{int(float(p))}"
    except Exception:
        return f"Rs.{p}"


# ═══════════════════════════════════════════════════════════════
# START
# ═══════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid) or create_user(uid, update.effective_user.first_name)
    wallet = user.get("wallet", 0)
    accs = get_meesho_accounts(uid)
    offer = get_user_offer(uid)

    offer_text = ""
    if offer:
        offer_text = f"\n优惠: {offer.get('title','')} {offer.get('text','')}"
    else:
        offer_text = "\n优惠: Koi offer nahi. Roll karo!"

    acc_text = f"\n📦 Accounts: {len(accs)}" if accs else "\n📦 Accounts: 0 (Add karo)"

    text = (
        f"🛍️ *SHOP*\n"
        f"{'━'*26}\n\n"
        f"💰 Wallet: *{fmt_price(wallet)}*\n"
        f"{acc_text}{offer_text}\n\n"
        f"Neeche buttons se sab karo:"
    )

    rows = [
        [InlineKeyboardButton("🎯 Roll Offer", callback_data="offer_roll"),
         InlineKeyboardButton("💰 Add Wallet", callback_data="wallet_add")],
        [InlineKeyboardButton("📦 My Orders", callback_data="orders"),
         InlineKeyboardButton("👤 My Account", callback_data="account_menu")],
        [InlineKeyboardButton("💳 Wallet History", callback_data="wallet_history")],
    ]

    WEBAPP_URL = os.environ.get("WEBAPP_URL", "")
    if WEBAPP_URL.startswith("https://"):
        rows.insert(0, [InlineKeyboardButton("🛍️ Open Shop", web_app=WebAppInfo(url=WEBAPP_URL))])

    if is_admin(uid):
        rows.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])

    await update.message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(rows))


# ═══════════════════════════════════════════════════════════════
# OFFER FLOW
# ═══════════════════════════════════════════════════════════════

async def cb_offer_roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer("🔄 Rolling best offer...")
    await q.edit_message_text("🔄 *Best offer roll ho raha hai...*\nThoda wait karo ⏳", parse_mode=ParseMode.MARKDOWN)

    result = get_meesho_offer()
    if result.get("ok") and result.get("offer"):
        offer = result["offer"]
        save_user_offer(uid, json.dumps(offer))
        buck = offer.get("bucket", 0)
        title = offer.get("title", "OFFER")
        text = offer.get("text", "")
        subtitle = offer.get("subtitle", "")

        msg = (
            f"🎯 *Best Offer Mil Gaya!*\n\n"
            f"🏷️ *{title}* {text}\n"
            f"📝 {subtitle}\n"
            f"💰 Upto *{fmt_price(buck)}* OFF\n\n"
            f"Ye offer ab apply hoga sab products pe!"
        )
        btns = [
            [InlineKeyboardButton("🔄 Roll Again", callback_data="offer_roll")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back")],
        ]
        await q.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(btns))
    else:
        await q.edit_message_text(
            "❌ Offer load nahi ho paya. Dobara try karo.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Retry", callback_data="offer_roll")],
                [InlineKeyboardButton("⬅️ Back", callback_data="back")],
            ]))


# ═══════════════════════════════════════════════════════════════
# WALLET FLOW - Bot pe hi
# ═══════════════════════════════════════════════════════════════

async def cb_wallet_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    user = get_user(uid) or {}
    wallet = user.get("wallet", 0)

    msg = (
        f"💰 *Add Money to Wallet*\n\n"
        f"Current Balance: *{fmt_price(wallet)}*\n\n"
        f"Kitna amount add karna hai?\n"
        f"Minimum: {fmt_price(WALLET_MIN)}, Maximum: {fmt_price(WALLET_MAX)}\n\n"
        f"Neeche amount select karo ya custom likho:"
    )
    btns = [
        [InlineKeyboardButton("Rs.5", callback_data="wamt_5"),
         InlineKeyboardButton("Rs.10", callback_data="wamt_10"),
         InlineKeyboardButton("Rs.25", callback_data="wamt_25")],
        [InlineKeyboardButton("Rs.50", callback_data="wamt_50"),
         InlineKeyboardButton("Rs.100", callback_data="wamt_100"),
         InlineKeyboardButton("Rs.200", callback_data="wamt_200")],
        [InlineKeyboardButton("✍️ Custom Amount", callback_data="wamt_custom")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")],
    ]
    await q.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(btns))


async def cb_wallet_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    d = q.data

    if d == "wamt_custom":
        context.user_data["wait_wamt"] = True
        await q.edit_message_text("✍️ *Amount likho:*\n\nExample: 50", parse_mode=ParseMode.MARKDOWN)
        await q.answer()
        return

    amount = int(d.replace("wamt_", ""))
    await _create_wallet_payment(q, uid, amount)


async def _create_wallet_payment(q, uid, amount):
    if amount < WALLET_MIN or amount > WALLET_MAX:
        await q.edit_message_text(f"❌ Amount {fmt_price(WALLET_MIN)}-{fmt_price(WALLET_MAX)} hona chahiye.")
        return

    await q.answer("⏳ Creating payment...")
    txn_id = generate_txn_id(uid)
    upi_link = create_upi_link(txn_id, amount)
    qr_url = get_qr_url(upi_link)
    create_wallet_tx(uid, amount, txn_id)

    msg = (
        f"💳 *Payment Karo*\n\n"
        f"Amount: *{fmt_price(amount)}*\n"
        f"UPI ID: `{GW_UPI_ID}`\n\n"
        f"QR scan karo ya UPI ID pay karo.\n"
        f"Payment ke baad 'I Paid' dabao."
    )
    btns = [
        [InlineKeyboardButton("✅ I Paid - Verify", callback_data=f"wverify_{txn_id}_{amount}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="back")],
    ]
    await q.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(btns))

    try:
        await q.message.reply_photo(photo=qr_url,
            caption=f"📱 *QR Code*\n{fmt_price(amount)} payment ke liye",
            parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await q.message.reply_text(f"🔗 QR Link: {qr_url}")


async def cb_wallet_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    d = q.data

    parts = d.replace("wverify_", "").split("_")
    txn_id = parts[0] if parts else ""
    amount = int(parts[1]) if len(parts) > 1 else 0

    await q.answer("🔍 Verifying payment...")
    result = verify_payment(txn_id)
    status = str(result.get("status", "")).lower()

    if result["success"] and status in ("success", "completed", "captured", "paid", "1"):
        from database import get_db
        conn = get_db()
        row = conn.execute("SELECT * FROM wallet_tx WHERE txn_id=? AND status='pending'", (txn_id,)).fetchone()
        if row:
            conn.execute("UPDATE wallet_tx SET status='completed' WHERE id=?", (row["id"],))
            conn.execute("UPDATE users SET wallet=wallet+? WHERE user_id=?", (row["amount"], row["user_id"]))
            conn.commit()
        conn.close()

        user = get_user(uid) or {}
        wallet = user.get("wallet", 0)
        await q.edit_message_text(
            f"✅ *Payment Verified!*\n\n"
            f"Rs.{amount} wallet mein add ho gaya!\n"
            f"💰 Total Balance: *{fmt_price(wallet)}*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="back")]]))
    else:
        btns = [
            [InlineKeyboardButton("🔄 Check Again", callback_data=f"wverify_{txn_id}_{amount}")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back")],
        ]
        await q.edit_message_text(
            "⏳ *Payment abhi verify nahi hua.*\n\nThoda wait karo ya dobara check karo.\nPayment send ho gaya hai?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(btns))


async def cb_wallet_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    user = get_user(uid) or {}
    wallet = user.get("wallet", 0)
    txs = get_wallet_tx(uid)

    msg = f"💳 *Wallet History*\n\n💰 Balance: *{fmt_price(wallet)}*\n\n"
    if not txs:
        msg += "Koi transaction nahi."
    else:
        for t in txs[:10]:
            st = "✅" if t.get("status") == "completed" else "⏳"
            msg += f"{st} {fmt_price(t.get('amount',0))} - {t.get('status','?')}\n"

    await q.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="back")]]))


# ═══════════════════════════════════════════════════════════════
# ACCOUNT FLOW - Bot pe hi
# ═══════════════════════════════════════════════════════════════

async def cb_account_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    accs = get_meesho_accounts(uid)

    msg = f"👤 *My Account*\n\n📦 Meesho Accounts: *{len(accs)}*\n"
    btns = []
    if accs:
        for i, a in enumerate(accs[:5]):
            phone = a.get("phone", "?")
            btns.append([InlineKeyboardButton(f"📱 {phone}", callback_data=f"acc_view_{a['id']}")])
    btns.append([InlineKeyboardButton("➕ Add New Account", callback_data="acc_add")])
    btns.append([InlineKeyboardButton("🔄 Refresh Session", callback_data="acc_refresh")])
    btns.append([InlineKeyboardButton("📤 Export Data", callback_data="acc_export")])
    btns.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])
    await q.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(btns))


async def cb_acc_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    context.user_data["wait_acc_phone"] = True
    await q.edit_message_text(
        "📱 *Meesho Account Add Karo*\n\nApna Meesho phone number likho:\n(10 digit)",
        parse_mode=ParseMode.MARKDOWN)
    await q.answer()


async def cb_acc_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    d = q.data
    acc_id = int(d.replace("acc_view_", ""))
    accs = get_meesho_accounts(uid)
    acc = None
    for a in accs:
        if a["id"] == acc_id:
            acc = a
            break
    if not acc:
        await q.edit_message_text("Account nahi mila.")
        return

    from datetime import datetime
    exp = acc.get("xo_exp", 0)
    exp_text = datetime.fromtimestamp(exp).strftime("%d %b %Y %H:%M") if exp else "Unknown"

    msg = (
        f"📱 *Account Details*\n\n"
        f"📞 Phone: `{acc.get('phone','?')}`\n"
        f"🆔 User ID: `{acc.get('meesho_user_id','?')}`\n"
        f"⏰ Session Expiry: {exp_text}\n"
    )

    is_expired = exp and exp < time.time()
    if is_expired:
        msg += "\n⚠️ *Session EXPIRED!* Refresh karo."

    btns = []
    if is_expired:
        btns.append([InlineKeyboardButton("🔄 Refresh Session", callback_data="acc_refresh")])
    btns.append([InlineKeyboardButton("🗑️ Delete Account", callback_data=f"acc_del_{acc_id}")])
    btns.append([InlineKeyboardButton("⬅️ Back", callback_data="account_menu")])
    await q.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(btns))


async def cb_acc_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    acc_id = int(q.data.replace("acc_del_", ""))
    delete_meesho_account(uid, acc_id)
    await q.edit_message_text("✅ Account delete ho gaya.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="account_menu")]]))


async def cb_acc_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer("🔄 Refreshing session...")
    result = get_meesho_offer()
    if result.get("ok") and result.get("offer"):
        offer = result["offer"]
        save_user_offer(uid, json.dumps(offer))
        await q.edit_message_text(
            f"✅ *Session Refreshed!*\n\n🎯 Offer: {offer.get('title','')} {offer.get('text','')}\n"
            f"💰 Upto *{fmt_price(offer.get('bucket',0))}* OFF",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="account_menu")]]))
    else:
        await q.edit_message_text("❌ Refresh failed. Dobara try karo.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Retry", callback_data="acc_refresh")],
                [InlineKeyboardButton("⬅️ Back", callback_data="account_menu")]]))


async def cb_acc_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    user = get_user(uid) or {}
    accs = get_meesho_accounts(uid)
    offer = get_user_offer(uid)
    wallet = user.get("wallet", 0)
    orders = get_orders(uid)
    txs = get_wallet_tx(uid)

    for a in accs:
        a.pop("xo", None)

    export_data = {
        "user_id": uid,
        "name": user.get("name", ""),
        "phone": user.get("phone", ""),
        "wallet_balance": wallet,
        "meesho_accounts": accs,
        "current_offer": offer,
        "orders_count": len(orders),
        "wallet_transactions": len(txs),
    }
    json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
    await q.edit_message_text(f"📤 *Your Data:*\n\n```{json_str[:3000]}```",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="account_menu")]]))


# ═══════════════════════════════════════════════════════════════
# ORDERS - Bot pe hi
# ═══════════════════════════════════════════════════════════════

async def cb_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    orders = get_orders(uid)

    if not orders:
        await q.edit_message_text(
            "📦 *My Orders*\n\nKoi orders nahi abhi.\nShopping shuru karo!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="back")]]))
        return

    msg = f"📦 *My Orders ({len(orders)})*\n\n"
    for o in orders[:10]:
        st = {"pending": "⏳", "confirmed": "✅", "delivered": "📦"}.get(o.get("status", ""), "❓")
        msg += f"{st} #{o['id']} | {fmt_price(o.get('total',0))} | {o.get('status','?')}\n"

    await q.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="back")]]))


# ═══════════════════════════════════════════════════════════════
# BACK / HOME
# ═══════════════════════════════════════════════════════════════

async def cb_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    user = get_user(uid) or create_user(uid, q.from_user.first_name)
    wallet = user.get("wallet", 0)
    accs = get_meesho_accounts(uid)
    offer = get_user_offer(uid)

    offer_text = ""
    if offer:
        offer_text = f"\n优惠: {offer.get('title','')} {offer.get('text','')}"
    else:
        offer_text = "\n优惠: Koi offer nahi. Roll karo!"

    text = (
        f"🛍️ *SHOP*\n"
        f"{'━'*26}\n\n"
        f"💰 Wallet: *{fmt_price(wallet)}*\n"
        f"📦 Accounts: {len(accs)}{offer_text}\n\n"
        f"Neeche buttons se sab karo:"
    )

    rows = [
        [InlineKeyboardButton("🎯 Roll Offer", callback_data="offer_roll"),
         InlineKeyboardButton("💰 Add Wallet", callback_data="wallet_add")],
        [InlineKeyboardButton("📦 My Orders", callback_data="orders"),
         InlineKeyboardButton("👤 My Account", callback_data="account_menu")],
        [InlineKeyboardButton("💳 Wallet History", callback_data="wallet_history")],
    ]
    WEBAPP_URL = os.environ.get("WEBAPP_URL", "")
    if WEBAPP_URL.startswith("https://"):
        rows.insert(0, [InlineKeyboardButton("🛍️ Open Shop", web_app=WebAppInfo(url=WEBAPP_URL))])
    if is_admin(uid):
        rows.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])

    await q.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(rows))


# ═══════════════════════════════════════════════════════════════
# ADMIN
# ═══════════════════════════════════════════════════════════════

async def cb_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not is_admin(q.from_user.id):
        await q.answer("Not admin!", show_alert=True)
        return
    orders = get_all_orders()
    btns = [
        [InlineKeyboardButton(f"📦 Orders ({len(orders)})", callback_data="admin_orders")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")],
    ]
    await q.edit_message_text(f"👑 *Admin Panel*\n\nTotal Orders: {len(orders)}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(btns))


async def cb_admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not is_admin(q.from_user.id):
        return
    orders = get_all_orders()
    if not orders:
        await q.edit_message_text("📭 Koi orders nahi!")
        return
    msg = f"📦 *ALL ORDERS ({len(orders)}):*\n\n"
    for o in orders[:20]:
        st = {"pending": "⏳", "confirmed": "✅", "delivered": "📦"}.get(o.get("status", ""), "❓")
        msg += f"#{o['id']} | 👤{o.get('user_id','?')} | {fmt_price(o.get('total',0))} | {st}\n"
    await q.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")]]))


# ═══════════════════════════════════════════════════════════════
# TEXT MESSAGE ROUTER
# ═══════════════════════════════════════════════════════════════

async def msg_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    # Custom wallet amount
    if context.user_data.get("wait_wamt"):
        context.user_data["wait_wamt"] = False
        try:
            amount = int(text)
            if amount < WALLET_MIN or amount > WALLET_MAX:
                await update.message.reply_text(f"❌ Amount {WALLET_MIN}-{WALLET_MAX} hona chahiye.")
                return
        except ValueError:
            await update.message.reply_text("❌ Sirf number likho.")
            return

        txn_id = generate_txn_id(uid)
        upi_link = create_upi_link(txn_id, amount)
        qr_url = get_qr_url(upi_link)
        create_wallet_tx(uid, amount, txn_id)

        btns = [[InlineKeyboardButton("✅ I Paid - Verify", callback_data=f"wverify_{txn_id}_{amount}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="back")]]
        await update.message.reply_text(
            f"💳 *Payment Karo*\n\nAmount: *{fmt_price(amount)}*\nUPI ID: `{GW_UPI_ID}`\n\nQR scan karo ya UPI ID pay karo.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(btns))
        try:
            await update.message.reply_photo(photo=qr_url,
                caption=f"📱 QR Code - {fmt_price(amount)}",
                parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await update.message.reply_text(f"🔗 QR: {qr_url}")
        return

    # Add account phone
    if context.user_data.get("wait_acc_phone"):
        context.user_data["wait_acc_phone"] = False
        phone = text[-10:] if len(text) >= 10 else text
        if len(phone) != 10 or not phone.isdigit():
            await update.message.reply_text("❌ 10 digit phone number likho.")
            return

        await update.message.reply_text(f"📱 *{phone}* pe OTP bhej raha hoon...", parse_mode=ParseMode.MARKDOWN)
        result = send_otp(phone)
        if result.get("ok") and result.get("session"):
            context.user_data["acc_session"] = result["session"]
            context.user_data["acc_phone"] = phone
            context.user_data["wait_acc_otp"] = True
            await update.message.reply_text(
                f"✅ OTP bheja gaya *{phone}* pe!\nOTP likho:",
                parse_mode=ParseMode.MARKDOWN)
        else:
            err = result.get("error", "Failed")
            await update.message.reply_text(f"❌ OTP send nahi hua: {err}")
        return

    # Add account OTP
    if context.user_data.get("wait_acc_otp"):
        context.user_data["wait_acc_otp"] = False
        phone = context.user_data.get("acc_phone", "")
        session = context.user_data.get("acc_session")
        if not session:
            await update.message.reply_text("❌ Session expire ho gaya. Dobara add karo.")
            return

        await update.message.reply_text("🔍 OTP verify ho raha hai...", parse_mode=ParseMode.MARKDOWN)
        result = verify_otp(phone, text, session)
        if result.get("ok"):
            save_meesho_account(uid, phone,
                result.get("user_id", ""),
                result.get("xo", ""),
                result.get("xo_exp", 0),
                result.get("instance_id", ""))

            await update.message.reply_text(
                f"✅ *Account Add Ho Gaya!*\n\n📱 Phone: `{phone}`\n🆔 User ID: `{result.get('user_id','?')}`\n\n"
                f"Ab shopping shuru karo!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="back")]]))
        else:
            err = result.get("error", "Wrong OTP")
            await update.message.reply_text(
                f"❌ OTP galat hai: {err}\n\nDobara try karo /start",
                parse_mode=ParseMode.MARKDOWN)
        context.user_data.pop("acc_session", None)
        context.user_data.pop("acc_phone", None)
        return

    # Admin add product
    if is_admin(uid) and context.user_data.get("wait_prod"):
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
# ADMIN COMMANDS
# ═══════════════════════════════════════════════════════════════

async def cmd_addproduct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    context.user_data["wait_prod"] = True
    await update.message.reply_text(
        "📦 Product add karo:\n\nFormat: name | price | stock | category",
        parse_mode=ParseMode.HTML)


# ═══════════════════════════════════════════════════════════════
# CALLBACK ROUTER
# ═══════════════════════════════════════════════════════════════

async def cb_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    d = q.data

    if d == "back":
        await cb_back(update, context)
    elif d == "offer_roll":
        await cb_offer_roll(update, context)
    elif d == "wallet_add":
        await cb_wallet_add(update, context)
    elif d.startswith("wamt_"):
        await cb_wallet_amount(update, context)
    elif d.startswith("wverify_"):
        await cb_wallet_verify(update, context)
    elif d == "wallet_history":
        await cb_wallet_history(update, context)
    elif d == "account_menu":
        await cb_account_menu(update, context)
    elif d == "acc_add":
        await cb_acc_add(update, context)
    elif d.startswith("acc_view_"):
        await cb_acc_view(update, context)
    elif d.startswith("acc_del_"):
        await cb_acc_del(update, context)
    elif d == "acc_refresh":
        await cb_acc_refresh(update, context)
    elif d == "acc_export":
        await cb_acc_export(update, context)
    elif d == "orders":
        await cb_orders(update, context)
    elif d == "admin_panel":
        await cb_admin_panel(update, context)
    elif d == "admin_orders":
        await cb_admin_orders(update, context)


# ═══════════════════════════════════════════════════════════════
# FLASK IN BACKGROUND
# ═══════════════════════════════════════════════════════════════

def run_flask():
    from app import app as flask_app
    flask_app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print("Starting Bot + Mini App...")
    print(f"Admin: {ADMIN_IDS}")

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("Flask running on port 5000")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("addproduct", cmd_addproduct))
    app.add_handler(CallbackQueryHandler(cb_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_router))

    print("Bot running!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

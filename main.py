#!/usr/bin/env python3
"""
main.py - Telegram Bot Entrypoint for Meesho FOD Pilot
Handles /start, /help, /status, and /mode (/togglemode) commands.
"""
import logging
import os
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

import config
from database import (
    init_db,
    get_global_mode,
    set_global_mode,
    get_order_fee,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("meesho_bot")


def is_admin(user_id: int) -> bool:
    return int(user_id) in config.ADMIN_IDS


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /start command with WebApp launcher."""
    user = update.effective_user
    name = user.first_name if user else "Shopper"
    mode = get_global_mode().upper()
    fee = get_order_fee()

    msg = (
        f"👋 *Welcome to {config.BRAND_NAME}, {name}!*\n\n"
        f"🎯 *First-Order Discount (FOD) Pilot Engine*\n"
        f"• Auto-roll ₹180–₹220 OFF on Meesho 1st orders\n"
        f"• Direct real-time Meesho Cart & Catalog sync\n"
        f"• COD & Instant UPI Payments\n\n"
        f"⚙️ *Current Platform Mode:* `{mode}` (Fee: ₹{fee})\n\n"
        f"Tap the button below to launch the Mini App:"
    )

    buttons = []
    if config.WEBAPP_URL:
        buttons.append([InlineKeyboardButton("🚀 Open Meesho Mini App", web_app=WebAppInfo(url=config.WEBAPP_URL))])
    else:
        buttons.append([InlineKeyboardButton("ℹ️ WebApp URL not set", callback_data="no_url")])

    if user and is_admin(user.id):
        buttons.append([
            InlineKeyboardButton(f"⚙️ Switch Mode ({'FREE' if mode == 'PAID' else 'PAID'})", callback_data="toggle_mode")
        ])

    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)


async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles /mode and /togglemode command.
    Shows current mode, and allows admins to toggle between free/paid mode.
    Usage:
      /mode
      /mode free
      /mode paid
      /mode toggle
    """
    user = update.effective_user
    if not user:
        return

    current_mode = get_global_mode().lower()
    current_fee = get_order_fee()

    # If arguments provided (e.g. /mode free, /mode paid, /mode toggle)
    if context.args:
        arg = context.args[0].strip().lower()
        if not is_admin(user.id):
            await update.message.reply_text(
                f"⚠️ *Access Denied:* Only administrators can change platform mode.\n"
                f"Current mode: `{current_mode.upper()}` (Order fee: ₹{current_fee})",
                parse_mode="Markdown",
            )
            return

        if arg in ("free", "0"):
            new_mode = set_global_mode("free")
        elif arg in ("paid", "5"):
            new_mode = set_global_mode("paid")
        elif arg in ("toggle", "switch"):
            new_mode = set_global_mode("free" if current_mode == "paid" else "paid")
        else:
            await update.message.reply_text("Usage: `/mode [free|paid|toggle]`", parse_mode="Markdown")
            return

        new_fee = get_order_fee()
        await update.message.reply_text(
            f"✅ *Platform Mode Updated!*\n\n"
            f"• *New Mode:* `{new_mode.upper()}`\n"
            f"• *Platform Order Fee:* ₹{new_fee}\n"
            f"Changes take effect immediately across all users without server restart.",
            parse_mode="Markdown",
        )
        return

    # No arguments: Show current mode and admin toggle buttons
    if is_admin(user.id):
        target_mode = "free" if current_mode == "paid" else "paid"
        keyboard = [
            [
                InlineKeyboardButton(
                    f"🔄 Switch to {target_mode.upper()} Mode",
                    callback_data="toggle_mode",
                )
            ]
        ]
        await update.message.reply_text(
            f"⚙️ *Platform Mode Management (Admin)*\n\n"
            f"• Current Mode: *{current_mode.upper()}*\n"
            f"• Platform Order Fee: *₹{current_fee}*\n\n"
            f"_FREE mode removes the ₹5 internal wallet deduction on orders._\n"
            f"_PAID mode enforces ₹5 platform service fee per order._",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await update.message.reply_text(
            f"ℹ️ *Platform Mode Status*\n\n"
            f"• Current Mode: *{current_mode.upper()}*\n"
            f"• Platform Fee: *₹{current_fee} per order*\n\n"
            f"_(Only bot administrators can toggle mode)_",
            parse_mode="Markdown",
        )


async def on_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles inline button clicks for mode toggling."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not user:
        return

    if query.data == "toggle_mode":
        if not is_admin(user.id):
            await query.edit_message_text("⚠️ Access denied: Only bot admins can toggle mode.")
            return

        current_mode = get_global_mode().lower()
        new_mode = set_global_mode("free" if current_mode == "paid" else "paid")
        new_fee = get_order_fee()
        target_next = "paid" if new_mode == "free" else "free"

        keyboard = [
            [
                InlineKeyboardButton(
                    f"🔄 Switch to {target_next.upper()} Mode",
                    callback_data="toggle_mode",
                )
            ]
        ]
        await query.edit_message_text(
            f"✅ *Platform Mode Updated!*\n\n"
            f"• *Active Mode:* `{new_mode.upper()}`\n"
            f"• *Platform Order Fee:* ₹{new_fee}\n\n"
            f"Live database updated without code reload.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    elif query.data == "no_url":
        await query.edit_message_text(
            "ℹ️ WEBAPP_URL environment variable is not configured yet. Set it in .env or your host environment."
        )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /status command."""
    mode = get_global_mode().upper()
    fee = get_order_fee()
    await update.message.reply_text(
        f"🟢 *{config.BRAND_NAME} System Status*\n\n"
        f"• *Status:* Online & Synchronized\n"
        f"• *Global Mode:* `{mode}`\n"
        f"• *Order Platform Fee:* ₹{fee}\n"
        f"• *Database:* SQLite Persistent Ledger\n"
        f"• *FOD Target Bucket:* ₹180–₹220 OFF",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /help command."""
    await update.message.reply_text(
        f"📖 *{config.BRAND_NAME} Command Reference:*\n\n"
        f"/start - Launch Meesho Mini App & Welcome info\n"
        f"/mode [free|paid|toggle] - View or toggle Free vs Paid platform fee\n"
        f"/togglemode - Quick toggle between Free and Paid mode\n"
        f"/status - View system and mode status\n"
        f"/help - Display this help guide",
        parse_mode="Markdown",
    )


def main():
    """Initializes and runs the Telegram bot."""
    init_db()
    token = config.BOT_TOKEN
    if not token or "AAFPMF3BcrF1drjCrzOL0OshDRfVWG1akU0" not in token and len(token) < 20:
        logger.error("BOT_TOKEN is not valid. Please check your config.py or environment.")
        return

    logger.info(f"Starting {config.BRAND_NAME} Telegram Bot...")
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("togglemode", cmd_mode))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(on_callback_query))

    logger.info(f"Bot listening for updates. Admin IDs: {config.ADMIN_IDS}")
    app.run_polling()


if __name__ == "__main__":
    main()

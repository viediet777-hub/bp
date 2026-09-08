import logging
import sys
import os
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import settings
from bot.database.database import db
from bot.services.api_helpers import set_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running!")

    def log_message(self, format, *args):
        pass


def start_health_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"Health server started on port {port}")
    server.serve_forever()


def main():
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN missing! .env file banao.")
    if not settings.ADMIN_IDS:
        raise RuntimeError("ADMIN_IDS missing! .env file banao.")

    set_token(settings.BOT_TOKEN)

    if os.getenv("RAILWAY_STATIC_URL"):
        thread = threading.Thread(target=start_health_server, daemon=True)
        thread.start()

    from telegram import Update
    from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                               MessageHandler, filters)

    from bot.handlers.user_handlers import (
        start_command, force_join_check, buy_products_callback,
        product_detail_callback, quantity_callback, place_order_callback,
        my_orders_callback, wallet_callback, add_funds_callback,
        check_deposit_callback, send_screenshot_callback, support_callback,
        approve_deposit_command, add_balance_command, done_command,
        main_menu_callback, text_router, photo_router
    )
    from bot.handlers.admin_handlers import (
        admin_command, admin_panel_callback, admin_add_product_start,
        admin_add_messages, admin_products_callback, admin_product_detail_callback,
        admin_stock_callback, admin_stock_product_callback, admin_stock_add_callback,
        admin_stock_export_callback, admin_stock_withdraw_callback,
        admin_users_callback, admin_stats_callback, admin_broadcast_callback,
        admin_force_channel_callback, admin_set_channel_callback,
        admin_disable_channel_callback, handle_admin_text
    )

    app = Application.builder().token(settings.BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("approve", approve_deposit_command))
    app.add_handler(CommandHandler("add", add_balance_command))
    app.add_handler(CommandHandler("done", done_command))

    # User callbacks
    app.add_handler(CallbackQueryHandler(force_join_check, pattern=r"^force_join_check$"))
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern=r"^main_menu$"))
    app.add_handler(CallbackQueryHandler(buy_products_callback, pattern=r"^buy_products$"))
    app.add_handler(CallbackQueryHandler(product_detail_callback, pattern=r"^product_\d+$"))
    app.add_handler(CallbackQueryHandler(quantity_callback, pattern=r"^qty_"))
    app.add_handler(CallbackQueryHandler(place_order_callback, pattern=r"^place_order_\d+$"))
    app.add_handler(CallbackQueryHandler(my_orders_callback, pattern=r"^my_orders$"))
    app.add_handler(CallbackQueryHandler(wallet_callback, pattern=r"^wallet$"))
    app.add_handler(CallbackQueryHandler(add_funds_callback, pattern=r"^add_funds$"))
    app.add_handler(CallbackQueryHandler(check_deposit_callback, pattern=r"^check_deposit$"))
    app.add_handler(CallbackQueryHandler(send_screenshot_callback, pattern=r"^send_screenshot$"))
    app.add_handler(CallbackQueryHandler(support_callback, pattern=r"^support$"))

    # Admin callbacks
    app.add_handler(CallbackQueryHandler(admin_panel_callback, pattern=r"^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_add_product_start, pattern=r"^admin_add_product$"))
    app.add_handler(CallbackQueryHandler(admin_products_callback, pattern=r"^admin_products$"))
    app.add_handler(CallbackQueryHandler(admin_product_detail_callback, pattern=r"^admin_prod_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_stock_callback, pattern=r"^admin_stock$"))
    app.add_handler(CallbackQueryHandler(admin_stock_product_callback, pattern=r"^admin_stock_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_stock_add_callback, pattern=r"^admin_stockadd_"))
    app.add_handler(CallbackQueryHandler(admin_stock_export_callback, pattern=r"^admin_stockexport_"))
    app.add_handler(CallbackQueryHandler(admin_stock_withdraw_callback, pattern=r"^admin_stockwithdraw_"))
    app.add_handler(CallbackQueryHandler(admin_users_callback, pattern=r"^admin_users$"))
    app.add_handler(CallbackQueryHandler(admin_stats_callback, pattern=r"^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast_callback, pattern=r"^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(admin_force_channel_callback, pattern=r"^admin_force_channel$"))
    app.add_handler(CallbackQueryHandler(admin_set_channel_callback, pattern=r"^admin_set_channel$"))
    app.add_handler(CallbackQueryHandler(admin_disable_channel_callback, pattern=r"^admin_disable_channel$"))

    # Photo handler (screenshots)
    app.add_handler(MessageHandler(filters.PHOTO, photo_router))

    # Text handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

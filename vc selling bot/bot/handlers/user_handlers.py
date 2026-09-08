from telegram import Update
from telegram.ext import ContextTypes
from bot.database.database import db
from bot.database.models import User, Product, Order, StockCode
from bot.services.api_helpers import (send_msg, edit_msg, answer_cb, send_photo,
                                       send_doc, sbtn, sbtn_url, ICON, get_chat_member)
from bot.services.payment import VCPaymentGateway
from bot.keyboards.keyboards import main_menu_kb, back_kb, product_detail_kb
from config.settings import settings


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = User.get_or_create(user_id, update.effective_user.username,
                               update.effective_user.first_name, update.effective_user.last_name)
    if settings.FORCE_JOIN_CHANNEL:
        try:
            member = get_chat_member(settings.FORCE_JOIN_CHANNEL, user_id)
            status = member.get("result", {}).get("status", "left")
            if status in ("left", "kicked"):
                await send_msg(user_id,
                    "🔒 <b>Channel Join Required</b>\n\nPehle channel join karo, phir /start dabao.",
                    {"inline_keyboard": [
                        [sbtn("📢 Join Channel", f"https://t.me/{settings.FORCE_JOIN_CHANNEL.replace('@','')}", "success")],
                        [sbtn("✅ I Joined", "force_join_check", "primary", ICON["success"])]
                    ]})
                return
        except:
            pass
    user = User.get(user_id)
    bal = user.wallet_balance if user else 0
    text = (
        f"👋 <b>Welcome, {user.first_name or 'User'}!</b>\n\n"
        f"🛒 <b>Digital Store</b>\n"
        f"💰 Balance: <b>{bal}</b>\n\n"
        f"Choose an option:"
    )
    await send_msg(user_id, text, main_menu_kb())


async def force_join_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if settings.FORCE_JOIN_CHANNEL:
        try:
            member = get_chat_member(settings.FORCE_JOIN_CHANNEL, user_id)
            status = member.get("result", {}).get("status", "left")
            if status in ("left", "kicked"):
                await answer_cb(query.id, "❌ Pehle channel join karo!", True)
                return
        except:
            pass
    await answer_cb(query.id, "✅ Verified!")
    user = User.get(user_id)
    bal = user.wallet_balance if user else 0
    await query.edit_message_text(
        f"👋 <b>Welcome!</b>\n\n💰 Balance: <b>{bal}</b>\n\nChoose an option:",
        reply_markup=main_menu_kb(), parse_mode="HTML")


async def buy_products_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await answer_cb(query.id)
    user = User.get(query.from_user.id)
    products = Product.get_all(status="active")
    if not products:
        await query.edit_message_text("📦 Abhi koi product available nahi hai.",
            reply_markup=back_kb(), parse_mode="HTML")
        return
    bal = user.wallet_balance if user else 0
    text = f"🛒 <b>Products</b>\n\n💰 Balance: <b>{bal}</b>\n\nProduct select karo:"
    buttons = []
    for p in products:
        sc = StockCode.count_unused(p.id)
        buttons.append([sbtn(f"📦 {p.name} ({p.price}) [{sc} codes]", f"product_{p.id}", "primary", ICON["cart"])])
    buttons.append([sbtn("🔙 Back", "main_menu", "danger", ICON["back"])])
    await query.edit_message_text(text, reply_markup={"inline_keyboard": buttons}, parse_mode="HTML")


async def product_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await answer_cb(query.id)
    product_id = int(query.data.split("_")[1])
    product = Product.get(product_id)
    if not product:
        return await answer_cb(query.id, "❌ Product not found!", True)
    context.user_data['current_product_id'] = product_id
    context.user_data['current_qty'] = 1
    sc = StockCode.count_unused(product.id)
    text = (
        f"📦 <b>{product.name}</b>\n\n"
        f"📄 Description:\n{product.description}\n\n"
        f"💰 Price: <b>{product.price}/code</b>\n"
        f"🎫 Stock: <b>{sc} codes</b>\n"
        f"🔢 Qty: <b>1</b>\n"
        f"💸 Total: <b>{product.price}</b>\n\n"
        f"Qty select karo:"
    )
    await query.edit_message_text(text, reply_markup=product_detail_kb(product, 1), parse_mode="HTML")


async def quantity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    product_id = context.user_data.get('current_product_id')
    if not product_id:
        return await answer_cb(query.id, "❌ Product not selected!", True)
    product = Product.get(product_id)
    if not product:
        return await answer_cb(query.id, "❌ Product not found!", True)
    qty = context.user_data.get('current_qty', 1)
    sc = StockCode.count_unused(product.id)

    if data.startswith("qty_inc_"):
        qty += 1
    elif data.startswith("qty_dec_"):
        qty = max(1, qty - 1)
    elif data.startswith("qty_set_"):
        parts = data.split("_")
        try:
            qty = min(int(parts[-1]), sc)
        except:
            pass
    elif data.startswith("qty_custom_"):
        context.user_data['awaiting_custom_qty'] = True
        await query.edit_message_text("🔢 <b>Custom Quantity</b>\n\nSirf number likho.",
            reply_markup=product_detail_kb(product, qty), parse_mode="HTML")
        return
    elif data.startswith("qty_info_"):
        return await answer_cb(query.id, "🔢 +/- buttons se qty change karo")

    if qty > sc:
        qty = sc
    context.user_data['current_qty'] = qty
    total = product.price * qty
    text = (
        f"📦 <b>{product.name}</b>\n\n"
        f"📄 Description:\n{product.description}\n\n"
        f"💰 Price: <b>{product.price}/code</b>\n"
        f"🎫 Stock: <b>{sc} codes</b>\n"
        f"🔢 Qty: <b>{qty}</b>\n"
        f"💸 Total: <b>{total}</b>\n\n"
        f"Qty select karo:"
    )
    await answer_cb(query.id)
    await query.edit_message_text(text, reply_markup=product_detail_kb(product, qty), parse_mode="HTML")


async def custom_quantity_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_custom_qty'):
        return
    try:
        qty = int(update.message.text.strip())
        if qty < 1:
            raise ValueError
    except:
        return await send_msg(update.effective_chat.id, "❌ Valid number likho!")
    product_id = context.user_data.get('current_product_id')
    product = Product.get(product_id)
    if not product:
        return
    sc = StockCode.count_unused(product.id)
    if qty > sc:
        qty = sc
    context.user_data['awaiting_custom_qty'] = False
    context.user_data['current_qty'] = qty
    total = product.price * qty
    text = (
        f"📦 <b>{product.name}</b>\n\n"
        f"💰 Price: <b>{product.price}/code</b>\n"
        f"🎫 Stock: <b>{sc} codes</b>\n"
        f"🔢 Qty: <b>{qty}</b>\n"
        f"💸 Total: <b>{total}</b>\n\n"
        f"Buy karna hai?"
    )
    await send_msg(update.effective_chat.id, text, product_detail_kb(product, qty))


async def place_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await answer_cb(query.id)
    user_id = query.from_user.id
    user = User.get(user_id)
    product_id = context.user_data.get('current_product_id')
    qty = context.user_data.get('current_qty', 1)
    if not product_id:
        return await answer_cb(query.id, "❌ Product not selected!", True)
    product = Product.get(product_id)
    if not product:
        return await answer_cb(query.id, "❌ Product not found!", True)
    sc = StockCode.count_unused(product.id)
    if sc < qty:
        return await answer_cb(query.id, f"❌ Stock kam hai! Sirf {sc} codes.", True)
    total_price = product.price * qty
    if user.wallet_balance < total_price:
        context.user_data['pending_order'] = {'product_id': product_id, 'quantity': qty}
        needed = total_price - user.wallet_balance
        await query.edit_message_text(
            f"❌ <b>Balance Kam Hai!</b>\n\n"
            f"💸 Required: <b>{total_price}</b>\n"
            f"💰 Available: <b>{user.wallet_balance}</b>\n"
            f"📈 Need: <b>{needed}</b>\n\n"
            f"Funds add karo.",
            reply_markup={"inline_keyboard": [
                [sbtn("💰 Add Funds", "wallet", "success", ICON["wallet"])],
                [sbtn("🔙 Back", f"product_{product_id}", "danger")]
            ]}, parse_mode="HTML")
        return
    user.deduct_balance(total_price)
    product.reduce_stock(qty)
    order = Order.create(user_id, product_id, qty, total_price)
    codes = StockCode.assign(product.id, order.order_id, qty)
    if not codes:
        user.add_balance(total_price)
        return await answer_cb(query.id, "❌ Stock khatm! Paisa wapas.", True)
    order.save_codes(codes)
    file_content = f"📦 Product : {product.name}\n🆔 Order ID: {order.order_id}\n🔢 Quantity: {qty}\n{'-'*30}\n"
    file_content += "\n".join(codes)
    file_content += f"\n{'-'*30}\n⏰ Note: 24 hrs me use karo.\n"
    await send_doc(user_id, file_content, f"{order.order_id}.txt",
                   f"📦 <b>Your Codes</b>\n🆔 Order: <code>{order.order_id}</code>\n🔢 Qty: {qty}")
    user = User.get(user_id)
    text = (
        f"🎉 <b>Purchase Successful!</b>\n\n"
        f"📦 Product: <b>{product.name}</b>\n"
        f"🆔 Order: <code>{order.order_id}</code>\n"
        f"🔢 Qty: <b>{qty}</b>\n"
        f"💸 Paid: <b>{total_price}</b>\n"
        f"💰 Balance: <b>{user.wallet_balance}</b>\n\n"
        f"📦 <b>{qty} codes TXT file me bheje gaye hain.</b>"
    )
    kb = {"inline_keyboard": [
        [sbtn("🛒 More Products", "buy_products", "primary", ICON["cart"]),
         sbtn("📋 My Orders", "my_orders", "success", ICON["order"])]
    ]}
    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")


async def my_orders_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await answer_cb(query.id)
    orders = Order.get_user_orders(query.from_user.id)
    if not orders:
        return await query.edit_message_text("📋 <b>My Orders</b>\n\nAbhi koi order nahi.",
            reply_markup=back_kb(), parse_mode="HTML")
    text = "📋 <b>My Orders</b>\n\n"
    for o in orders:
        p = Product.get(o.product_id)
        text += f"🆔 <code>{o.order_id}</code> - {p.name if p else '?'}\n🔢 Qty: {o.quantity} | 💸 {o.total_price} | {o.status}\n\n"
    await query.edit_message_text(text, reply_markup=back_kb(), parse_mode="HTML")


async def wallet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await answer_cb(query.id)
    user = User.get(query.from_user.id)
    text = (
        f"💰 <b>Wallet</b>\n\n"
        f"💰 Balance: <b>{user.wallet_balance}</b>\n"
        f"💵 Deposited: <b>{user.total_deposited}</b>\n"
        f"💸 Spent: <b>{user.total_spent}</b>\n\n"
        f"Funds add karo:"
    )
    kb = {"inline_keyboard": [
        [sbtn("💳 Add Balance", "add_funds", "success", ICON["wallet"])],
        [sbtn("🔙 Back", "main_menu", "danger", ICON["back"])]
    ]}
    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")


# ============================================================
# DEPOSIT FLOW - EXACT BOTHELP LOGIC
# ============================================================

async def add_funds_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await answer_cb(query.id)
    await query.edit_message_text(
        "💳 <b>ENTER YOUR DEPOSIT AMOUNT</b>\n\n"
        "💰 Minimum Deposit: <b>1</b>\n"
        "Enter the amount you want to add.\n\n"
        "📝 Example: <code>100</code>",
        reply_markup=back_kb("wallet"), parse_mode="HTML")
    context.user_data['awaiting_deposit_amount'] = True


async def deposit_amount_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_deposit_amount'):
        return

    amount_text = update.message.text.strip()
    try:
        amount = int(amount_text)
        if amount < 1:
            raise ValueError
    except:
        return await send_msg(update.effective_chat.id,
            "❌ <b>INVALID AMOUNT</b>\n\n💰 Minimum Deposit: <b>1</b>\n📝 Example: <code>100</code>")

    context.user_data['awaiting_deposit_amount'] = False
    user_id = update.effective_user.id

    order_id = VCPaymentGateway.create_order_id(user_id)

    context.user_data['deposit_order_id'] = order_id
    context.user_data['deposit_amount'] = amount

    qr_url = VCPaymentGateway.generate_qr_url(amount, order_id)

    text = (
        f"💳 <b>VC PAYMENT GATEWAY</b>\n\n"
        f"💸 Amount: <b>{amount}</b>\n"
        f"🆔 Order ID:\n<code>{order_id}</code>\n\n"
        f"📱 Scan the QR code to pay.\n\n"
        f"⚠️ Pay the exact amount shown above.\n\n"
        f"✅ After payment, click CHECK PAYMENT."
    )
    kb = {"inline_keyboard": [
        [sbtn("✅ CHECK PAYMENT", "check_deposit", "success", ICON["success"])]
    ]}
    await send_photo(update.effective_chat.id, qr_url, text, kb)


async def check_deposit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    order_id = context.user_data.get('deposit_order_id')
    amount = context.user_data.get('deposit_amount')

    if not order_id or not amount:
        await answer_cb(query.id, "❌ Transaction data not found.", True)
        return

    try:
        await query.message.delete()
    except:
        pass

    await answer_cb(query.id, "🔄 Checking payment...")

    result = VCPaymentGateway.check_payment(order_id, amount)

    if result.get("status") == "success":
        credited = float(result.get("amount_credited", amount))
        user = User.get(query.from_user.id)
        user.add_balance(credited)

        context.user_data.pop('deposit_order_id', None)
        context.user_data.pop('deposit_amount', None)

        user = User.get(query.from_user.id)
        text = (
            f"🎉 <b>Payment Successful!</b>\n\n"
            f"🆔 Order ID: <code>{order_id}</code>\n"
            f"💸 Amount Added: <b>{credited}</b>\n"
            f"💰 Current Balance: <b>{user.wallet_balance}</b>\n\n"
            f"✅ Your wallet has been credited successfully."
        )
        await send_msg(query.from_user.id, text, back_kb())

        for admin_id in settings.ADMIN_IDS:
            try:
                await send_msg(admin_id,
                    f"🟢 <b>New Successful Payment</b>\n\n"
                    f"👤 User ID: <code>{query.from_user.id}</code>\n"
                    f"🆔 Order ID: <code>{order_id}</code>\n"
                    f"💸 Amount: <b>{credited}</b>",
                    parse_mode="HTML")
            except:
                pass

    else:
        text = (
            f"⏳ <b>Payment Not Found</b>\n\n"
            f"🆔 Order ID: <code>{order_id}</code>\n"
            f"📊 Status: {result.get('message', 'Pending')}\n\n"
            f"Please complete your payment and try again."
        )
        kb = {"inline_keyboard": [
            [sbtn("✅ CHECK PAYMENT", "check_deposit", "success", ICON["success"])],
            [sbtn("🔙 Back", "wallet", "danger", ICON["back"])]
        ]}
        await send_msg(query.from_user.id, text, kb)


# ============================================================
# ADMIN: /add userid amount
# ============================================================

async def add_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in settings.ADMIN_IDS:
        return
    text = update.message.text.strip()
    parts = text.split()
    if len(parts) < 3:
        return await send_msg(user_id,
            "📝 <b>Usage:</b>\n/add USERID AMOUNT\n\nExample: <code>/add 12345678 100</code>")
    try:
        target_user_id = int(parts[1])
        amount = int(parts[2])
    except:
        return await send_msg(user_id, "❌ <b>Invalid format!</b>\nUsage: /add USERID AMOUNT")
    user = User.get(target_user_id)
    if not user:
        return await send_msg(user_id, f"❌ <b>User not found:</b> {target_user_id}")
    user.add_balance(amount)
    user = User.get(target_user_id)
    await send_msg(user_id,
        f"✅ <b>Balance Added!</b>\n\n"
        f"👤 User ID: <code>{target_user_id}</code>\n"
        f"💸 Amount: <b>{amount}</b>\n"
        f"💰 New Balance: <b>{user.wallet_balance}</b>")
    try:
        await send_msg(target_user_id,
            f"💰 <b>Balance Added!</b>\n\n"
            f"💸 Amount: <b>{amount}</b>\n"
            f"💰 Balance: <b>{user.wallet_balance}</b>")
    except:
        pass


async def approve_deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in settings.ADMIN_IDS:
        return
    text = update.message.text.strip()
    parts = text.split("_")
    if len(parts) < 3:
        return await send_msg(user_id,
            "📝 <b>Usage:</b>\n/approve_USERID_AMOUNT\nExample: <code>/approve_12345678_100</code>")
    try:
        target_user_id = int(parts[1])
        amount = int(parts[2])
    except:
        return await send_msg(user_id, "❌ <b>Invalid format!</b>\nUsage: /approve_USERID_AMOUNT")
    user = User.get(target_user_id)
    if not user:
        return await send_msg(user_id, f"❌ <b>User not found:</b> {target_user_id}")
    user.add_balance(amount)
    user = User.get(target_user_id)
    await send_msg(user_id,
        f"✅ <b>Deposit Approved!</b>\n\n"
        f"👤 User ID: <code>{target_user_id}</code>\n"
        f"💸 Amount: <b>{amount}</b>\n"
        f"💰 New Balance: <b>{user.wallet_balance}</b>")
    try:
        await send_msg(target_user_id,
            f"✅ <b>Deposit Approved!</b>\n\n"
            f"💸 Amount: <b>{amount}</b>\n"
            f"💰 Balance: <b>{user.wallet_balance}</b>")
    except:
        pass


async def send_screenshot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await answer_cb(query.id)
    order_id = context.user_data.get('deposit_order_id')
    amount = context.user_data.get('deposit_amount')
    if not order_id:
        return await answer_cb(query.id, "❌ Koi pending deposit nahi hai!", True)
    context.user_data['awaiting_screenshot'] = True
    await query.edit_message_text(
        f"📸 <b>SCREENSHOT BHEJO</b>\n\n"
        f"🆔 Order ID: <code>{order_id}</code>\n"
        f"💸 Amount: <b>{amount}</b>\n\n"
        f"Payment ka screenshot yahan bhejo.\n"
        f"Admin approve karega.",
        reply_markup=back_kb("wallet"), parse_mode="HTML")


async def photo_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.user_data.get('awaiting_screenshot'):
        return
    context.user_data['awaiting_screenshot'] = False
    order_id = context.user_data.get('deposit_order_id')
    amount = context.user_data.get('deposit_amount')
    caption = (
        f"📸 <b>NEW DEPOSIT REQUEST</b>\n\n"
        f"👤 User ID: <code>{user_id}</code>\n"
        f"🆔 Order ID: <code>{order_id}</code>\n"
        f"💸 Amount: <b>{amount}</b>\n\n"
        f"Approve: <code>/approve_{user_id}_{amount}</code>"
    )
    for admin_id in settings.ADMIN_IDS:
        try:
            await update.message.forward(chat_id=admin_id)
            await send_msg(admin_id, caption)
        except:
            pass
    await send_msg(user_id,
        f"✅ <b>Screenshot Received!</b>\n\n"
        f"🆔 Order ID: <code>{order_id}</code>\n"
        f"💸 Amount: <b>{amount}</b>\n\n"
        f"Admin jaldi approve karega.",
        back_kb("wallet"))


async def support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await answer_cb(query.id)
    await query.edit_message_text("📞 <b>Support</b>\n\nAdmin se contact karo.",
        reply_markup=back_kb(), parse_mode="HTML")


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await answer_cb(query.id)
    user = User.get(query.from_user.id)
    bal = user.wallet_balance if user else 0
    await query.edit_message_text(
        f"👋 <b>Welcome!</b>\n\n💰 Balance: <b>{bal}</b>\n\nChoose an option:",
        reply_markup=main_menu_kb(), parse_mode="HTML")


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in settings.ADMIN_IDS:
        return
    if context.user_data.get('awaiting_add_codes'):
        from bot.handlers.admin_handlers import admin_add_messages
        fake_update = update
        fake_update.message.text = "/done"
        await admin_add_messages(fake_update, context)
        return
    if context.user_data.get('awaiting_stock_add'):
        from bot.handlers.admin_handlers import handle_admin_text
        fake_update = update
        fake_update.message.text = "/done"
        await handle_admin_text(fake_update, context)
        return


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if context.user_data.get('awaiting_custom_qty'):
        await custom_quantity_message(update, context)
        return
    if context.user_data.get('awaiting_deposit_amount'):
        await deposit_amount_message(update, context)
        return
    if any(context.user_data.get(k) for k in ['awaiting_add_name', 'awaiting_add_price',
            'awaiting_add_desc', 'awaiting_add_codes']):
        from bot.handlers.admin_handlers import admin_add_messages
        await admin_add_messages(update, context)
        return
    if context.user_data.get('awaiting_withdraw_qty'):
        from bot.handlers.admin_handlers import handle_admin_text
        await handle_admin_text(update, context)
        return
    if any(context.user_data.get(k) for k in ['awaiting_stock_add',
            'awaiting_broadcast', 'awaiting_set_channel']):
        from bot.handlers.admin_handlers import handle_admin_text
        await handle_admin_text(update, context)
        return

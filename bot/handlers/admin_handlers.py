from telegram import Update
from telegram.ext import ContextTypes
from bot.database.models import User, Product, Order, StockCode
from bot.services.api_helpers import (send_msg, edit_msg, answer_cb, send_doc,
                                       sbtn, sbtn_url, ICON)
from bot.keyboards.keyboards import back_kb, admin_panel_kb
from config.settings import settings
from bot.database.database import db


def _load_force_channel():
    """Load force-join channel from database on startup."""
    try:
        row = db.fetchone("SELECT value FROM settings WHERE key = 'force_join_channel'")
        if row and row['value']:
            settings.FORCE_JOIN_CHANNEL = row['value']
    except Exception:
        pass

_load_force_channel()


def is_admin(user_id):
    return user_id in settings.ADMIN_IDS


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await send_msg(user_id, "❌ Access Denied!")
        return
    total_users = User.count()
    products = Product.get_all()
    total_codes = sum(StockCode.count_unused(p.id) for p in products)
    text = (
        f"🔧 <b>ADMIN PANEL</b>\n\n"
        f"👤 Users: <b>{total_users}</b> | "
        f"📦 Products: <b>{len(products)}</b> | "
        f"🎫 Codes: <b>{total_codes}</b>\n\n"
        f"Choose option:"
    )
    await send_msg(user_id, text, admin_panel_kb())


async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return await answer_cb(query.id, "❌ Access Denied!", True)
    await answer_cb(query.id)
    total_users = User.count()
    products = Product.get_all()
    total_codes = sum(StockCode.count_unused(p.id) for p in products)
    text = (
        f"🔧 <b>ADMIN PANEL</b>\n\n"
        f"👤 Users: <b>{total_users}</b> | "
        f"📦 Products: <b>{len(products)}</b> | "
        f"🎫 Codes: <b>{total_codes}</b>\n\n"
        f"Choose option:"
    )
    await query.edit_message_text(text, reply_markup=admin_panel_kb(), parse_mode="HTML")


async def admin_add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return await answer_cb(query.id, "❌ Access Denied!", True)
    await answer_cb(query.id)
    context.user_data['awaiting_add_name'] = True
    await query.edit_message_text(
        "📦 <b>Add Product - Step 1/3</b>\n\n📝 Product name bhejo:",
        reply_markup=back_kb("admin_panel"), parse_mode="HTML")


async def admin_add_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    text = update.message.text.strip()

    if context.user_data.get('awaiting_add_name'):
        context.user_data['add_name'] = text
        context.user_data['awaiting_add_name'] = False
        context.user_data['awaiting_add_price'] = True
        await send_msg(user_id,
            f"📦 <b>Add Product - Step 2/3</b>\n\n📝 Name: <b>{text}</b>\n\n💰 Price (per code) bhejo:",
            back_kb("admin_panel"))

    elif context.user_data.get('awaiting_add_price'):
        try:
            price = float(text)
        except:
            return await send_msg(user_id, "❌ Valid price likho!")
        context.user_data['add_price'] = price
        context.user_data['awaiting_add_price'] = False
        context.user_data['awaiting_add_desc'] = True
        await send_msg(user_id,
            f"📦 <b>Add Product - Step 3/3</b>\n\n📝 Name: <b>{context.user_data['add_name']}</b>\n💰 Price: <b>{price}</b>\n\n📄 Description bhejo (ya 'skip' likho):",
            back_kb("admin_panel"))

    elif context.user_data.get('awaiting_add_desc'):
        desc = text if text.lower() != "skip" else "No description"
        name = context.user_data['add_name']
        price = context.user_data['add_price']
        product = Product(name=name, description=desc, price=price, category="General", stock=0, status="active")
        product.save()
        context.user_data.pop('awaiting_add_desc', None)
        context.user_data.pop('add_name', None)
        context.user_data.pop('add_price', None)
        context.user_data['awaiting_add_codes'] = product.id
        await send_msg(user_id,
            f"✅ <b>Product Created!</b>\n\n📝 Name: <b>{name}</b>\n💰 Price: <b>{price}</b>\n\n🎫 Ab codes paste karo (har line pe ek code/link).\n<b>/done</b> jab finish ho.",
            back_kb("admin_panel"))

    elif context.user_data.get('awaiting_add_codes'):
        product_id = context.user_data['awaiting_add_codes']
        product = Product.get(product_id)
        if not product:
            return
        if text == "/done":
            sc = StockCode.count_unused(product.id)
            product.stock = sc
            product.save()
            context.user_data.pop('awaiting_add_codes', None)
            await send_msg(user_id,
                f"🎉 <b>Product Ready!</b>\n\n📝 Name: <b>{product.name}</b>\n💰 Price: <b>{product.price}</b>\n🎫 Codes: <b>{sc}</b>",
                admin_panel_kb())
            return
        codes = [c.strip() for c in text.split("\n") if c.strip()]
        if codes:
            StockCode.add_bulk(product.id, codes)
            sc = StockCode.count_unused(product.id)
            await send_msg(user_id,
                f"✅ <b>{len(codes)} codes added!</b> Total: {sc}\n\nAur codes ho toh paste karo, /done for finish.")

    elif context.user_data.get('awaiting_stock_add'):
        product_id = context.user_data['awaiting_stock_add']
        product = Product.get(product_id)
        if not product:
            return
        if text == "/done":
            sc = StockCode.count_unused(product.id)
            product.stock = sc
            product.save()
            context.user_data.pop('awaiting_stock_add', None)
            await send_msg(user_id, f"✅ <b>Stock Updated!</b> Total codes: {sc}", admin_panel_kb())
            return
        codes = [c.strip() for c in text.split("\n") if c.strip()]
        if codes:
            StockCode.add_bulk(product.id, codes)
            sc = StockCode.count_unused(product.id)
            await send_msg(user_id, f"✅ <b>{len(codes)} codes added!</b> Total: {sc}\n\nAur codes ho toh paste karo, /done for finish.")

    elif context.user_data.get('awaiting_broadcast'):
        context.user_data['awaiting_broadcast'] = False
        users = User.get_all()
        success = 0
        failed = 0
        for uid in users:
            try:
                from bot.services.api_helpers import send_msg as sm
                await sm(uid, text)
                success += 1
            except:
                failed += 1
        await send_msg(user_id, f"📢 <b>Broadcast Done!</b>\n\nSent: {success}\nFailed: {failed}", admin_panel_kb())


async def admin_products_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return await answer_cb(query.id, "❌ Access Denied!", True)
    await answer_cb(query.id)
    products = Product.get_all()
    if not products:
        return await query.edit_message_text("📦 Koi product nahi hai.",
            reply_markup=back_kb("admin_panel"), parse_mode="HTML")
    buttons = []
    for p in products:
        sc = StockCode.count_unused(p.id)
        buttons.append([sbtn(f"📦 {p.name} [{sc} codes]", f"admin_prod_{p.id}", "primary", ICON["cart"])])
    buttons.append([sbtn("🔙 Back", "admin_panel", "danger", ICON["back"])])
    await query.edit_message_text("📦 <b>Products</b>", reply_markup={"inline_keyboard": buttons}, parse_mode="HTML")


async def admin_product_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return await answer_cb(query.id, "❌ Access Denied!", True)
    await answer_cb(query.id)
    product_id = int(query.data.split("_")[2])
    product = Product.get(product_id)
    if not product:
        return await answer_cb(query.id, "❌ Product not found!", True)
    sc = StockCode.count_unused(product.id)
    buttons = [
        [sbtn("➕ Add Codes", f"admin_stockadd_{product.id}", "success", ICON["star"]),
         sbtn("📤 Export", f"admin_stockexport_{product.id}", "primary", ICON["download"])],
        [sbtn("🗑️ Withdraw", f"admin_stockwithdraw_{product.id}", "danger", ICON["danger"])],
        [sbtn("🔙 Back", "admin_products", "danger", ICON["back"])]
    ]
    await query.edit_message_text(
        f"📦 <b>{product.name}</b>\n\n"
        f"💰 Price: <b>{product.price}/code</b>\n"
        f"🎫 Stock: <b>{sc} codes</b>\n"
        f"📄 Description: <b>{product.description}</b>",
        reply_markup={"inline_keyboard": buttons}, parse_mode="HTML")


async def admin_stock_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return await answer_cb(query.id, "❌ Access Denied!", True)
    await answer_cb(query.id)
    products = Product.get_all()
    if not products:
        return await query.edit_message_text("📦 Koi product nahi hai.",
            reply_markup=back_kb("admin_panel"), parse_mode="HTML")
    buttons = []
    for p in products:
        sc = StockCode.count_unused(p.id)
        buttons.append([sbtn(f"📦 {p.name} [{sc} codes]", f"admin_stock_{p.id}", "primary", ICON["cart"])])
    buttons.append([sbtn("🔙 Back", "admin_panel", "danger", ICON["back"])])
    await query.edit_message_text("📦 <b>Stock Management</b>\n\nProduct select karo:",
        reply_markup={"inline_keyboard": buttons}, parse_mode="HTML")


async def admin_stock_product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return await answer_cb(query.id, "❌ Access Denied!", True)
    await answer_cb(query.id)
    product_id = int(query.data.split("_")[2])
    product = Product.get(product_id)
    if not product:
        return
    sc = StockCode.count_unused(product.id)
    buttons = [
        [sbtn("➕ Add Codes", f"admin_stockadd_{product.id}", "success", ICON["star"]),
         sbtn("📤 Export", f"admin_stockexport_{product.id}", "primary", ICON["download"])],
        [sbtn("🗑️ Withdraw", f"admin_stockwithdraw_{product.id}", "danger", ICON["danger"])],
        [sbtn("🔙 Back", "admin_stock", "danger", ICON["back"])]
    ]
    await query.edit_message_text(
        f"📦 <b>{product.name}</b>\n\n🎫 Codes: <b>{sc}</b>\n💰 Price: <b>{product.price}</b>",
        reply_markup={"inline_keyboard": buttons}, parse_mode="HTML")


async def admin_stock_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return await answer_cb(query.id, "❌ Access Denied!", True)
    await answer_cb(query.id)
    product_id = int(query.data.split("_")[2])
    context.user_data['awaiting_stock_add'] = product_id
    await query.edit_message_text(
        "🎫 <b>Codes paste karo</b>\n\nHar line pe ek code/link.\n<b>/done</b> jab finish.",
        reply_markup=back_kb("admin_stock"), parse_mode="HTML")


async def admin_stock_export_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return await answer_cb(query.id, "❌ Access Denied!", True)
    await answer_cb(query.id)
    product_id = int(query.data.split("_")[2])
    product = Product.get(product_id)
    if not product:
        return
    codes = StockCode.export_all(product.id)
    if not codes:
        return await answer_cb(query.id, "❌ Koi codes nahi hain!", True)
    file_content = f"📦 Product : {product.name}\n🎫 Count   : {len(codes)}\n{'-'*30}\n"
    file_content += "\n".join(codes)
    file_content += f"\n{'-'*30}\n"
    await send_doc(query.from_user.id, file_content, f"{product.name}_codes.txt",
                   f"📤 <b>Export</b> - {len(codes)} codes")


async def admin_stock_withdraw_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return await answer_cb(query.id, "❌ Access Denied!", True)
    await answer_cb(query.id)
    product_id = int(query.data.split("_")[2])
    product = Product.get(product_id)
    if not product:
        return
    sc = StockCode.count_unused(product.id)
    await query.edit_message_text(
        f"🗑️ <b>Withdraw Codes</b>\n\n📦 Product: <b>{product.name}</b>\n🎫 Available: <b>{sc}</b>\n\nKitne withdraw karna hai? Number likho.",
        reply_markup=back_kb("admin_stock"), parse_mode="HTML")
    context.user_data['awaiting_withdraw_qty'] = product_id


async def admin_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return await answer_cb(query.id, "❌ Access Denied!", True)
    await answer_cb(query.id)
    users = User.get_all()
    text = f"👤 <b>All Users</b>\n\nTotal: {len(users)}\n\n"
    for uid in users[:20]:
        u = User.get(uid)
        if u:
            text += f"<code>{u.user_id}</code> - {u.first_name or 'N/A'} | Bal: {u.wallet_balance}\n"
    await query.edit_message_text(text, reply_markup=back_kb("admin_panel"), parse_mode="HTML")


async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return await answer_cb(query.id, "❌ Access Denied!", True)
    await answer_cb(query.id)
    users = User.count()
    products = Product.get_all()
    total_codes = sum(StockCode.count_unused(p.id) for p in products)
    text = f"📊 <b>Statistics</b>\n\n👤 Users: {users}\n📦 Products: {len(products)}\n🎫 Total Codes: {total_codes}"
    await query.edit_message_text(text, reply_markup=back_kb("admin_panel"), parse_mode="HTML")


async def admin_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return await answer_cb(query.id, "❌ Access Denied!", True)
    await answer_cb(query.id)
    context.user_data['awaiting_broadcast'] = True
    await query.edit_message_text(
        "📢 <b>Broadcast</b>\n\nMessage bhejo jo sab users ko jayega.",
        reply_markup=back_kb("admin_panel"), parse_mode="HTML")


async def admin_force_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return await answer_cb(query.id, "❌ Access Denied!", True)
    await answer_cb(query.id)
    current = settings.FORCE_JOIN_CHANNEL or "Not Set"
    buttons = [
        [sbtn("✅ Set Channel", "admin_set_channel", "success", ICON["star"])],
        [sbtn("❌ Disable", "admin_disable_channel", "danger", ICON["danger"])],
        [sbtn("🔙 Back", "admin_panel", "danger", ICON["back"])]
    ]
    await query.edit_message_text(
        f"🔒 <b>Force Channel Settings</b>\n\nCurrent: <b>{current}</b>",
        reply_markup={"inline_keyboard": buttons}, parse_mode="HTML")


async def admin_set_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return await answer_cb(query.id, "❌ Access Denied!", True)
    await answer_cb(query.id)
    context.user_data['awaiting_set_channel'] = True
    await query.edit_message_text(
        "🔒 <b>Channel username bhejo</b>\n\nExample: @channelname",
        reply_markup=back_kb("admin_force_channel"), parse_mode="HTML")


async def admin_disable_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return await answer_cb(query.id, "❌ Access Denied!", True)
    await answer_cb(query.id)
    settings.FORCE_JOIN_CHANNEL = ""
    await query.edit_message_text("✅ <b>Force join disabled!</b>",
        reply_markup=back_kb("admin_panel"), parse_mode="HTML")


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    text = update.message.text.strip()

    if text == "/done":
        if context.user_data.get('awaiting_stock_add'):
            product_id = context.user_data['awaiting_stock_add']
            product = Product.get(product_id)
            if product:
                sc = StockCode.count_unused(product.id)
                product.stock = sc
                product.save()
            context.user_data.pop('awaiting_stock_add', None)
            await send_msg(user_id, f"✅ <b>Stock Updated!</b> Total codes: {sc}", admin_panel_kb())
            return

    if context.user_data.get('awaiting_withdraw_qty'):
        product_id = context.user_data['awaiting_withdraw_qty']
        try:
            qty = int(text)
        except:
            return await send_msg(user_id, "❌ Valid number likho!")
        product = Product.get(product_id)
        if not product:
            return
        withdrawn = StockCode.withdraw(product.id, qty)
        sc = StockCode.count_unused(product.id)
        product.stock = sc
        product.save()
        context.user_data.pop('awaiting_withdraw_qty', None)
        await send_msg(user_id, f"✅ <b>{withdrawn} Codes Withdrawn!</b>\n🎫 Remaining: {sc}", admin_panel_kb())
        return

    if context.user_data.get('awaiting_set_channel'):
        channel = text.replace("@", "").replace("https://t.me/", "").strip()
        if not channel:
            return await send_msg(user_id, "❌ Channel username dalo!")
        settings.FORCE_JOIN_CHANNEL = channel
        from bot.database.database import db
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                   ("force_join_channel", channel))
        context.user_data.pop('awaiting_set_channel', None)
        await send_msg(user_id, f"✅ <b>Force Channel Set!</b>\n\n@{channel}", admin_panel_kb())
        return

    if context.user_data.get('awaiting_stock_add'):
        product_id = context.user_data['awaiting_stock_add']
        product = Product.get(product_id)
        if not product:
            return
        # Guard: reject text that looks like channel/URL (not a code)
        if text.startswith("@") or "t.me/" in text:
            return await send_msg(user_id, "❌ Ye channel username hai, code nahi!\nCode paste karo ya /done dabao.")
        codes = [c.strip() for c in text.split("\n") if c.strip()]
        if codes:
            StockCode.add_bulk(product.id, codes)
            sc = StockCode.count_unused(product.id)
            await send_msg(user_id, f"✅ <b>{len(codes)} codes added!</b> Total: {sc}\n\nAur codes ho toh paste karo, /done for finish.")
        return

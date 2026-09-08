from bot.services.api_helpers import sbtn, sbtn_url, ICON


def main_menu_kb():
    return {"inline_keyboard": [
        [sbtn("🛒 Products", "buy_products", "primary", ICON["cart"]),
         sbtn("📋 My Orders", "my_orders", "success", ICON["order"])],
        [sbtn("💰 Wallet", "wallet", "success", ICON["wallet"])],
        [sbtn("📞 Support", "support", "danger", ICON["support"])]
    ]}


def back_kb(callback="main_menu"):
    return {"inline_keyboard": [[sbtn("🔙 Back", callback, "danger", ICON["back"])]]}


def product_detail_kb(product, qty=1):
    total = product.price * qty
    return {"inline_keyboard": [
        [sbtn("➖", f"qty_dec_{product.id}", "danger"),
         sbtn(f"🔢 Qty: {qty}", "qty_info", "primary"),
         sbtn("➕", f"qty_inc_{product.id}", "success")],
        [sbtn("+5", f"qty_set_{product.id}_5", "primary"),
         sbtn("+10", f"qty_set_{product.id}_10", "primary"),
         sbtn("+50", f"qty_set_{product.id}_50", "primary")],
        [sbtn("✏️ Custom Qty", f"qty_custom_{product.id}", "primary")],
        [sbtn(f"🛒 Buy {qty} Code = {total}", f"place_order_{product.id}", "success", ICON["star"])],
        [sbtn("🔙 Back", "buy_products", "danger", ICON["back"])]
    ]}


def deposit_kb():
    return {"inline_keyboard": [
        [sbtn("✅ Check Payment", "check_deposit", "success", ICON["success"])],
        [sbtn("🔙 Back", "wallet", "danger", ICON["back"])]
    ]}


def admin_panel_kb():
    return {"inline_keyboard": [
        [sbtn("📦 Add Product", "admin_add_product", "success", ICON["star"])],
        [sbtn("📦 Products", "admin_products", "primary", ICON["cart"]),
         sbtn("🎫 Stock", "admin_stock", "primary", ICON["download"])],
        [sbtn("👤 Users", "admin_users", "primary", ICON["users"]),
         sbtn("📊 Stats", "admin_stats", "success", ICON["chart"])],
        [sbtn("📢 Broadcast", "admin_broadcast", "primary", ICON["broadcast"])],
        [sbtn("🔒 Force Channel", "admin_force_channel", "primary", ICON["support"])]
    ]}

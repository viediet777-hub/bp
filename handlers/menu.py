from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import ORDER_FEE, WALLET_MIN, WALLET_MAX


def btn(text, cb=None, url=None):
    b = {"text": text}
    if cb:
        b["callback_data"] = cb
    if url:
        b["url"] = url
    return b


def mk(rows):
    return InlineKeyboardMarkup(rows)


# ═══════════════════════════════════════════════════════════════
# MAIN MENU
# ═══════════════════════════════════════════════════════════════

def main_menu(user):
    w = user.get("wallet", 0) if user else 0
    text = (
        f"<b>SHOP</b>\n"
        f"{'='*28}\n"
        f"Wallet: <b>₹{w}</b>\n"
        f"Order Fee: ₹{ORDER_FEE}\n"
    )
    rows = [
        [btn("Browse Products", "browse"), btn("Search Price", "search")],
        [btn("My Cart", "cart"), btn("My Orders", "orders")],
        [btn("My Account", "account"), btn("Add Wallet", "wallet")],
    ]
    return text, mk(rows)


# ═══════════════════════════════════════════════════════════════
# BROWSE - paste link to check price
# ═══════════════════════════════════════════════════════════════

def browse_menu():
    text = (
        f"<b>BROWSE PRODUCTS</b>\n"
        f"{'='*28}\n\n"
        f"Product ka link daalo\n"
        f"Price automatically dikhega\n\n"
        f"<i>Example:</i>\n"
        f"<code>https://example.com/product/123</code>"
    )
    rows = [
        [btn("Paste Link Above", cb="noop")],
        [btn("Back", "back")],
    ]
    return text, mk(rows)


def price_result(title, price, original=None, url=None):
    text = (
        f"<b>PRICE FOUND</b>\n"
        f"{'='*28}\n\n"
        f"<b>{title}</b>\n"
        f"Selling Price: <b>₹{price}</b>\n"
    )
    if original and original != price:
        text += f"Original: ₹{original}\n"
    rows = [
        [btn("Add to Cart", cb=f"addurl_{url or ''}")],
        [btn("Check Another", "browse"), btn("Back", "back")],
    ]
    return text, mk(rows)


# ═══════════════════════════════════════════════════════════════
# MY ACCOUNT - only view + delete
# ═══════════════════════════════════════════════════════════════

def account_menu(user):
    text = (
        f"<b>MY ACCOUNT</b>\n"
        f"{'='*28}\n\n"
        f"Name: {user.get('name') or 'Not set'}\n"
        f"Phone: <code>{user.get('phone') or 'Not set'}</code>\n"
        f"Address: {user.get('address') or 'Not set'}\n"
        f"Wallet: <b>₹{user.get('wallet', 0)}</b>"
    )
    rows = [
        [btn("Delete Account", "acc_delete")],
        [btn("Back", "back")],
    ]
    return text, mk(rows)


def delete_confirm():
    text = (
        f"<b>DELETE ACCOUNT?</b>\n"
        f"{'='*28}\n\n"
        f"Ye sab delete ho jayega:\n"
        f"- Account info\n"
        f"- Cart items\n"
        f"- Wallet balance\n"
        f"- Order history\n\n"
        f"<b>Confirm karo:</b>"
    )
    rows = [
        [btn("Yes, Delete", "acc_delete_yes"), btn("No, Cancel", "account")],
    ]
    return text, mk(rows)


# ═══════════════════════════════════════════════════════════════
# CART
# ═══════════════════════════════════════════════════════════════

def cart_view(cart_items, user):
    if not cart_items:
        text = (
            f"<b>MY CART</b>\n"
            f"{'='*28}\n\n"
            f"Cart is empty!"
        )
        rows = [[btn("Browse Products", "browse"), btn("Back", "back")]]
        return text, mk(rows)

    subtotal = sum(c.get("price", 0) * c.get("qty", 1) for c in cart_items)
    total = subtotal + ORDER_FEE
    w = user.get("wallet", 0)

    text = f"<b>MY CART</b>\n{'='*28}\n\n"
    for c in cart_items:
        name = c.get("name", "Item")
        price = c.get("price", 0)
        qty = c.get("qty", 1)
        text += f"{name} x{qty} = ₹{price * qty}\n"

    text += (
        f"\n{'='*28}\n"
        f"Subtotal: ₹{subtotal}\n"
        f"Fee: ₹{ORDER_FEE}\n"
        f"Total: <b>₹{total}</b>\n"
        f"Wallet: ₹{w}\n"
    )

    rows = []
    for c in cart_items:
        cid = c["id"]
        name = c.get("name", "?")[:15]
        qty = c.get("qty", 1)
        rows.append([
            btn("-", cb=f"cd_{cid}"),
            btn(f"{name} x{qty}", cb=f"ci_{cid}"),
            btn("+", cb=f"ci_{cid}")
        ])
    rows.append([btn("Clear Cart", "cclear")])
    rows.append([btn("Place Order", "placeorder")])
    rows.append([btn("Back", "back")])
    return text, mk(rows)


# ═══════════════════════════════════════════════════════════════
# ORDERS
# ═══════════════════════════════════════════════════════════════

def orders_list(orders):
    if not orders:
        text = f"<b>MY ORDERS</b>\n{'='*28}\n\nNo orders yet!"
        rows = [[btn("Browse Products", "browse"), btn("Back", "back")]]
        return text, mk(rows)

    text = f"<b>MY ORDERS</b>\n{'='*28}\n\n"
    rows = []
    for o in orders[:10]:
        st = {"pending": "⏳", "confirmed": "✅", "delivered": "📦"}.get(o["status"], "❓")
        text += f"#{o['id']} | ₹{o['total']} | {st} {o['status']}\n"
        rows.append([btn(f"Order #{o['id']}", cb=f"ord_{o['id']}")])
    rows.append([btn("Back", "back")])
    return text, mk(rows)


def order_detail(o):
    text = (
        f"<b>ORDER #{o['id']}</b>\n"
        f"{'='*28}\n\n"
        f"Items: {o['items']}\n"
        f"Total: ₹{o['total']}\n"
        f"Fee: ₹{o['fee']}\n"
        f"Status: {o['status']}\n"
        f"Address: {o.get('address') or 'N/A'}\n"
    )
    rows = [[btn("Back", "orders")]]
    return text, mk(rows)


# ═══════════════════════════════════════════════════════════════
# WALLET
# ═══════════════════════════════════════════════════════════════

def wallet_menu(user, txs=None):
    w = user.get("wallet", 0)
    text = (
        f"<b>ADD WALLET</b>\n"
        f"{'='*28}\n\n"
        f"Balance: <b>₹{w}</b>\n"
        f"Order Fee: ₹{ORDER_FEE}/order\n\n"
        f"Amount choose karo:"
    )
    rows = [
        [btn("₹5", "w5"), btn("₹10", "w10"), btn("₹25", "w25")],
        [btn("₹50", "w50"), btn("₹100", "w100")],
        [btn("Custom Amount", "wcustom")],
    ]
    if txs:
        text += f"\n<b>Recent:</b>\n"
        for t in txs[:5]:
            s = "✅" if t["status"] == "completed" else "⏳"
            text += f"  {s} ₹{t['amount']} - {t['status']}\n"
    rows.append([btn("Back", "back")])
    return text, mk(rows)


def payment_screen(amount, txn_id, qr_url, upi_link):
    text = (
        f"<b>PAY ₹{amount}</b>\n"
        f"{'='*28}\n\n"
        f"Order ID: <code>{txn_id}</code>\n\n"
        f"QR scan karo ya UPI link use karo\n"
        f"<b>Exact amount pay karo</b>\n\n"
        f"Payment ke baad <b>Verify</b> dabao"
    )
    rows = [
        [btn("Verify Payment", cb=f"vp_{txn_id}")],
        [btn("Cancel", "wallet")],
    ]
    return text, qr_url, rows


def verifying_screen(amount, txn_id):
    text = (
        f"<b>VERIFYING PAYMENT...</b>\n"
        f"{'='*28}\n\n"
        f"Amount: ₹{amount}\n"
        f"Order ID: <code>{txn_id}</code>\n\n"
        f"<i>Payment check ho raha hai...</i>\n"
        f"Thoda wait karo"
    )
    rows = [
        [btn("Check Again", cb=f"vp_{txn_id}")],
        [btn("Cancel", "wallet")],
    ]
    return text, mk(rows)

"""
app.py - Flask Backend for Mini App
Products, Cart, Orders, Wallet - sab API yahan se
"""
import json
import time
from flask import Flask, render_template, request, jsonify
from database import (
    get_user, create_user, update_user, delete_user, add_wallet, deduct_wallet,
    get_products, get_product, add_product, update_stock,
    get_cart, add_to_cart, update_cart_qty, clear_cart,
    create_order, get_orders, get_order,
    create_wallet_tx, get_wallet_tx,
)
from gateway import generate_txn_id, create_upi_link, get_qr_url, verify_payment
from config import ORDER_FEE, WALLET_MIN, WALLET_MAX, GW_UPI_ID, GW_UPI_NAME

app = Flask(__name__)


def get_uid():
    """Get user_id from request header"""
    return int(request.headers.get("X-User-Id", 0))


# ═══════════════════════════════════════════════════════════════
# PAGES
# ═══════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


# ═══════════════════════════════════════════════════════════════
# USER API
# ═══════════════════════════════════════════════════════════════

@app.route("/api/user", methods=["GET"])
def api_user():
    uid = get_uid()
    if not uid:
        return jsonify({"error": "no user"}), 400
    user = get_user(uid)
    if not user:
        user = create_user(uid)
    return jsonify(user)


@app.route("/api/user", methods=["POST"])
def api_update_user():
    uid = get_uid()
    data = request.json
    update_user(uid, **data)
    return jsonify({"ok": True})


@app.route("/api/user/delete", methods=["POST"])
def api_delete_user():
    uid = get_uid()
    delete_user(uid)
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════════
# PRODUCTS API
# ═══════════════════════════════════════════════════════════════

@app.route("/api/products")
def api_products():
    cat = request.args.get("category")
    q = request.args.get("q")
    products = get_products(category=cat, search=q)
    return jsonify(products)


@app.route("/api/products/<int:pid>")
def api_product(pid):
    p = get_product(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    return jsonify(p)


# ═══════════════════════════════════════════════════════════════
# CART API
# ═══════════════════════════════════════════════════════════════

@app.route("/api/cart")
def api_cart():
    uid = get_uid()
    cart = get_cart(uid)
    return jsonify(cart)


@app.route("/api/cart/add", methods=["POST"])
def api_cart_add():
    uid = get_uid()
    data = request.json
    pid = data.get("product_id")
    qty = data.get("qty", 1)
    add_to_cart(uid, pid, qty)
    return jsonify({"ok": True})


@app.route("/api/cart/update", methods=["POST"])
def api_cart_update():
    uid = get_uid()
    data = request.json
    cid = data.get("cart_id")
    qty = data.get("qty", 1)
    update_cart_qty(cid, qty)
    return jsonify({"ok": True})


@app.route("/api/cart/clear", methods=["POST"])
def api_cart_clear():
    uid = get_uid()
    clear_cart(uid)
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════════
# ORDERS API
# ═══════════════════════════════════════════════════════════════

@app.route("/api/orders")
def api_orders():
    uid = get_uid()
    orders = get_orders(uid)
    return jsonify(orders)


@app.route("/api/orders/place", methods=["POST"])
def api_place_order():
    uid = get_uid()
    user = get_user(uid)
    cart = get_cart(uid)

    if not cart:
        return jsonify({"error": "cart empty"}), 400

    subtotal = sum(c.get("price", 0) * c.get("qty", 1) for c in cart)
    total = subtotal + ORDER_FEE
    w = user.get("wallet", 0)

    if w < total:
        return jsonify({"error": "insufficient wallet", "needed": total - w}), 400

    items_str = ", ".join([f"{c.get('name','?')}x{c.get('qty',1)}" for c in cart])
    deduct_wallet(uid, total)
    oid = create_order(uid, items_str, total, ORDER_FEE, user.get("address", ""))

    for c in cart:
        if c.get("product_id"):
            update_stock(c["product_id"], c.get("qty", 1))
    clear_cart(uid)

    return jsonify({"ok": True, "order_id": oid, "total": total})


# ═══════════════════════════════════════════════════════════════
# WALLET API
# ═══════════════════════════════════════════════════════════════

@app.route("/api/wallet")
def api_wallet():
    uid = get_uid()
    user = get_user(uid)
    txs = get_wallet_tx(uid)
    return jsonify({"balance": user.get("wallet", 0), "transactions": txs})


@app.route("/api/wallet/create", methods=["POST"])
def api_wallet_create():
    uid = get_uid()
    data = request.json
    amount = int(data.get("amount", 0))

    if amount < WALLET_MIN or amount > WALLET_MAX:
        return jsonify({"error": f"Amount ₹{WALLET_MIN}-₹{WALLET_MAX}"}), 400

    txn_id = generate_txn_id(uid)
    upi_link = create_upi_link(txn_id, amount)
    qr_url = get_qr_url(upi_link)

    create_wallet_tx(uid, amount, txn_id)

    return jsonify({
        "ok": True,
        "txn_id": txn_id,
        "amount": amount,
        "qr_url": qr_url,
        "upi_link": upi_link,
        "upi_id": GW_UPI_ID,
    })


@app.route("/api/wallet/verify", methods=["POST"])
def api_wallet_verify():
    uid = get_uid()
    data = request.json
    txn_id = data.get("txn_id")

    result = verify_payment(txn_id)
    status = str(result.get("status", "")).lower()

    if result["success"] and status in ("success", "completed", "captured", "paid", "1"):
        from database import get_db
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM wallet_tx WHERE txn_id=? AND status='pending'",
            (txn_id,)).fetchone()
        if row:
            conn.execute("UPDATE wallet_tx SET status='completed' WHERE id=?", (row["id"],))
            conn.execute("UPDATE users SET wallet=wallet+? WHERE user_id=?",
                         (row["amount"], row["user_id"]))
            conn.commit()
            conn.close()
            return jsonify({"ok": True, "status": "completed", "amount": row["amount"]})
        conn.close()
        return jsonify({"ok": True, "status": "already_verified"})

    return jsonify({"ok": False, "status": status, "message": "Payment not found"})


# ═══════════════════════════════════════════════════════════════
# ADMIN API
# ═══════════════════════════════════════════════════════════════

@app.route("/api/admin/products", methods=["POST"])
def api_admin_add_product():
    data = request.json
    pid = add_product(
        name=data.get("name", ""),
        price=int(data.get("price", 0)),
        stock=int(data.get("stock", 0)),
        desc=data.get("description", ""),
        category=data.get("category", ""),
        image=data.get("image_url", ""),
    )
    return jsonify({"ok": True, "product_id": pid})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

"""
app.py - Flask Backend for Mini App
Products, Cart, Orders, Wallet, Meesho - sab API yahan se
"""
import json
import os
import time
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from database import (
    get_user, create_user, update_user, delete_user, add_wallet, deduct_wallet,
    get_products, get_product, add_product, update_stock,
    get_cart, add_to_cart, update_cart_qty, clear_cart,
    create_order, get_orders, get_order,
    create_wallet_tx, get_wallet_tx,
    save_meesho_account, get_meesho_accounts, get_active_meesho_account,
    delete_meesho_account, update_meesho_xo,
    save_user_offer, get_user_offer,
    get_addresses, get_address, create_address, update_address,
    delete_address, set_default_address, get_default_address,
    toggle_user_mode, get_user_mode, get_global_mode, set_global_mode, get_order_count,
    get_cart_session, set_cart_session,
    get_all_users,
)
from gateway import generate_txn_id, create_upi_link, get_qr_url, verify_payment
from config import ORDER_FEE, WALLET_MIN, WALLET_MAX, GW_UPI_ID, GW_UPI_NAME, ADMIN_IDS
from meesho import (
    get_meesho_offer, search_meesho, get_meesho_product, send_otp, verify_otp, check_number,
    real_cart_add, real_cart_add_many, real_cart_review, real_cart_clear, real_cart_sync, real_cart_remove,
    real_bind_address, real_paymentinfo, real_address_create, real_fetch_addresses,
    real_preorder, real_payment_status, real_preorder_status, real_payment_options,
    fresh_checkout_state, roll_fod_sync,
)

app = Flask(__name__)

CORS(app, resources={r"/api/*": {"origins": "*"}})
CORS(app, resources={r"/": {"origins": "*"}})

@app.before_request
def log_request():
    import sys
    print(f"[REQ] {request.method} {request.path} from {request.remote_addr}", flush=True, file=sys.stderr)


def get_uid():
    """Get user_id from request header"""
    uid = request.headers.get("X-User-Id", "0")
    try:
        return int(uid)
    except (ValueError, TypeError):
        return uid


def _int0(v):
    """Coerce a JSON value to int, treating null/''/garbage as 0."""
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return 0


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


@app.route("/api/mode")
def api_get_mode():
    uid = get_uid()
    mode = get_global_mode()
    return jsonify({"mode": mode})


@app.route("/api/mode/toggle", methods=["POST"])
def api_toggle_mode():
    uid = get_uid()
    if not uid:
        return jsonify({"ok": False, "error": "login required"})
    if uid not in ADMIN_IDS:
        return jsonify({"ok": False, "error": "admin only"})
    new_mode = toggle_user_mode(uid)
    return jsonify({"ok": True, "mode": new_mode})


@app.route("/api/meesho/addresses")
def api_meesho_addresses():
    uid = get_uid()
    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"addresses": []})
    addrs = real_fetch_addresses(acc)
    return jsonify({"addresses": addrs})


@app.route("/api/cart/sync", methods=["POST"])
def api_cart_sync():
    uid = get_uid()
    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"ok": False, "error": "no account"})
    cart = get_cart(uid)
    if not cart:
        return jsonify({"ok": True, "message": "cart empty"})
    cs = get_cart_session(uid)
    # Push all items to real Meesho cart
    valid_items = [c for c in cart if c.get("product_id")]
    if valid_items:
        # Clear existing
        existing = real_cart_review(acc, cs)
        if existing.get("ok") and existing.get("items"):
            for ei in existing["items"]:
                if ei.get("identifier") and existing.get("cart_session"):
                    real_cart_remove(acc, ei["identifier"], existing["cart_session"])
        # Add all items
        add_r = real_cart_add_many(acc, valid_items, cs or "")
        if add_r.get("ok"):
            cs = add_r.get("cart_session", cs)
            set_cart_session(uid, cs)
    return jsonify({"ok": True, "cart_session": cs})


@app.route("/api/orders/count")
def api_order_count():
    uid = get_uid()
    if not uid:
        return jsonify({"count": 0})
    count = get_order_count(uid)
    return jsonify({"count": count})


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
    name = data.get("name", "")
    price = int(data.get("price", 0))
    image = data.get("image", "")
    source = data.get("source", "local")
    supplier_id = _int0(data.get("supplier_id"))
    variation_id = _int0(data.get("variation_id"))
    variation_name = data.get("variation_name", "Free Size")
    mrp = int(data.get("mrp", price))
    add_to_cart(uid, pid, qty, name=name, price=price, image=image, source=source,
                supplier_id=supplier_id, variation_id=variation_id,
                variation_name=variation_name, mrp=mrp)
    # Sync to real Meesho cart immediately
    acc = get_active_meesho_account(uid)
    synced, reason = False, ""
    if not acc:
        reason = "no_account"
    elif not supplier_id or not variation_id:
        # Without both ids Meesho rejects the item, so the local cart row would
        # never have a real counterpart. Surface it instead of failing silently.
        reason = "missing_supplier_or_variation"
    else:
        cs = get_cart_session(uid)
        r = real_cart_add(acc, pid, supplier_id, variation_id, variation_name, qty, cs)
        if r.get("ok"):
            synced = True
            if r.get("cart_session"):
                set_cart_session(uid, r["cart_session"])
        else:
            reason = str(r.get("error") or "cart_add_failed")[:200]
    return jsonify({"ok": True, "real_cart_synced": synced, "real_cart_error": reason})


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

    data = request.json or {}
    payment_method = data.get("payment_method", "COD").upper()
    address_id = data.get("address_id")

    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"error": "no meesho account linked. Login first."}), 400

    addr = None
    if address_id:
        addr = get_address(address_id)
    if not addr:
        addr = get_default_address(uid)
    if not addr:
        return jsonify({"error": "no address found. Add address first."}), 400

    subtotal = sum(c.get("price", 0) * c.get("qty", 1) for c in cart)
    user_mode = get_global_mode()
    fee = 0 if user_mode == "free" else ORDER_FEE
    our_total = subtotal + fee
    w = user.get("wallet", 0)

    if user_mode == "paid":
        if w < our_total:
            return jsonify({"error": "insufficient wallet", "needed": our_total - w, "balance": w}), 400
        deduct_wallet(uid, our_total)

    # Get persisted cart_session, or sync local cart to real Meesho cart
    cart_session = get_cart_session(uid)

    # Push local cart to real Meesho cart via multi-item add
    valid_items = [c for c in cart if c.get("product_id")]
    if valid_items:
        # Clear any existing real cart items first
        existing_review = real_cart_review(acc, cart_session)
        if existing_review.get("ok") and existing_review.get("items"):
            for ei in existing_review["items"]:
                if ei.get("identifier") and existing_review.get("cart_session"):
                    real_cart_remove(acc, ei["identifier"], existing_review["cart_session"])
        # Push the full bag in one call
        add_r = real_cart_add_many(acc, valid_items, cart_session or "")
        if add_r.get("ok"):
            cart_session = add_r.get("cart_session", cart_session)
            if cart_session:
                set_cart_session(uid, cart_session)

    # Use fresh_checkout_state to run review -> bind -> paymentinfo in one flow
    st = fresh_checkout_state(acc, cart_session, need_paymentinfo=(payment_method != "COD"))
    if not st:
        if user_mode == "paid":
            add_wallet(uid, our_total)
        return jsonify({"error": "Could not load the live Meesho cart."}), 400

    cart_session = st["cs"]
    meesho_amount = st["order_total"] or subtotal
    meesho_addr_id = st["addr"].get("id")
    set_cart_session(uid, cart_session)

    order_r = real_preorder(acc, cart_session, meesho_addr_id,
                            payment_method=payment_method,
                            customer_amount=meesho_amount)

    if not order_r.get("ok"):
        if user_mode == "paid":
            add_wallet(uid, our_total)
        return jsonify({"error": f"Order failed: {order_r.get('error')}",
                        "message": order_r.get("message", ""), "details": order_r}), 400

    meesho_order_num = order_r.get("order_num", "")
    items_str = ", ".join([f"{c.get('name', '?')}x{c.get('qty', 1)}" for c in cart])
    oid = create_order(uid, items_str, our_total, fee, addr.get("address_line_1", ""),
                       meesho_order_num=meesho_order_num, payment_method=payment_method,
                       meesho_amount=meesho_amount)

    clear_cart(uid)
    set_cart_session(uid, "")

    # QR generation: use Meesho's QR first, fallback to our gateway QR
    qr_base64 = order_r.get("qr_base64")
    upi_intent_url = order_r.get("upi_intent_url")
    qr_url = ""
    if payment_method.upper() in ("UPI", "PREPAID") and not qr_base64:
        if upi_intent_url:
            # Meesho returned the intent link but no image (the real app renders
            # the QR client-side via JusPay) -> render it ourselves.
            qr_url = get_qr_url(upi_intent_url)
        else:
            txn_id = generate_txn_id(uid)
            upi_intent_url = create_upi_link(txn_id, meesho_amount)
            qr_url = get_qr_url(upi_intent_url)

    return jsonify({
        "ok": True, "order_id": oid, "meesho_order_num": meesho_order_num,
        "total": our_total, "meesho_amount": meesho_amount,
        "payment_method": payment_method, "mode": user_mode,
        "qr_base64": qr_base64,
        "upi_intent_url": upi_intent_url,
        "qr_url": qr_url,
        "payment_url": order_r.get("payment_url"),
    })


# ═══════════════════════════════════════════════════════════════
# CHECKOUT API - Real Meesho pricing
# ═══════════════════════════════════════════════════════════════

@app.route("/api/checkout/summary")
def api_checkout_summary():
    uid = get_uid()
    cart = get_cart(uid)
    user = get_user(uid)
    if not cart:
        return jsonify({"error": "cart empty"}), 400

    subtotal = sum(c.get("price", 0) * c.get("qty", 1) for c in cart)
    user_mode = get_global_mode()
    fee = 0 if user_mode == "free" else ORDER_FEE
    total = subtotal + fee
    balance = user.get("wallet", 0) if user else 0

    addr = get_default_address(uid)
    acc = get_active_meesho_account(uid)

    cod_amount = subtotal
    upi_amount = subtotal
    payinfo_ok = False

    # Try to get real Meesho prices via cart review + paymentinfo
    if acc:
        cs = get_cart_session(uid)
        if not cs:
            # Push local cart to real Meesho cart first
            valid_items = [c for c in cart if c.get("product_id")]
            if valid_items:
                add_r = real_cart_add_many(acc, valid_items, "")
                if add_r.get("ok"):
                    cs = add_r.get("cart_session")
        if cs:
            # Get real cart review
            review = real_cart_review(acc, cs)
            if review.get("ok"):
                cs = review.get("cart_session", cs)
                set_cart_session(uid, cs)
                real_subtotal = review.get("effective_total") or subtotal
                cod_amount = real_subtotal
                upi_amount = review.get("effective_total_for_upi_plugin") or real_subtotal
                payinfo_ok = True
                # Get real COD amount
                pay_cod = real_paymentinfo(acc, cs, ["cod"])
                if pay_cod.get("ok"):
                    cod_amount = pay_cod.get("effective_total", cod_amount)
                # Get real UPI amount
                pay_upi = real_paymentinfo(acc, cs, ["upi_qr"])
                if pay_upi.get("ok"):
                    upi_amount = pay_upi.get("effective_total_for_upi_plugin") or pay_upi.get("effective_total", upi_amount)

    return jsonify({
        "items": cart,
        "subtotal": subtotal,
        "fee": fee,
        "total": total,
        "cod_amount": cod_amount,
        "upi_amount": upi_amount,
        "balance": balance,
        "mode": user_mode,
        "address": addr,
        "account": {"phone": acc.get("phone"), "user_id": acc.get("meesho_user_id") or acc.get("user_id")} if acc else None,
        "payinfo_ok": payinfo_ok,
    })


@app.route("/api/payment/status", methods=["POST"])
def api_payment_status():
    uid = get_uid()
    data = request.json or {}
    order_num = data.get("order_num")
    juspay_id = data.get("juspay_order_id")
    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"ok": False, "error": "no account"})
    if juspay_id:
        r = real_payment_status(acc, juspay_id)
    elif order_num:
        r = real_preorder_status(acc, order_num, data.get("cart_session", ""))
    else:
        return jsonify({"ok": False, "error": "no order reference"})
    return jsonify(r)


# ═══════════════════════════════════════════════════════════════
# WALLET API
# ═══════════════════════════════════════════════════════════════

@app.route("/api/wallet")
def api_wallet():
    uid = get_uid()
    if not uid:
        return jsonify({"balance": 0, "transactions": []})
    user = get_user(uid) or create_user(uid)
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

@app.route("/api/admin/users")
def api_admin_users():
    uid = get_uid()
    if uid not in ADMIN_IDS:
        return jsonify({"error": "admin only"}), 403
    users = get_all_users()
    return jsonify({"users": users})


@app.route("/api/admin/mode/toggle", methods=["POST"])
def api_admin_toggle_mode():
    uid = get_uid()
    if uid not in ADMIN_IDS:
        return jsonify({"error": "admin only"}), 403
    data = request.json or {}
    target_uid = data.get("user_id")
    if not target_uid:
        return jsonify({"error": "user_id required"}), 400
    new_mode = toggle_user_mode(target_uid)
    return jsonify({"ok": True, "user_id": target_uid, "mode": new_mode})


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


# ═══════════════════════════════════════════════════════════════
# MEESHO API - FOD, Search, Product, OTP
# ═══════════════════════════════════════════════════════════════

_meesho_otp_sessions = {}
_meesho_offer = None


@app.route("/api/fod/roll")
def api_fod_roll():
    global _meesho_offer
    result = get_meesho_offer()
    if result.get("ok") and result.get("offer"):
        _meesho_offer = result["offer"]
    return jsonify(result)


@app.route("/api/offers")
def api_offers():
    global _meesho_offer
    if not _meesho_offer:
        result = get_meesho_offer()
        if result.get("ok") and result.get("offer"):
            _meesho_offer = result["offer"]
    return jsonify({"offer": _meesho_offer})


@app.route("/api/search", methods=["POST"])
def api_meesho_search():
    data = request.json or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"catalogs": []})
    offer = _meesho_offer
    uid = get_uid()
    if uid and offer:
        acc = get_active_meesho_account(uid)
        if acc and not acc.get("is_first_order", 1):
            offer = None
    result = search_meesho(query, offer=offer)
    return jsonify(result or {"catalogs": []})


@app.route("/api/search/suggest", methods=["POST"])
def api_search_suggest():
    data = request.json or {}
    prefix = data.get("prefix", "").strip()[:40]
    if not prefix:
        return jsonify([])
    # Simple suggest from recent/common searches
    suggestions = [
        "fashion trending", "women kurti", "men tshirt", "saree",
        "phone case", "shoes", "watch", "bag", "earring", "kids wear",
        "home decor", "kitchen", "toys", "beauty", "fitness"
    ]
    matches = [s for s in suggestions if prefix.lower() in s.lower()][:5]
    return jsonify([{"text": s} for s in matches])


@app.route("/api/product/by_link", methods=["POST"])
def api_product_by_link():
    import re as _re
    data = request.json or {}
    link = data.get("link", "").strip()
    m = _re.search(r"product/(\d+)", link)
    if not m:
        return jsonify({"error": "bad_link", "message": "Not a valid Meesho product link"})
    pid = m.group(1)
    offer = _meesho_offer
    uid = get_uid()
    if uid and offer:
        acc = get_active_meesho_account(uid)
        if acc and not acc.get("is_first_order", 1):
            offer = None
    result = get_meesho_product(pid, offer=offer)
    if result:
        return jsonify(result)
    return jsonify({"error": "not found"})


@app.route("/api/product")
def api_meesho_product():
    pid = request.args.get("product_id", "")
    if not pid:
        return jsonify({"error": "no product_id"}), 400
    offer = _meesho_offer
    uid = get_uid()
    if uid and offer:
        acc = get_active_meesho_account(uid)
        if acc and not acc.get("is_first_order", 1):
            offer = None
    result = get_meesho_product(pid, offer=offer)
    if result:
        return jsonify(result)
    return jsonify({"error": "not found"}), 404


@app.route("/api/check_number", methods=["POST"])
def api_check_number():
    data = request.json or {}
    phone = str(data.get("phone_number", ""))[-10:]
    if len(phone) < 10:
        return jsonify({"ok": False, "error": "Invalid number"})
    result = check_number(phone)
    registered = result.get("registered", False)
    if registered:
        return jsonify({
            "ok": True, "eligible": True, "live": True,
            "registered": True,
            "title": "Number Registered on Meesho",
            "subtitle": "This number has an existing Meesho account. First-order discount may or may not apply — depends on order history.",
            "duration": 3})
    return jsonify({
        "ok": True, "eligible": False, "live": True,
        "registered": False,
        "title": "Number NOT Registered",
        "subtitle": result.get("error", "This number is not found on Meesho. New account = guaranteed 1st order discount!"),
        "duration": 0})


@app.route("/api/geocode")
def api_geocode():
    """Simple geocode: forward (q -> city/state/pin) and reverse (lat,lng -> city/state/pin)."""
    import math
    q = request.args.get("q", "").strip()
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)

    # Simple India geocode fallback (major cities with pincodes)
    CITIES = [
        {"city": "New Delhi", "state": "Delhi", "pin": "110001", "lat": 28.6139, "lng": 77.2090},
        {"city": "Mumbai", "state": "Maharashtra", "pin": "400001", "lat": 19.0760, "lng": 72.8777},
        {"city": "Bangalore", "state": "Karnataka", "pin": "560001", "lat": 12.9716, "lng": 77.5946},
        {"city": "Chennai", "state": "Tamil Nadu", "pin": "600001", "lat": 13.0827, "lng": 80.2707},
        {"city": "Kolkata", "state": "West Bengal", "pin": "700001", "lat": 22.5726, "lng": 88.3639},
        {"city": "Hyderabad", "state": "Telangana", "pin": "500001", "lat": 17.3850, "lng": 78.4867},
        {"city": "Pune", "state": "Maharashtra", "pin": "411001", "lat": 18.5204, "lng": 73.8567},
        {"city": "Ahmedabad", "state": "Gujarat", "pin": "380001", "lat": 23.0225, "lng": 72.5714},
        {"city": "Jaipur", "state": "Rajasthan", "pin": "302001", "lat": 26.9124, "lng": 75.7873},
        {"city": "Lucknow", "state": "Uttar Pradesh", "pin": "226001", "lat": 26.8467, "lng": 80.9462},
        {"city": "Bhopal", "state": "Madhya Pradesh", "pin": "462001", "lat": 23.2599, "lng": 77.4126},
        {"city": "Patna", "state": "Bihar", "pin": "800001", "lat": 25.6093, "lng": 85.1376},
        {"city": "Indore", "state": "Madhya Pradesh", "pin": "452001", "lat": 22.7196, "lng": 75.8577},
        {"city": "Nagpur", "state": "Maharashtra", "pin": "440001", "lat": 21.1458, "lng": 79.0882},
        {"city": "Chandigarh", "state": "Chandigarh", "pin": "160001", "lat": 30.7333, "lng": 76.7794},
    ]

    def _closest(lat, lng):
        best, best_d = CITIES[0], 9999
        for c in CITIES:
            d = math.sqrt((lat - c["lat"]) ** 2 + (lng - c["lng"]) ** 2)
            if d < best_d:
                best, best_d = c, d
        return best

    results = []
    if lat and lng:
        city = _closest(lat, lng)
        results.append({"formatted": f"{city['city']}, {city['state']} - {city['pin']}",
                        "city": city["city"], "state": city["state"], "pin": city["pin"],
                        "lat": city["lat"], "lng": city["lng"]})
    elif q:
        ql = q.lower()
        for c in CITIES:
            if ql in c["city"].lower() or ql in c["state"].lower() or ql in c["pin"]:
                results.append({"formatted": f"{c['city']}, {c['state']} - {c['pin']}",
                                "city": c["city"], "state": c["state"], "pin": c["pin"],
                                "lat": c["lat"], "lng": c["lng"]})
        if not results:
            # Default to Delhi
            results.append({"formatted": "New Delhi, Delhi - 110001",
                            "city": "New Delhi", "state": "Delhi", "pin": "110001",
                            "lat": 28.6139, "lng": 77.2090})

    return jsonify({"results": results})


@app.route("/api/auth/otp_send", methods=["POST"])
def api_otp_send():
    data = request.json or {}
    phone = str(data.get("phone_number", ""))[-10:]
    if len(phone) < 10:
        return jsonify({"ok": False, "error": "Enter valid 10-digit number"})
    result = send_otp(phone)
    if result.get("ok") and result.get("session"):
        _meesho_otp_sessions[phone] = result["session"]
        return jsonify({"ok": True, "phone": phone, "live": True})
    return jsonify({"ok": False, "error": result.get("error") or "OTP send failed"})


@app.route("/api/auth/otp_verify", methods=["POST"])
def api_otp_verify():
    data = request.json or {}
    uid = get_uid()
    phone = str(data.get("phone_number", ""))[-10:]
    otp = str(data.get("otp", "")).strip()
    print(f"[APP_OTP_VERIFY] uid={uid} phone={phone} otp={otp}", flush=True)
    session = _meesho_otp_sessions.get(phone)
    if not session:
        print(f"[APP_OTP_VERIFY] No session for phone={phone}, sessions={list(_meesho_otp_sessions.keys())}", flush=True)
        return jsonify({"ok": False, "error": "No pending OTP. Send OTP again."})
    result = verify_otp(phone, otp, session)
    print(f"[APP_OTP_VERIFY] result ok={result.get('ok')} error={result.get('error')}", flush=True)
    if result.get("ok"):
        _meesho_otp_sessions.pop(phone, None)
        if uid:
            is_first = 1 if result.get("is_new") else 0
            save_meesho_account(uid, phone,
                result.get("user_id", ""),
                result.get("xo", ""),
                0,
                result.get("instance_id", ""),
                is_first_order=is_first)
        acc = {
            "id": str(int(time.time() * 1000))[-8:],
            "mobile": phone,
            "user_id": result.get("user_id"),
            "xo": result.get("xo"),
            "instance_id": result.get("instance_id"),
            "is_first_order": result.get("is_new", False),
        }
        return jsonify({"ok": True, "account": acc})
    return jsonify({"ok": False, "error": result.get("error") or "Wrong OTP"})


@app.route("/api/auth/json_login", methods=["POST"])
def api_json_login():
    """Login with Meesho session JSON (user_id, xo, instance_id, etc.)"""
    uid = get_uid()
    if not uid:
        return jsonify({"ok": False, "error": "no user logged in"})
    data = request.json or {}
    print(f"[JSON_LOGIN] uid={uid} keys={list(data.keys())}", flush=True)

    user_id = data.get("user_id")
    xo = data.get("xo")
    instance_id = data.get("instance_id") or data.get("identity", {}).get("instance_id", "")
    app_session_id = data.get("app_session_id") or data.get("identity", {}).get("app_session_id", "")
    shield_session_id = data.get("shield_session_id", "")
    gaid = data.get("gaid") or data.get("identity", {}).get("gaid", "")
    phone = data.get("phone", "")
    phone_last4 = data.get("phone_last4", "")
    is_first = data.get("is_first_order", 1)

    if not user_id or not xo:
        return jsonify({"ok": False, "error": "user_id and xo are required"})

    if not phone and phone_last4:
        phone = f"xxxx{phone_last4}"

    save_meesho_account(uid, phone, str(user_id), xo, 0, instance_id,
                        is_first_order=int(is_first),
                        app_session_id=app_session_id,
                        shield_session_id=shield_session_id,
                        gaid=gaid)

    print(f"[JSON_LOGIN] Saved account: user_id={user_id} instance_id={instance_id}", flush=True)
    return jsonify({"ok": True, "user_id": user_id, "message": "Account logged in successfully!"})


@app.route("/api/auth/me")
def api_auth_me():
    return jsonify({"ok": True, "user": None})


@app.route("/api/fod/continue", methods=["POST"])
def api_fod_continue():
    data = request.json or {}
    offer = data.get("offer")
    if not offer:
        return jsonify({"ok": False, "error": "No offer"})
    global _meesho_offer
    _meesho_offer = offer
    uid = get_uid()
    if uid:
        import json as _json
        save_user_offer(uid, _json.dumps(offer))
    return jsonify({"ok": True, "offer": offer})


# ═══════════════════════════════════════════════════════════════
# MEESHO ACCOUNT MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@app.route("/api/accounts")
def api_accounts():
    uid = get_uid()
    if not uid:
        return jsonify([])
    accs = get_meesho_accounts(uid)
    for a in accs:
        a.pop("xo", None)
        phone = a.get("phone") or ""
        if phone and not phone.startswith("xxxx"):
            a["phone_display"] = phone
        elif phone:
            a["phone_display"] = "xxxx" + phone[-4:]
        else:
            a["phone_display"] = "xxxx"
    return jsonify({"accounts": accs})


@app.route("/api/accounts/add", methods=["POST"])
def api_account_add():
    uid = get_uid()
    if not uid:
        return jsonify({"ok": False, "error": "no user"})
    data = request.json or {}
    phone = str(data.get("phone", ""))[-10:]
    session_data = data.get("session", {})
    meesho_uid = data.get("meesho_user_id", "")
    xo = data.get("xo", "")
    instance_id = data.get("instance_id", "")
    save_meesho_account(uid, phone, meesho_uid, xo, 0, instance_id)
    return jsonify({"ok": True})


@app.route("/api/accounts/delete", methods=["POST"])
def api_account_delete():
    uid = get_uid()
    data = request.json or {}
    acc_id = data.get("id")
    if uid and acc_id:
        delete_meesho_account(uid, acc_id)
    return jsonify({"ok": True})


@app.route("/api/accounts/refresh", methods=["POST"])
def api_account_refresh():
    uid = get_uid()
    if not uid:
        return jsonify({"ok": False, "error": "no user"})
    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"ok": False, "error": "no account"})
    import json as _json
    try:
        offer_data = get_user_offer(uid)
        result = roll_fod_sync()
        if result.get("ok") and result.get("offer"):
            save_user_offer(uid, _json.dumps(result["offer"]))
            return jsonify({"ok": True, "offer": result["offer"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
    return jsonify({"ok": False, "error": "refresh failed"})


@app.route("/api/offers/roll", methods=["POST"])
def api_offer_roll():
    uid = get_uid()
    result = get_meesho_offer()
    if result.get("ok") and result.get("offer"):
        global _meesho_offer
        _meesho_offer = result["offer"]
        if uid:
            import json as _json
            save_user_offer(uid, _json.dumps(result["offer"]))
    return jsonify(result)


@app.route("/api/user/export")
def api_user_export():
    uid = get_uid()
    if not uid:
        return jsonify({"error": "no user"})
    user = get_user(uid) or {}
    accs = get_meesho_accounts(uid)
    offer = get_user_offer(uid)
    wallet_txs = get_wallet_tx(uid)
    orders = get_orders(uid)
    user.pop("wallet", None)
    for a in accs:
        a.pop("xo", None)
    return jsonify({
        "user": user,
        "meesho_accounts": accs,
        "offer": offer,
        "wallet_transactions": wallet_txs,
        "orders": orders,
    })


# ═══════════════════════════════════════════════════════════════
# ADDRESS API
# ═══════════════════════════════════════════════════════════════

@app.route("/api/addresses")
def api_addresses():
    uid = get_uid()
    if not uid:
        return jsonify({"addresses": [], "default": None})
    acc_id = request.args.get("account_id", type=int)
    addrs = get_addresses(uid, acc_id)
    default = next((a for a in addrs if a.get("is_default")), addrs[0] if addrs else None)
    return jsonify({"addresses": addrs, "default": default})


@app.route("/api/addresses/create", methods=["POST"])
def api_address_create():
    uid = get_uid()
    if not uid:
        return jsonify({"ok": False, "error": "no user"})
    data = request.json or {}
    name = data.get("name", "").strip()
    mobile = data.get("mobile", "").strip()
    pin = data.get("pin", "").strip()
    city = data.get("city", "").strip()
    state = data.get("state", "").strip()
    line1 = data.get("address_line_1", "").strip()
    line2 = data.get("address_line_2", "").strip()
    landmark = data.get("landmark", "").strip()
    addr_type = data.get("address_type", "Home")
    is_def = int(data.get("is_default", 0))
    acc_id = int(data.get("meesho_account_id", 0))
    lat = data.get("latitude", "")
    lng = data.get("longitude", "")

    if not (name and mobile and pin and line1):
        return jsonify({"ok": False, "error": "Name, mobile, pin, address required"})

    aid = create_address(uid, acc_id, name, mobile, pin, city, state,
                         line1, line2, landmark, addr_type, lat, lng, is_def)
    addr = get_address(aid)
    return jsonify({"ok": True, "address": addr})


@app.route("/api/addresses/update", methods=["POST"])
def api_address_update():
    uid = get_uid()
    if not uid:
        return jsonify({"ok": False, "error": "no user"})
    data = request.json or {}
    addr_id = data.get("id")
    if not addr_id:
        return jsonify({"ok": False, "error": "no address id"})
    addr = get_address(addr_id)
    if not addr or addr.get("user_id") != uid:
        return jsonify({"ok": False, "error": "not found"})

    fields = {}
    for k in ("name", "mobile", "pin", "city", "state", "address_line_1",
              "address_line_2", "landmark", "address_type", "latitude", "longitude"):
        if k in data:
            fields[k] = data[k]
    if "is_default" in data:
        fields["is_default"] = int(data["is_default"])
        if fields["is_default"]:
            set_default_address(uid, addr_id)
            fields.pop("is_default", None)

    if fields:
        update_address(addr_id, **fields)
    addr = get_address(addr_id)
    return jsonify({"ok": True, "address": addr})


@app.route("/api/addresses/delete", methods=["POST"])
def api_address_delete():
    uid = get_uid()
    if not uid:
        return jsonify({"ok": False, "error": "no user"})
    data = request.json or {}
    addr_id = data.get("id")
    if not addr_id:
        return jsonify({"ok": False, "error": "no address id"})
    addr = get_address(addr_id)
    if not addr or addr.get("user_id") != uid:
        return jsonify({"ok": False, "error": "not found"})
    delete_address(addr_id)
    return jsonify({"ok": True})


@app.route("/api/addresses/set_default", methods=["POST"])
def api_address_set_default():
    uid = get_uid()
    if not uid:
        return jsonify({"ok": False, "error": "no user"})
    data = request.json or {}
    addr_id = data.get("id")
    if not addr_id:
        return jsonify({"ok": False, "error": "no address id"})
    addr = get_address(addr_id)
    if not addr or addr.get("user_id") != uid:
        return jsonify({"ok": False, "error": "not found"})
    set_default_address(uid, addr_id)
    return jsonify({"ok": True})


@app.route("/api/addresses/default")
def api_address_default():
    uid = get_uid()
    if not uid:
        return jsonify({"address": None})
    addr = get_default_address(uid)
    return jsonify({"address": addr})


@app.route("/api/debug")
def api_debug():
    """Debug endpoint - test Meesho API connectivity"""
    import traceback
    results = {}
    
    # Test 1: Meesho search
    try:
        r = search_meesho("fashion trending", offer=_meesho_offer)
        count = len(r.get("catalogs", []))
        results["search"] = {"ok": True, "count": count, "first_name": r["catalogs"][0]["name"] if count else "none"}
    except Exception as e:
        results["search"] = {"ok": False, "error": str(e), "traceback": traceback.format_exc()}
    
    # Test 2: Meesho offer
    try:
        r = get_meesho_offer()
        results["offer"] = {"ok": r.get("ok"), "offer": r.get("offer", {}).get("display_text") if r.get("offer") else None}
    except Exception as e:
        results["offer"] = {"ok": False, "error": str(e)}
    
    # Test 3: Check outbound connectivity
    try:
        import httpx
        with httpx.Client(timeout=10) as c:
            r = c.get("https://httpbin.org/ip")
            results["internet"] = {"ok": True, "ip": r.json().get("origin")}
    except Exception as e:
        results["internet"] = {"ok": False, "error": str(e)}
    
    return jsonify(results)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

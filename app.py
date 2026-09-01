"""
app.py - Flask Backend for Mini App
Products, Cart, Orders, Wallet, Meesho - sab API yahan se
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
    save_meesho_account, get_meesho_accounts, get_active_meesho_account,
    delete_meesho_account, update_meesho_xo,
    save_user_offer, get_user_offer,
    get_addresses, get_address, create_address, update_address,
    delete_address, set_default_address, get_default_address,
    toggle_user_mode, get_user_mode, get_order_count,
)
from gateway import generate_txn_id, create_upi_link, get_qr_url, verify_payment
from config import ORDER_FEE, WALLET_MIN, WALLET_MAX, GW_UPI_ID, GW_UPI_NAME
from meesho import get_meesho_offer, search_meesho, get_meesho_product, send_otp, verify_otp, check_number

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


@app.route("/api/mode")
def api_get_mode():
    uid = get_uid()
    if not uid:
        return jsonify({"mode": "paid"})
    mode = get_user_mode(uid)
    return jsonify({"mode": mode})


@app.route("/api/mode/toggle", methods=["POST"])
def api_toggle_mode():
    uid = get_uid()
    if not uid:
        return jsonify({"ok": False, "error": "login required"})
    new_mode = toggle_user_mode(uid)
    return jsonify({"ok": True, "mode": new_mode})


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
    add_to_cart(uid, pid, qty, name=name, price=price, image=image, source=source)
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
    user_mode = (user.get("mode") or "paid") if user else "paid"
    fee = 0 if user_mode == "free" else ORDER_FEE
    total = subtotal + fee
    w = user.get("wallet", 0)

    if w < total:
        return jsonify({"error": "insufficient wallet", "needed": total - w}), 400

    data = request.json or {}
    addr_text = data.get("address", "")
    if not addr_text:
        default_addr = get_default_address(uid)
        if default_addr:
            addr_text = f"{default_addr.get('name','')}, {default_addr.get('address_line_1','')}, {default_addr.get('city','')}, {default_addr.get('state','')} - {default_addr.get('pin','')}"

    items_str = ", ".join([f"{c.get('name','?')}x{c.get('qty',1)}" for c in cart])
    deduct_wallet(uid, total)
    oid = create_order(uid, items_str, total, fee, addr_text)

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
    phone = str(data.get("phone_number", ""))[-10:]
    otp = str(data.get("otp", "")).strip()
    session = _meesho_otp_sessions.get(phone)
    if not session:
        return jsonify({"ok": False, "error": "No pending OTP."})
    result = verify_otp(phone, otp, session)
    if result.get("ok"):
        _meesho_otp_sessions.pop(phone, None)
        acc = {
            "id": str(int(time.time() * 1000))[-8:],
            "mobile": phone,
            "user_id": result.get("user_id"),
            "xo": result.get("xo"),
            "instance_id": result.get("instance_id"),
            "is_first_order": True,
            "order_placed": False,
        }
        return jsonify({"ok": True, "account": acc})
    return jsonify({"ok": False, "error": result.get("error") or "Wrong OTP"})


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
    return jsonify(accs)


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

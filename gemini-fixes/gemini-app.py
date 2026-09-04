import json
import os
import urllib.parse
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from database import (
    add_to_cart,
    clear_cart,
    create_address,
    create_order,
    create_user,
    get_address,
    get_addresses,
    get_cart,
    get_cart_session,
    get_default_address,
    get_orders,
    get_user,
    save_meesho_account,
    set_cart_session,
    set_default_address,
    tombstone_add,
    tombstone_recent,
    update_cart_qty,
    update_order_status,
)
from meesho import (
    check_order_payment_status,
    fresh_checkout_state,
    get_active_meesho_account,
    meesho_product_sync,
    meesho_remove_verified,
    meesho_search_sync,
    real_cart_add_many,
    real_cart_review,
    real_preorder,
    request_meesho_otp_sync,
    roll_fod_sync,
    verify_meesho_otp_sync,
)

app = Flask(__name__)
CORS(app)


def get_uid():
    for raw in (request.headers.get("X-User-Id"), request.args.get("uid")):
        if raw and str(raw).strip() not in ("", "0", "None"):
            try:
                return int(str(raw).strip())
            except Exception:
                pass
    return 1[cite: 12]


def sync_local_cart(uid, acc):
    """Idempotent sync: pushes local cart items ONLY if Meesho cart is verified empty."""
    cart = get_cart(uid)
    if not cart:
        return True, ""

    cs = get_cart_session(uid) or ""
    rev = real_cart_review(acc, cs)
    if not rev.get("ok"):
        rev = real_cart_review(acc, "")

    if rev.get("ok"):
        if rev.get("cart_session"):
            cs = rev["cart_session"]
            set_cart_session(uid, cs)
        if len(rev.get("items") or []) > 0:
            # Remote cart is populated; do not add again
            return True, cs

    # Remote cart is empty: push local items
    valid_items = [c for c in cart if c.get("product_id")]
    if not valid_items:
        return True, cs

    add_res = real_cart_add_many(acc, valid_items, cs)
    if add_res.get("ok"):
        new_cs = add_res.get("cart_session") or cs
        set_cart_session(uid, new_cs)
        return True, new_cs

    return False, cs


@app.route("/")
def index():
    return render_template("index.html")[cite: 12]


@app.route("/api/offers")
def api_offers():
    return jsonify(roll_fod_sync())


@app.route("/api/fod/roll")
def api_fod_roll():
    return jsonify(roll_fod_sync())


@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.json or {}[cite: 12]
    q = data.get("query", "fashion trending")
    return jsonify(meesho_search_sync(q))


@app.route("/api/product")
def api_product():
    pid = request.args.get("product_id")[cite: 12]
    p = meesho_product_sync(pid)
    if p:
        return jsonify(p)
    return jsonify({"error": "not found"}), 404[cite: 12]


@app.route("/api/cart")
def api_cart():
    uid = get_uid()
    items = get_cart(uid)
    tot = sum(int(c.get("price", 0)) * int(c.get("qty", 1)) for c in items)
    return jsonify({
        "items": items,
        "total_quantity": sum(int(c.get("qty", 1)) for c in items),
        "effective_total": tot,
        "cart_session": get_cart_session(uid),
    })


@app.route("/api/cart/add", methods=["POST"])
def api_cart_add():
    uid = get_uid()
    data = request.json or {}[cite: 12]
    pid = int(data.get("product_id"))
    qty = int(data.get("qty") or data.get("quantity") or 1)

    add_to_cart(
        user_id=uid,
        product_id=pid,
        qty=qty,
        name=data.get("name", "Product"),
        price=int(data.get("price", 0)),
        image=data.get("image", ""),
        supplier_id=int(data.get("supplier_id") or 0),
        variation_id=int(data.get("variation_id") or 0),
        variation_name=data.get("variation", "Free Size"),
        mrp=int(data.get("mrp", 0)),
    )
    return jsonify({"ok": True})


@app.route("/api/cart/update", methods=["POST"])
def api_cart_update():
    uid = get_uid()
    data = request.json or {}[cite: 12]
    cid = data.get("cart_id")[cite: 12]
    pid = data.get("product_id")
    qty = int(data.get("qty", 0))

    if not cid and pid:
        cart = get_cart(uid)
        target = next((c for c in cart if str(c.get("product_id")) == str(pid)), None)[cite: 12]
        if target:
            cid = target.get("id")[cite: 12]

    if cid:
        update_cart_qty(cid, qty)

    if pid and qty <= 0:
        # User explicitly deleted the item: Tombstone immediately
        tombstone_add(uid, int(pid))
        acc = get_active_meesho_account(uid)
        if acc:
            cs = get_cart_session(uid)
            meesho_remove_verified(acc, int(pid), cs)

    return jsonify({"ok": True})


@app.route("/api/cart/sync/pull", methods=["GET", "POST"])
def api_cart_sync_pull():
    uid = get_uid()
    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"ok": False, "error": "no_account"})[cite: 12]

    cs = get_cart_session(uid)
    rev = real_cart_review(acc, cs)
    if not rev.get("ok"):
        rev = real_cart_review(acc, "")
    if rev.get("cart_session"):
        set_cart_session(uid, rev["cart_session"])

    meesho_items = rev.get("items") or []
    tombs = tombstone_recent(uid)
    local_cart = get_cart(uid)
    local_keys = {(int(c["product_id"]), int(c["variation_id"])) for c in local_cart}

    imported = 0
    for mi in meesho_items:
        mpid = int(mi["product_id"])
        mvid = int(mi.get("variation_id") or 0)
        # Skip tombstoned items so lagging Meesho removes don't resurrect locally
        if mpid in tombs:
            continue
        if (mpid, mvid) not in local_keys:
            add_to_cart(
                user_id=uid,
                product_id=mpid,
                qty=int(mi.get("quantity", 1)),
                name=mi.get("name", "Product"),
                price=int(mi.get("price", 0)),
                image=mi.get("image", ""),
                supplier_id=int(mi.get("supplier_id") or 0),
                variation_id=mvid,
                variation_name=mi.get("variation", "Free Size"),
                mrp=int(mi.get("mrp", 0)),
            )
            imported += 1

    return jsonify({"ok": True, "imported": imported, "items": get_cart(uid)})


@app.route("/api/checkout/summary")
def api_checkout_summary():
    uid = get_uid()
    cart = get_cart(uid)
    if not cart:
        return jsonify({"error": "Cart is empty"}), 400

    acc = get_active_meesho_account(uid)
    subtotal = sum(int(c.get("price", 0)) * int(c.get("qty", 1)) for c in cart)
    cod_amount = subtotal
    upi_amount = max(0, subtotal - 28) if subtotal > 40 else subtotal

    if acc:
        cs = get_cart_session(uid)
        rev = real_cart_review(acc, cs)
        if rev.get("ok") and rev.get("effective_total"):
            cod_amount = int(rev.get("effective_total"))
            upi_amount = int(rev.get("effective_total_for_upi_plugin") or max(0, cod_amount - 28))

    return jsonify({
        "product_price": subtotal + 50,
        "total_discounts": -50,
        "cod_amount": cod_amount,
        "upi_amount": upi_amount,
        "prepaid_discount": max(0, cod_amount - upi_amount),
        "total": cod_amount,
    })


@app.route("/api/order/place_cod", methods=["POST"])
def api_place_cod():
    uid = get_uid()
    data = request.json or {}[cite: 12]
    aid = data.get("address_id")[cite: 12]

    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"ok": False, "error": "no_account", "message": "Login to Meesho first"}), 400

    addr = get_address(aid) if aid else get_default_address(uid)
    if not addr:
        return jsonify({"ok": False, "error": "no_address", "message": "Select delivery address"}), 400

    # Idempotent push to guarantee items are on Meesho before ordering
    sync_ok, cs = sync_local_cart(uid, acc)
    if not sync_ok:
        return jsonify({"ok": False, "error": "cart_sync_failed", "message": "Unable to sync cart to Meesho"}), 400

    info = {}
    st = fresh_checkout_state(acc, cs, need_paymentinfo=True, cod=True, info=info)
    if not st:
        return jsonify({"ok": False, "error": info.get("stage", "checkout_failed"), "message": "Could not finalize Meesho cart"}), 400

    total_amt = st["cod_amount"]
    order_res = real_preorder(acc, st["cs"], st["addr"]["id"], payment_method="COD", customer_amount=total_amt)

    if not order_res.get("ok"):
        return jsonify({"ok": False, "error": order_res.get("error"), "message": "COD order placement failed"}), 400

    oid = create_order(uid, "Items", total_amt, 0, addr.get("address_line_1", ""), order_res.get("order_num"), "COD", total_amt)
    clear_cart(uid)
    set_cart_session(uid, "")

    return jsonify({
        "ok": True,
        "order_num": str(oid),
        "meesho_order_num": order_res.get("order_num"),
        "total": total_amt,
        "message": "Order placed successfully!",
    })


@app.route("/api/order/pay_online", methods=["POST"])
def api_pay_online():
    uid = get_uid()
    data = request.json or {}[cite: 12]
    aid = data.get("address_id")[cite: 12]

    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"ok": False, "error": "no_account", "message": "Login to Meesho first"}), 400

    addr = get_address(aid) if aid else get_default_address(uid)
    if not addr:
        return jsonify({"ok": False, "error": "no_address", "message": "Select delivery address"}), 400

    sync_ok, cs = sync_local_cart(uid, acc)
    if not sync_ok:
        return jsonify({"ok": False, "error": "cart_sync_failed", "message": "Unable to sync cart to Meesho"}), 400

    info = {}
    st = fresh_checkout_state(acc, cs, need_paymentinfo=True, cod=False, info=info)
    if not st:
        return jsonify({"ok": False, "error": info.get("stage", "checkout_failed"), "message": "Could not finalize Meesho checkout"}), 400

    total_amt = st["upi_amount"]
    order_res = real_preorder(acc, st["cs"], st["addr"]["id"], payment_method="UPI", customer_amount=total_amt)

    if not order_res.get("ok"):
        return jsonify({"ok": False, "error": order_res.get("error"), "message": "UPI order initialization failed"}), 400

    oid = create_order(uid, "Items", total_amt, 0, addr.get("address_line_1", ""), order_res.get("order_num"), "UPI", total_amt)
    clear_cart(uid)
    set_cart_session(uid, "")

    upi_intent_url = order_res.get("upi_intent_url") or ""
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={urllib.parse.quote(upi_intent_url)}" if upi_intent_url else ""

    return jsonify({
        "ok": True,
        "order_num": str(oid),
        "meesho_order_num": order_res.get("order_num"),
        "amount": total_amt,
        "upi_amount": total_amt,
        "upi_intent_url": upi_intent_url,
        "qr_url": qr_url,
        "qr_base64": "",
    })


@app.route("/api/order/confirm", methods=["POST"])
def api_order_confirm():
    data = request.json or {}[cite: 12]
    oid = data.get("order_num")[cite: 12]
    if oid:
        update_order_status(oid, "confirmed")
    return jsonify({"ok": True, "message": "Order confirmed"})


@app.route("/api/orders")
def api_orders():
    uid = get_uid()
    return jsonify({"orders": get_orders(uid)})


@app.route("/api/addresses")
def api_addresses():
    uid = get_uid()
    return jsonify({"addresses": get_addresses(uid)})


@app.route("/api/addresses/create", methods=["POST"])
def api_address_create():
    uid = get_uid()
    d = request.json or {}[cite: 12]
    aid = create_address(
        user_id=uid,
        name=d.get("name", ""),
        mobile=d.get("mobile", ""),
        pin=d.get("pin", ""),
        city=d.get("city", ""),
        state=d.get("state", ""),
        address_line_1=d.get("address_line_1", ""),
        is_default=1,
    )
    return jsonify({"ok": True, "id": aid})


@app.route("/api/addresses/set_default", methods=["POST"])
def api_addresses_set_default():
    uid = get_uid()
    d = request.json or {}[cite: 12]
    set_default_address(uid, d.get("id"))
    return jsonify({"ok": True})


@app.route("/api/auth/otp_send", methods=["POST"])
def api_otp_send():
    d = request.json or {}[cite: 12]
    phone = str(d.get("phone_number", ""))[-10:][cite: 12]
    return jsonify(request_meesho_otp_sync(phone))


@app.route("/api/auth/otp_verify", methods=["POST"])
def api_otp_verify():
    uid = get_uid()
    d = request.json or {}[cite: 12]
    res = verify_meesho_otp_sync(d.get("phone_number"), d.get("otp"), d)
    if res.get("ok"):
        save_meesho_account(
            user_id=uid,
            phone=res["phone"],
            meesho_user_id=res["user_id"],
            xo=res["xo"],
            instance_id=res["instance_id"],
            is_first_order=1 if res.get("is_new") else 0,[cite: 12]
        )
        return jsonify({"ok": True, "message": "Account linked!"})[cite: 12]
    return jsonify(res), 400


@app.route("/api/auth/json_login", methods=["POST"])
def api_json_login():
    uid = get_uid()
    d = request.json or {}[cite: 12]
    save_meesho_account(
        user_id=uid,
        phone=d.get("phone", "9999999999"),
        meesho_user_id=d.get("user_id", ""),
        xo=d.get("xo", ""),
        instance_id=d.get("instance_id", uuid.uuid4().hex),
        is_first_order=int(d.get("is_first_order", 1)),
    )
    return jsonify({"ok": True, "message": "Connected successfully"})


@app.route("/api/geocode")
def api_geocode():
    return jsonify({
        "results": [{
            "city": "Indore",
            "state": "Madhya Pradesh",
            "pin": "452010",
        }]
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
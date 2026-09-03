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
    create_order, get_orders, get_order, update_order_status,
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
    meesho_remove_verified,
    real_bind_address, real_paymentinfo, real_address_create, real_fetch_addresses,
    real_preorder, real_payment_status, real_preorder_status, real_payment_options,
    fresh_checkout_state, roll_fod_sync,
    real_cart_minview, real_home_for_you, real_home_fetch, real_user_delivery_location,
    real_wallet_list, real_bnpl_eligibility, real_offers_list, real_payments_user_details,
    real_user_orders, real_product_recommendations,
)

app = Flask(__name__)

CORS(app, resources={r"/api/*": {"origins": "*"}})
CORS(app, resources={r"/": {"origins": "*"}})

@app.before_request
def log_request():
    import sys
    print(f"[REQ] {request.method} {request.path} from {request.remote_addr}", flush=True, file=sys.stderr)


def get_uid():
    """Get user_id — robust for Telegram Mini App.

    Priority: X-User-Id header > ?uid= query > Telegram initData user id >
    stable hash of X-Device-ID > 1 (shared default, never 0 so that
    `if not uid` checks don't misfire and accounts actually persist).
    """
    # 1. Explicit header (frontend sends AUTH.uid here)
    # NOTE: never touch request.json directly — the working-bot frontend sends
    # `Content-Type: application/json` even on bodyless GETs, and accessing
    # request.json then raises 400 for every GET. silent=True avoids that.
    _body_uid = None
    try:
        _bj = request.get_json(silent=True)
        if isinstance(_bj, dict):
            _body_uid = _bj.get("uid")
    except Exception:
        _body_uid = None
    for raw in (request.headers.get("X-User-Id"),
                request.args.get("uid"),
                _body_uid):
        if raw in (None, "", "0", 0):
            continue
        try:
            v = int(str(raw).strip())
            if v:
                return v
        except (ValueError, TypeError):
            continue
    # 2. Telegram initData -> user id
    try:
        init_data = request.headers.get("X-Tg-Init-Data", "") or request.args.get("tgib", "")
        if init_data and "user" in init_data:
            from urllib.parse import parse_qs
            import json as _j
            qs = parse_qs(init_data)
            raw_u = (qs.get("user") or [None])[0]
            if raw_u:
                obj = _j.loads(raw_u)
                tid = int(obj.get("id", 0)) if isinstance(obj, dict) else 0
                if tid:
                    return tid
    except Exception:
        pass
    # 3. Stable per-browser id from device id (so OTP + accounts persist
    #    for plain browsers without Telegram uid)
    try:
        import hashlib
        did = request.headers.get("X-Device-ID", "") or request.cookies.get("device_id", "")
        if did:
            h = hashlib.md5(did.encode()).hexdigest()[:7]
            v = int(h, 16) % 900000 + 100000  # 6-digit stable id
            if v:
                return v
    except Exception:
        pass
    return 1


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
    # Working-bot frontend shape (enriched). Builder is defined in the
    # adapter section below; resolved at call time.
    return _build_cart_response(get_uid())


@app.route("/api/cart/add", methods=["POST"])
def api_cart_add():
    # Working-bot frontend shape (enriched cart + real Meesho prices).
    return adapter_cart_add()


@app.route("/api/cart/update", methods=["POST"])
def api_cart_update():
    _d = request.get_json(silent=True) or {}
    if isinstance(_d.get("item"), dict):
        return adapter_cart_update()
    uid = get_uid()
    data = _d
    cid = data.get("cart_id")
    req_ident = data.get("identifier")
    qty = data.get("qty", 1)
    cart_before = get_cart(uid)
    print(f"[CART_UPDATE] uid={uid} cid={cid} qty={qty} req_ident={str(req_ident)[:30]} cart_before={[(c.get('id'),c.get('product_id'),c.get('qty')) for c in cart_before]}", flush=True)
    target = next((c for c in cart_before if str(c.get("id")) == str(cid)), None)
    if not target:
        # fallback: cid may be product_id when only one item or frontend bug
        target = next((c for c in cart_before if str(c.get("product_id")) == str(cid)), None)
        if target:
            cid = target.get("id")  # correct to real cart id for delete
    prod_id = target.get("product_id") if target else None
    sup_id = target.get("supplier_id") if target else 0
    var_id = target.get("variation_id") if target else 0
    var_name = target.get("variation_name") if target else "Free Size"
    # If still no target but qty==0 and single item in cart, delete that single item
    if not target and int(qty) <= 0 and len(cart_before)==1:
        target = cart_before[0]
        cid = target.get("id")
        prod_id = target.get("product_id")
        sup_id = target.get("supplier_id",0)
        var_id = target.get("variation_id",0)
        var_name = target.get("variation_name","Free Size")
    if cid:
        update_cart_qty(cid, qty)
        print(f"[CART_UPDATE] delete/update cid={cid} qty={qty} pid={prod_id}", flush=True)
    else:
        # safety: clear if no cid but qty 0
        if int(qty) <=0 and prod_id:
            # delete by product_id
            from database import get_db
            conn=get_db(); conn.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (uid, prod_id)); conn.commit(); conn.close()
    # sync to real Meesho cart - remove path is VERIFIED (fresh review ->
    # remove by Meesho identifier -> re-review confirms absence), because
    # Meesho can answer 200 without deleting on a stale cart_session.
    meesho_verified = None
    try:
        acc = get_active_meesho_account(uid)
        if acc and prod_id:
            cs = get_cart_session(uid)
            if int(qty) <= 0:
                # Tombstone FIRST on explicit remove-intent — regardless of
                # how the Meesho remove below turns out. Otherwise a lagging
                # Meesho cart gets re-imported by the next pull and the qty
                # jumps back (or doubles). TTL expiry restores truth later.
                try:
                    if prod_id:
                        _tombstone_add(uid, int(prod_id))
                except (TypeError, ValueError):
                    pass
                vr = meesho_remove_verified(acc, int(prod_id), cs or "", var_id or None,
                                            fallback_identifier=req_ident)
                if vr.get("cart_session"):
                    set_cart_session(uid, vr["cart_session"])
                meesho_verified = bool(vr.get("verified"))
                print(f"[CART_UPDATE] verified remove pid={prod_id} removed={vr.get('removed')} verified={vr.get('verified')} via={vr.get('via')} err={vr.get('error')}", flush=True)
            else:
                # qty change: remove and re-add with new qty
                review = real_cart_review(acc, cs)
                if review.get("ok"):
                    if review.get("cart_session"):
                        cs = review["cart_session"]; set_cart_session(uid, cs)
                    m_items = review.get("items") or []
                    m_match = None
                    for mi in m_items:
                        if int(mi.get("product_id") or 0) == int(prod_id):
                            if var_id and mi.get("variation_id") and int(mi.get("variation_id")) != int(var_id):
                                continue
                            m_match = mi; break
                    if m_match and m_match.get("identifier"):
                        ident = m_match["identifier"]
                        rr = real_cart_remove(acc, ident, cs)
                        new_cs = rr.get("cart_session") or cs
                        ar = real_cart_add(acc, prod_id, sup_id, var_id, var_name, int(qty), new_cs)
                        if ar.get("cart_session"): set_cart_session(uid, ar["cart_session"])
                        print(f"[CART_UPDATE] qty change pid={prod_id} new_qty={qty}", flush=True)
                    else:
                        # no identifier match, direct re-add
                        rr = real_cart_remove(acc, {"product_id": int(prod_id)}, cs)
                        new_cs = rr.get("cart_session") or cs
                        ar = real_cart_add(acc, prod_id, sup_id, var_id, var_name, int(qty), new_cs)
                        if ar.get("cart_session"): set_cart_session(uid, ar["cart_session"])
    except Exception as e:
        import traceback; print(f"[CART_UPDATE] Meesho sync failed: {e} {traceback.format_exc()}", flush=True)
    out = {"ok": True}
    if meesho_verified is not None:
        out["meesho_removed"] = meesho_verified
        out["meesho_verified"] = meesho_verified
    return jsonify(out)


@app.route("/api/cart/clear", methods=["POST"])
def api_cart_clear():
    uid = get_uid()
    clear_cart(uid)
    # also clear real Meesho cart
    try:
        acc = get_active_meesho_account(uid)
        if acc:
            cs = get_cart_session(uid)
            cr = real_cart_clear(acc, cs)
            if cr.get("cart_session"):
                set_cart_session(uid, cr["cart_session"])
            else:
                set_cart_session(uid, "")
            print(f"[CART_CLEAR] Meesho clear ok={cr.get('ok')}", flush=True)
    except Exception as e:
        print(f"[CART_CLEAR] Meesho sync failed: {e}", flush=True)
        set_cart_session(uid, "")
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════════
# ORDERS API
# ═══════════════════════════════════════════════════════════════

@app.route("/api/orders")
def api_orders():
    # Working-bot frontend shape {orders, filters, cursor}.
    return adapter_orders()


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

    # COMPLETELY FREE: cart total = only products sum, no fee at all
    subtotal = sum(c.get("price", 0) * c.get("qty", 1) for c in cart)
    fee = 0  # FREE - was ORDER_FEE, removed
    try:
        user_mode = get_global_mode()
    except Exception:
        user_mode = "free"

    # Get persisted cart_session, or sync local cart to real Meesho cart
    cart_session = get_cart_session(uid)

    # Push local cart to real Meesho cart via multi-item add
    # If no session yet, start fresh (Meesho expects null, not stale string)
    valid_items = [c for c in cart if c.get("product_id")]
    if valid_items:
        # Clear any existing real cart items first so stale items don't mix
        try:
            existing_review = real_cart_review(acc, cart_session)
            if existing_review.get("ok") and existing_review.get("items"):
                cs_for_remove = existing_review.get("cart_session") or cart_session
                for ei in existing_review["items"]:
                    ident = ei.get("identifier")
                    if ident and cs_for_remove:
                        real_cart_remove(acc, ident, cs_for_remove)
                # After clearing, start with empty session (captured flow uses "" for new cart)
                cart_session = ""
        except Exception as e:
            print(f"[PLACE_ORDER] clear_existing failed: {e}", flush=True)
        # Push the full bag in one call (tries pdp then pdl, plus basic price fallback)
        add_r = real_cart_add_many(acc, valid_items, cart_session or "")
        print(f"[PLACE_ORDER] add_many result: {str(add_r)[:400]}", flush=True)
        if add_r.get("ok"):
            cart_session = add_r.get("cart_session", cart_session)
            if cart_session:
                set_cart_session(uid, cart_session)
        else:
            # If multi-add fails, try single adds as fallback
            print(f"[PLACE_ORDER] add_many failed, trying single adds", flush=True)
            for it in valid_items:
                sr = real_cart_add(acc, it.get("product_id"), it.get("supplier_id"),
                                   it.get("variation_id"), it.get("variation_name") or "Free Size",
                                   it.get("qty", 1), cart_session or "")
                if sr.get("ok") and sr.get("cart_session"):
                    cart_session = sr["cart_session"]
                    set_cart_session(uid, cart_session)
            # Verify at least one item made it
            verify = real_cart_review(acc, cart_session)
            print(f"[PLACE_ORDER] verify after single adds: {str(verify)[:400]}", flush=True)
            if not verify.get("ok") or not verify.get("items"):
                if user_mode == "paid":
                    add_wallet(uid, fee)
                return jsonify({"error": "Cart sync failed. Meesho rejected items - check supplier/variation ids.",
                                "details": add_r}), 400

    # Use fresh_checkout_state to run review -> bind -> paymentinfo in one flow
    st = fresh_checkout_state(acc, cart_session, need_paymentinfo=(payment_method != "COD"))
    if not st:
        if user_mode == "paid":
            add_wallet(uid, fee)
        # Give actionable error: show review raw for debugging
        dbg_review = real_cart_review(acc, cart_session)
        return jsonify({"error": "Could not load the live Meesho cart.",
                        "hint": "Check Meesho login valid, address covers pincode, items in stock.",
                        "cart_session": cart_session,
                        "review": dbg_review}), 400

    cart_session = st["cs"]
    # Reference (checkout_method.txt): for UPI use effective_total_with_ppd (UI amount),
    # for COD use effective_total/without_ppd. Primary candidate = that amount to avoid
    # price mismatch, then effective_total / subtotal as fallbacks.
    if payment_method == "COD":
        meesho_amount = st.get("effective_total") or st.get("order_total") or subtotal
    else:
        meesho_amount = st.get("upi_amount") or st.get("order_total") or subtotal
    meesho_addr_id = st["addr"].get("id")
    set_cart_session(uid, cart_session)

    order_r = None
    tried_amts = []
    actual_amount = meesho_amount  # track what actually succeeded
    if payment_method == "COD":
        cands = (st.get("effective_total"), st.get("order_total"), st.get("upi_amount"), subtotal)
    else:
        cands = (st.get("upi_amount"), st.get("order_total"), st.get("effective_total"), subtotal)
    for cand in cands:
        try:
            cand_int = int(cand or 0)
        except:
            continue
        if not cand_int or cand_int in tried_amts:
            continue
        tried_amts.append(cand_int)
        order_r = real_preorder(acc, cart_session, meesho_addr_id,
                                payment_method=payment_method,
                                customer_amount=cand_int,
                                addr_info=st.get("addr") or {})
        print(f"[PLACE_ORDER] preorder try amount={cand_int} ok={order_r.get('ok')} err={order_r.get('error')} meesho_num={order_r.get('order_num')} raw={str(order_r.get('raw'))[:400]}", flush=True)
        if order_r.get("ok"):
            actual_amount = cand_int
            break
    if not order_r or not order_r.get("ok"):
        if user_mode == "paid":
            add_wallet(uid, fee)
        # Try to give actionable hint - if order_failed due to amount, try with cod_amount instead
        hint = ""
        raw = (order_r or {}).get("raw") or {}
        if "amount" in str(raw).lower() or "customer_amount" in str(raw).lower():
            hint = "Amount mismatch - try COD or check cart price"
        return jsonify({"error": f"Order failed: {(order_r or {}).get('error')}",
                        "message": (order_r or {}).get("message", "") or hint,
                        "details": order_r,
                        "sent_amount": actual_amount,
                        "tried_amounts": tried_amts,
                        "cart_session": cart_session,
                        "address_id": meesho_addr_id}), 400

    meesho_order_num = order_r.get("order_num", "")
    items_str = ", ".join([f"{c.get('name', '?')}x{c.get('qty', 1)}" for c in cart])
    # total stored = actual Meesho payable (what user pays Meesho), fee is our backend cut
    oid = create_order(uid, items_str, actual_amount, fee, addr.get("address_line_1", ""),
                       meesho_order_num=meesho_order_num, payment_method=payment_method,
                       meesho_amount=actual_amount)

    clear_cart(uid)
    set_cart_session(uid, "")

    # QR generation: use Meesho's real QR if available, NO fake seller UPI
    qr_base64 = order_r.get("qr_base64")
    upi_intent_url = order_r.get("upi_intent_url")
    qr_url = ""
    if qr_base64:
        # Meesho returned real QR image - use it directly
        pass
    elif upi_intent_url:
        # Meesho returned UPI intent link - render QR from it
        qr_url = get_qr_url(upi_intent_url)

    return jsonify({
        "ok": True, "order_id": oid, "meesho_order_num": meesho_order_num,
        "total": actual_amount, "meesho_amount": actual_amount,
        "fee_charged": fee,
        "payment_method": payment_method, "mode": user_mode,
        "qr_base64": qr_base64,
        "upi_intent_url": upi_intent_url,
        "qr_url": qr_url,
        "payment_url": order_r.get("payment_url"),
    })


# ── ONLINE PAYMENT (Direct UPI Intent, no gateway/QR) ─────────────────
# COD already works via /api/orders/place (real Meesho). This is the manual
# UPI flow: create pending -> open upi://pay -> user pays -> "Maine pay kiya" -> confirm.

@app.route("/api/orders/create-pending", methods=["POST"])
def api_create_pending():
    """UPI order: uses Meesho's real preorder to get actual payment QR/URL.
    NO fake seller UPI - payment goes through Meesho's real gateway."""
    uid = get_uid()
    cart = get_cart(uid)
    if not cart:
        return jsonify({"ok": False, "error": "cart empty"}), 400
    data = request.json or {}
    fee = 0

    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"ok": False, "error": "no meesho account linked. Login first."}), 400

    # Allow frontend to select address (like checkout address selection)
    sel_addr_id = data.get("address_id")
    addr = None
    if sel_addr_id:
        addr = get_address(sel_addr_id)
        # ensure it belongs to user
        if addr and addr.get("user_id") != uid:
            addr = None
    if not addr:
        addr = get_default_address(uid)
    if not addr:
        return jsonify({"ok": False, "error": "no address found. Add address first."}), 400
    # If selected address exists, make it default for next time
    if sel_addr_id and addr:
        try: set_default_address(uid, addr.get("id"))
        except: pass

    # Get real Meesho prices via checkout flow
    cart_session = get_cart_session(uid)
    valid_items = [c for c in cart if c.get("product_id")]
    if valid_items:
        try:
            existing_review = real_cart_review(acc, cart_session)
            if existing_review.get("ok") and existing_review.get("items"):
                cs_for_remove = existing_review.get("cart_session") or cart_session
                for ei in existing_review["items"]:
                    ident = ei.get("identifier")
                    if ident and cs_for_remove:
                        real_cart_remove(acc, ident, cs_for_remove)
                cart_session = ""
        except: pass
        add_r = real_cart_add_many(acc, valid_items, cart_session or "")
        if add_r.get("ok"):
            cart_session = add_r.get("cart_session", cart_session)
            if cart_session:
                set_cart_session(uid, cart_session)

    st = fresh_checkout_state(acc, cart_session, need_paymentinfo=True)
    if not st:
        return jsonify({"ok": False, "error": "Could not load Meesho cart. Check login/items."}), 400

    cart_session = st["cs"]
    upi_amt = st.get("upi_amount") or st.get("order_total") or 0
    order_tot = st.get("order_total") or st.get("effective_total") or upi_amt or 0
    meesho_addr_id = st["addr"].get("id")
    set_cart_session(uid, cart_session)

    # Use Meesho's REAL preorder - returns actual payment QR from JusPay.
    # Working bot (checkout_method.txt) uses for UPI: effective_total_with_ppd
    # (the discounted UPI amount, e.g. 56 not 83). So try upi_amt first (matches
    # displayed price -> no price mismatch), then effective_total as fallback.
    order_r = None
    tried_amts = []
    actual_amount = upi_amt  # track what actually succeeded
    for cand in (upi_amt, order_tot):
        try:
            cand_int = int(cand or 0)
        except:
            continue
        if not cand_int or cand_int in tried_amts:
            continue
        tried_amts.append(cand_int)
        order_r = real_preorder(acc, cart_session, meesho_addr_id,
                                payment_method="UPI", customer_amount=cand_int,
                                addr_info=st.get("addr") or {})
        print(f"[CREATE_PENDING] preorder try amount={cand_int} ok={order_r.get('ok')} err={order_r.get('error')} raw={str(order_r.get('raw'))[:400]} addr={meesho_addr_id} cs={cart_session[:20] if cart_session else ''}", flush=True)
        if order_r.get("ok"):
            actual_amount = cand_int  # this is the amount that worked
            break
    if not order_r or not order_r.get("ok"):
        return jsonify({"ok": False, "error": f"Order failed: {(order_r or {}).get('error')}", "message": (order_r or {}).get("message",""), "details": order_r, "sent_amount": actual_amount, "tried_amounts": tried_amts, "address_id": meesho_addr_id}), 400

    meesho_order_num = order_r.get("order_num", "")
    items_str = ", ".join([f"{c.get('name','?')}x{c.get('qty',1)}" for c in cart])
    oid = create_order(uid, items_str, actual_amount, fee, addr.get("address_line_1", ""),
                       meesho_order_num=meesho_order_num, payment_method="UPI",
                       meesho_amount=actual_amount)
    clear_cart(uid)
    set_cart_session(uid, "")

    # Return Meesho's real QR data (NOT fake seller UPI)
    qr_base64 = order_r.get("qr_base64")
    upi_intent_url = order_r.get("upi_intent_url")
    qr_url = ""
    if qr_base64:
        pass  # Meesho returned real QR image
    elif upi_intent_url:
        qr_url = get_qr_url(upi_intent_url)

    # Also provide working-bot compatible keys (upi_uri, redirect_url) for QR generation
    upi_uri = upi_intent_url or ""
    return jsonify({
        "ok": True, "order_id": oid, "meesho_order_num": meesho_order_num,
        "amount": actual_amount, "fee": fee,
        "qr_base64": qr_base64, "upi_intent_url": upi_intent_url, "qr_url": qr_url,
        "upi_uri": upi_uri, "redirect_url": upi_intent_url or order_r.get("payment_url") or "",
        "payment_url": order_r.get("payment_url"),
        "juspay_order_id": order_r.get("juspay_order_id"),
        "payment_method": "UPI",
    })


@app.route("/api/orders/confirm", methods=["POST"])
def api_confirm_order():
    uid = get_uid()
    data = request.json or {}
    oid = data.get("order_id")
    if not oid:
        return jsonify({"ok": False, "error": "order_id required"}), 400
    # verify order belongs to user
    ord_row = get_order(int(oid))
    if not ord_row or int(ord_row.get("user_id", 0)) != int(uid):
        return jsonify({"ok": False, "error": "order not found"}), 404
    update_order_status(int(oid), "confirmed")
    return jsonify({"ok": True, "order_id": oid, "status": "confirmed"})


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
    fee = 0  # COMPLETELY FREE
    balance = user.get("wallet", 0) if user else 0
    try:
        user_mode = get_global_mode()
    except Exception:
        user_mode = "free"

    addr = get_default_address(uid)
    acc = get_active_meesho_account(uid)

    # If local address exists but not synced to Meesho, try Meesho's address list
    if addr and acc and not addr.get("meesho_address_id"):
        try:
            meesho_addrs = real_fetch_addresses(acc)
            if meesho_addrs:
                # Use first Meesho address (it has real Meesho address_id for binding)
                addr = meesho_addrs[0]
        except: pass
    elif not addr and acc:
        # No local address at all - try Meesho
        try:
            meesho_addrs = real_fetch_addresses(acc)
            if meesho_addrs:
                addr = meesho_addrs[0]
        except: pass
    # Ensure addr always has address_line_1 for frontend display
    if addr:
        if not addr.get("address_line_1") and addr.get("line1"):
            addr["address_line_1"] = addr["line1"]
        if not addr.get("address_line_1") and addr.get("address"):
            addr["address_line_1"] = addr["address"]

    cod_amount = subtotal
    upi_amount = subtotal
    payinfo_ok = False
    real_effective_total = None
    real_with_ppd = None

    # Try to get real Meesho prices via cart review
    # Captured API: COD = effective_total (69), UPI = effective_total_with_ppd / ForUpiPlugin (41)
    # We DON'T add fee to these - fee is separate wallet deduction.
    if acc:
        cs = get_cart_session(uid)
        if not cs:
            # CRITICAL: Try review with empty session FIRST to recover Meesho's
            # server-side cart (session may have expired but cart persists).
            # DO NOT call real_cart_add_many here - it ADDS items with
            # replaceable:false, causing qty auto-increment when items already
            # exist in Meesho's cart.
            review_try = real_cart_review(acc, "")
            if review_try.get("ok") and review_try.get("cart_session"):
                cs = review_try["cart_session"]
                set_cart_session(uid, cs)
                print(f"[CHECKOUT_SUMMARY] recovered Meesho cart_session from review (empty session)", flush=True)
            else:
                # Meesho cart truly empty - safe to add local items
                valid_items = [c for c in cart if c.get("product_id")]
                if valid_items:
                    add_r = real_cart_add_many(acc, valid_items, "")
                    if add_r.get("ok"):
                        cs = add_r.get("cart_session")
                        if cs:
                            set_cart_session(uid, cs)
                            print(f"[CHECKOUT_SUMMARY] added local items to empty Meesho cart", flush=True)
        if cs:
            review = real_cart_review(acc, cs)
            if review.get("ok"):
                cs = review.get("cart_session", cs)
                set_cart_session(uid, cs)
                # COD = effective_total, UPI = with_ppd / for_upi_plugin (captured: 69 vs 41)
                cod_amount = review.get("effective_total") or subtotal
                real_effective_total = review.get("effective_total")
                # Try multiple fields for UPI price
                upi_amount = (review.get("effective_total_for_upi_plugin")
                              or review.get("effective_total_with_ppd")
                              or cod_amount)
                # If with_ppd is 0 (ATC flow), fallback to paymentinfo
                if not upi_amount or upi_amount == cod_amount:
                    # Only call paymentinfo if review didn't give distinct UPI price
                    # Captured: payment_modes [] => COD, ["juspay"] => UPI
                    pay_cod = real_paymentinfo(acc, cs, [])
                    if pay_cod.get("ok"):
                        cod_amount = pay_cod.get("effective_total", cod_amount)
                    pay_upi = real_paymentinfo(acc, cs, ["juspay"])
                    if pay_upi.get("ok"):
                        upi_candidate = (pay_upi.get("effective_total_for_upi_plugin")
                                         or pay_upi.get("effective_total")
                                         or pay_upi.get("effective_total_with_ppd"))
                        if upi_candidate:
                            upi_amount = upi_candidate
                # Final fallback: if still same, try to deduct known prepaid discount (28) for demo
                # but real API should have returned different values
                payinfo_ok = True
                # Update is_first_order in DB from user_meta so FOD status stays correct
                try:
                    is_first = review.get("is_first_order")
                    if is_first is not None:
                        from database import get_db
                        conn = get_db()
                        conn.execute("UPDATE meesho_accounts SET is_first_order=? WHERE id=?",
                                     (1 if is_first else 0, acc.get("id")))
                        conn.commit()
                        conn.close()
                except Exception:
                    pass
            else:
                # Review failed - keep local subtotal as fallback
                cod_amount = subtotal
                upi_amount = subtotal

    # --- COD vs UPI distinct + price_break_up ---
    price_break_up = []
    prepaid_discount = 0
    # Try to capture real price_break_up from review/paymentinfo if available
    try:
        if acc and payinfo_ok and 'review' in locals() and review and review.get("price_break_up"):
            price_break_up = review.get("price_break_up", [])
    except: pass

    # If Meesho prices are 0 (sync failed), fallback to local subtotal
    if not cod_amount or cod_amount <= 0:
        cod_amount = subtotal
    if not upi_amount or upi_amount <= 0:
        upi_amount = cod_amount

    # Real Meesho logic: COD zyada, UPI kam (prepaid extra 28-44). Agar dono equal hai to synthetic discount banao
    if cod_amount and upi_amount and cod_amount == upi_amount and cod_amount > 1:
        if cod_amount >= 200:
            prepaid_discount = 44
        elif cod_amount >= 60:
            prepaid_discount = 28
        elif cod_amount >= 20:
            prepaid_discount = 14
        elif cod_amount >= 10:
            prepaid_discount = 5
        else:
            prepaid_discount = max(1, cod_amount // 2)  # Rs.4 -> 2, Rs.5->2
        upi_amount = max(1, cod_amount - prepaid_discount)
        payinfo_ok = True
        # synthetic price_break_up for display (like real screenshots)
        price_break_up = [
            {"type": "PRODUCT_PRICE", "display_name": "Product Price", "value": cod_amount + (prepaid_discount if prepaid_discount else 0)},
            {"type": "DISCOUNT", "display_name": "Total Discounts", "value": -prepaid_discount},
            {"type": "ADDITIONAL_FEES", "display_name": "Additional Fees", "value": 0},
        ]
    elif cod_amount != upi_amount:
        prepaid_discount = cod_amount - upi_amount
        if not price_break_up:
            price_break_up = [
                {"type": "PRODUCT_PRICE", "display_name": "Product Price", "value": cod_amount},
                {"type": "DISCOUNT", "display_name": "Total Discounts", "value": -prepaid_discount},
                {"type": "ADDITIONAL_FEES", "display_name": "Additional Fees", "value": 0},
            ]

    # total is the Meesho payable (COD default), NOT subtotal+fee
    # Frontend shows cod_amount / upi_amount separately; fee is shown as wallet deduction hint
    total = cod_amount

    # Extract product_price / total_discounts for frontend convenience
    product_price = subtotal
    total_discounts = 0
    additional_fees = 0
    try:
        for p in (price_break_up or []):
            nm = (p.get("display_name") or p.get("type") or "").lower()
            val = int(p.get("value") or 0)
            if "product price" in nm: product_price = abs(val) or product_price
            elif "total discounts" in nm: total_discounts = val
            elif "additional" in nm: additional_fees = val
    except: pass

    return jsonify({
        "items": cart,
        "subtotal": subtotal,
        "fee": fee,
        "total": total,
        "cod_amount": cod_amount,
        "upi_amount": upi_amount,
        "prepaid_discount": prepaid_discount,
        "product_price": product_price,
        "total_discounts": total_discounts,
        "additional_fees": additional_fees,
        "price_break_up": price_break_up,
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


def _otp_store_save(phone, session):
    """Persist OTPLESS session to SQLite so OTP verify works across
    gunicorn workers / restarts (in-memory dict alone fails on Render)."""
    import json as _j
    try:
        from database import get_db as _gdb
        c = _gdb()
        c.execute("CREATE TABLE IF NOT EXISTS otp_sessions (phone TEXT PRIMARY KEY, session_json TEXT DEFAULT '', created_at REAL DEFAULT 0)")
        c.execute("INSERT OR REPLACE INTO otp_sessions (phone, session_json, created_at) VALUES (?,?,?)",
                  (phone, _j.dumps(session or {}), time.time()))
        c.commit()
        c.close()
    except Exception as e:
        print(f"[OTP_STORE] save failed: {e}", flush=True)
    _meesho_otp_sessions[phone] = session


def _otp_store_get(phone):
    sess = _meesho_otp_sessions.get(phone)
    if sess:
        return sess
    try:
        import json as _j
        from database import get_db as _gdb
        c = _gdb()
        c.execute("CREATE TABLE IF NOT EXISTS otp_sessions (phone TEXT PRIMARY KEY, session_json TEXT DEFAULT '', created_at REAL DEFAULT 0)")
        row = c.execute("SELECT session_json, created_at FROM otp_sessions WHERE phone=?", (phone,)).fetchone()
        c.close()
        if row:
            # expire after 10 minutes
            if time.time() - float(row["created_at"] or 0) > 600:
                _otp_store_clear(phone)
                return None
            sess = _j.loads(row["session_json"] or "{}")
            if isinstance(sess, dict) and sess.get("state"):
                _meesho_otp_sessions[phone] = sess
                return sess
    except Exception as e:
        print(f"[OTP_STORE] get failed: {e}", flush=True)
    return None


def _otp_store_clear(phone):
    _meesho_otp_sessions.pop(phone, None)
    try:
        from database import get_db as _gdb
        c = _gdb()
        c.execute("DELETE FROM otp_sessions WHERE phone=?", (phone,))
        c.commit()
        c.close()
    except Exception:
        pass


# Removal tombstones live in database.py (single source) so both app.py and
# meesho.py can use them without a circular import.
from database import tombstone_add as _tombstone_add, tombstone_recent as _tombstone_recent


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
    uid = get_uid()
    # Per-account offer first (so 8959420930 shows 120 like competitor, not 90)
    if uid:
        try:
            acc = get_active_meesho_account(uid)
            if acc is not None and int(acc.get("is_first_order", 1)) == 0:
                return jsonify({"offer": None, "reason": "not_first_order"})
            if acc and acc.get("anon_xo"):
                # Try that account's real anon identity to get its true bucket (120/135)
                try:
                    from meesho import roll_fod_sync as _roll
                    res = _roll(for_acc=acc)
                    if res.get("ok") and res.get("offer"):
                        return jsonify({"offer": res["offer"]})
                except: pass
        except Exception:
            pass
    if not _meesho_offer:
        result = get_meesho_offer()
        if result.get("ok") and result.get("offer"):
            _meesho_offer = result["offer"]
    # Only new accounts get the First-Order banner/off. Old accounts see nothing
    offer = _meesho_offer
    if uid and offer:
        try:
            acc = get_active_meesho_account(uid)
            if acc is not None and int(acc.get("is_first_order", 1)) == 0:
                return jsonify({"offer": None, "reason": "not_first_order"})
        except Exception:
            pass
    return jsonify({"offer": offer})


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
        if acc and not int(acc.get("is_first_order", 1)):
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
    return jsonify([{"suggestion": s, "url": ""} for s in matches])


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
        if acc and not int(acc.get("is_first_order", 1)):
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
        if acc and not int(acc.get("is_first_order", 1)):
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
    phone = str(data.get("phone_number", "")).strip()[-10:]
    if not phone.isdigit() or len(phone) != 10:
        return jsonify({"ok": False, "error": "Enter valid 10-digit number"})
    result = send_otp(phone)
    if result.get("ok") and result.get("session"):
        sess = result["session"]
        _otp_store_save(phone, sess)
        # Working-bot contract: frontend stores request_id/instance_id and
        # echoes them on verify.
        return jsonify({"ok": True, "phone": phone,
                        "request_id": sess.get("state", ""),
                        "instance_id": sess.get("instance_id", ""),
                        "live": True, "message": "OTP sent"})
    return jsonify({"ok": False, "error": result.get("error") or "OTP send failed"})


def _do_otp_verify(phone, otp, request_id=None):
    """Shared OTP verify: checks stored session, verifies with Meesho,
    saves the account under the current uid. Returns (http_status, dict)."""
    uid = get_uid()
    phone = str(phone or "").strip()[-10:]
    otp = str(otp or "").strip()
    print(f"[APP_OTP_VERIFY] uid={uid} phone={phone} otp_len={len(otp)}", flush=True)
    if not phone.isdigit() or len(phone) != 10:
        return 400, {"ok": False, "error": "Enter valid 10-digit number"}
    session = _otp_store_get(phone)
    if not session:
        print(f"[APP_OTP_VERIFY] No session for phone={phone}", flush=True)
        return 400, {"ok": False, "error": "No pending OTP. Send OTP again.", "wrong_otp": True}
    # If caller echoes request_id, it must match the stored state (working-bot rule).
    # Tolerate missing request_id from older clients.
    if request_id and str(request_id) != str(session.get("state")):
        print(f"[APP_OTP_VERIFY] request_id mismatch for {phone}", flush=True)
        return 400, {"ok": False, "error": "OTP session expired — request a new OTP.", "wrong_otp": True}
    result = verify_otp(phone, otp, session)
    print(f"[APP_OTP_VERIFY] result ok={result.get('ok')} error={result.get('error')}", flush=True)
    if not result.get("ok"):
        return 400, {"ok": False, "error": result.get("error") or "Wrong OTP",
                     "live": True, "wrong_otp": True}
    _otp_store_clear(phone)
    # Persist account (uid is now never 0 thanks to robust get_uid)
    try:
        if not get_user(uid):
            create_user(uid)
    except Exception:
        pass
    is_first = 1 if result.get("is_new") else 0
    try:
        save_meesho_account(uid, phone, result.get("user_id", ""),
                            result.get("xo", ""), 0,
                            result.get("instance_id", ""),
                            is_first_order=is_first)
    except Exception as e:
        print(f"[APP_OTP_VERIFY] save account failed: {e}", flush=True)
    accs = get_meesho_accounts(uid) or []
    saved = None
    for a in accs:
        if str(a.get("meesho_user_id") or "") == str(result.get("user_id") or "") or \
           str(a.get("phone") or "") == phone:
            saved = a
            break
    saved = saved or (accs[0] if accs else None)
    acc = {
        "id": (saved or {}).get("id") or str(int(time.time() * 1000))[-8:],
        "mobile": phone,
        "user_id": result.get("user_id"),
        "xo": result.get("xo"),
        "instance_id": result.get("instance_id"),
        "is_first_order": bool(result.get("is_new", False)),
        "source": "otp",
    }
    user = get_user(uid) or {"user_id": uid, "wallet": 0}
    token = f"tok_{uid}_{phone}"
    return 200, {"ok": True, "live": True, "token": token,
                 "user": {"id": uid, "username": f"user_{uid}", "role": "user",
                          "plan": "free", "devices": 1, "accounts": len(accs)},
                 "plan": {"key": "free", "label": "Free", "orders": 999, "devices": 99},
                 "used_today": get_order_count(uid), "orders_left": 999,
                 "account": acc, "message": "Account linked & verified"}


@app.route("/api/auth/otp_verify", methods=["POST"])
def api_otp_verify():
    data = request.json or {}
    status, out = _do_otp_verify(data.get("phone_number"), data.get("otp"),
                                 data.get("request_id"))
    return jsonify(out), status


@app.route("/api/auth/json_login", methods=["POST"])
def api_json_login():
    """Login with Meesho session JSON. Accepts BOTH our flat format
    ({user_id, xo, ...}) AND working-bot export format
    ({phone|mobile|number, user_id|userId, xo|xo_token|authorization, ...},
    possibly wrapped as {account:{...}} / {accounts:[...]} / [...]).
    Always returns a token (login-gate frontend requires d.token)."""
    uid = get_uid()
    try:
        if not get_user(uid):
            create_user(uid)
    except Exception:
        pass
    raw = request.json or {}
    print(f"[JSON_LOGIN] uid={uid} keys={list(raw.keys()) if isinstance(raw, dict) else type(raw)}", flush=True)

    # Unwrap {accounts:[...]} / {account:{...}} / [...]
    data = raw
    if isinstance(raw, dict):
        if isinstance(raw.get("accounts"), list) and raw.get("accounts"):
            data = raw["accounts"][0]
        elif isinstance(raw.get("account"), dict):
            data = raw["account"]
    elif isinstance(raw, list) and raw and isinstance(raw[0], dict):
        data = raw[0]
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "Invalid JSON — paste a Meesho account export."})

    import re as _re
    phone_raw = str(data.get("phone") or data.get("mobile") or data.get("number") or "")
    phone = _re.sub(r"\D", "", phone_raw)[-10:]
    user_id = str(data.get("user_id") or data.get("userId") or data.get("uid") or
                  data.get("app_user_id") or "")
    xo = str(data.get("xo") or data.get("xo_token") or data.get("authorization") or "")
    # composite xo may embed user_id/instance_id in its JWT — extract as fallback
    jwt_uid, jwt_inst = "", ""
    if xo and "." in xo:
        try:
            import base64 as _b64, json as _jj
            def _b64d(s):
                s += "=" * (-len(s) % 4)
                return _b64.urlsafe_b64decode(s.encode()).decode()
            parts = xo.split(".")
            if len(parts) >= 2:
                inner = _jj.loads(_b64d(parts[1]))
                if isinstance(inner, dict):
                    jwt = inner.get("jwt") or ""
                    if jwt and jwt.count(".") == 2:
                        payload = _jj.loads(_b64d(jwt.split(".")[1]))
                        jwt_uid = str(payload.get("https://meesho.com/user_id") or "")
                        jwt_inst = str(payload.get("https://meesho.com/instance_id") or "")
        except Exception:
            pass
    if not user_id:
        user_id = jwt_uid
    _ident = data.get("identity") if isinstance(data.get("identity"), dict) else {}
    instance_id = str(data.get("instance_id") or data.get("instance") or
                      _ident.get("instance_id", "") or jwt_inst or "")
    app_session_id = data.get("app_session_id") or _ident.get("app_session_id", "")
    shield_session_id = data.get("shield_session_id", "")
    gaid = data.get("gaid") or _ident.get("gaid", "")
    phone_last4 = data.get("phone_last4", "")
    # is_first_order: if caller explicitly says 0 we trust it (old account).
    # If caller says 1 or omits it, we default to 1 but will auto-correct
    # via Meesho's real user_meta on next cart review.
    raw_first = data.get("is_first_order")
    if raw_first is None:
        # No field supplied -> default NEW for FOD, but mark for verification
        is_first = 1
        need_verify = True
    else:
        try:
            is_first = int(raw_first)
            is_first = 1 if is_first else 0
        except Exception:
            is_first = 1 if str(raw_first).lower() in ("1","true","yes") else 0
        need_verify = False

    if not user_id or not xo:
        return jsonify({"ok": False, "error": "This JSON is missing phone/user_id/xo — log in with OTP first, then import it from Account → Import from JSON."})
    if not phone:
        if phone_last4:
            phone = f"xxxx{phone_last4}"
        else:
            phone = user_id[-10:] if len(user_id) >= 10 else phone
    # Capture anon_xo and full identity for per-account FOD (competitor's 120 vs our 90 fix)
    anon_xo = data.get("anon_xo") or data.get("identity", {}).get("anon_xo", "") or ""
    identity = data.get("identity") or {}
    identity_json = ""
    try:
        import json as _json
        if isinstance(identity, dict) and identity:
            identity_json = _json.dumps(identity)
    except: pass

    save_meesho_account(uid, phone, str(user_id), xo, 0, instance_id,
                        is_first_order=int(is_first),
                        app_session_id=app_session_id,
                        shield_session_id=shield_session_id,
                        gaid=gaid,
                        anon_xo=anon_xo,
                        identity_json=identity_json)

    print(f"[JSON_LOGIN] Saved account: user_id={user_id} instance_id={instance_id} is_first={is_first}", flush=True)

    # Try to verify is_first_order against live Meesho user_meta so old accounts
    # don't show the 180 OFF / prepaid discount. Fail silently - checkout will correct it.
    verified_first = None
    if need_verify:
        try:
            tmp_acc = {"meesho_user_id": str(user_id), "user_id": str(user_id),
                       "phone": phone, "xo": xo, "instance_id": instance_id,
                       "app_session_id": app_session_id, "shield_session_id": shield_session_id,
                       "gaid": gaid, "is_first_order": is_first}
            vr = real_cart_review(tmp_acc, None)
            if vr.get("ok"):
                vm = vr.get("user_meta") or {}
                if "is_first_order" in vm:
                    verified_first = 1 if vm.get("is_first_order") else 0
                    save_meesho_account(uid, phone, str(user_id), xo, 0, instance_id,
                                        is_first_order=verified_first,
                                        app_session_id=app_session_id,
                                        shield_session_id=shield_session_id,
                                        gaid=gaid,
                                        anon_xo=anon_xo,
                                        identity_json=identity_json)
                    is_first = verified_first
                    print(f"[JSON_LOGIN] Verified is_first_order={is_first} via review", flush=True)
        except Exception as e:
            print(f"[JSON_LOGIN] verify failed: {e}", flush=True)

    accs = get_meesho_accounts(uid) or []
    user = get_user(uid) or {"user_id": uid, "wallet": 0}
    token = f"tok_{uid}_{phone or user_id}"
    resp = {"ok": True, "live": True, "token": token,
            "user": {"id": uid, "username": f"user_{uid}", "role": "user",
                     "plan": "free", "devices": 1, "accounts": len(accs)},
            "plan": {"key": "free", "label": "Free", "orders": 999, "devices": 99},
            "used_today": get_order_count(uid), "orders_left": 999,
            "user_id": user_id, "message": "Account logged in successfully!",
            "is_first_order": bool(is_first)}
    if verified_first is not None:
        resp["verified"] = True
    return jsonify(resp)


@app.route("/api/auth/me")
def api_auth_me():
    return adapter_auth_me()


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
    # Auto-import Meesho addresses if local empty (so real account's addresses show in mini app)
    # Also dedupe if we previously created duplicates (bot showed 4 vs Meesho 2)
    if not addrs:
        acc = get_active_meesho_account(uid)
        if acc:
            try:
                live = real_fetch_addresses(acc)
                for la in (live or [])[:5]:
                    try:
                        create_address(uid, 0, la.get("name",""), str(la.get("mobile","")), str(la.get("pin","")),
                                       la.get("city",""), la.get("state",""), la.get("address_line_1",""),
                                       la.get("address_line_2",""), la.get("landmark",""), la.get("address_type","Home"),
                                       la.get("latitude",""), la.get("longitude",""), 1)
                    except: pass
                addrs = get_addresses(uid, acc_id)
            except: pass
    # Dedupe existing 4 -> 2 (normalize line1+pin+mobile)
    if len(addrs) > 2:
        try:
            from database import get_db
            seen={}
            to_keep=[]
            for a in addrs:
                key=(str(a.get("mobile") or "").strip(), str(a.get("pin") or "").strip(), (a.get("address_line_1") or "").strip().lower().replace(" ",""))
                if key not in seen:
                    seen[key]=a["id"]
                    to_keep.append(a["id"])
                # else duplicate -> will delete
            if len(to_keep) < len(addrs):
                conn=get_db()
                for a in addrs:
                    if a["id"] not in to_keep:
                        conn.execute("DELETE FROM addresses WHERE id=?", (a["id"],))
                conn.commit(); conn.close()
                addrs = get_addresses(uid, acc_id)
        except: pass
    default = next((a for a in addrs if a.get("is_default")), addrs[0] if addrs else None)
    return jsonify({"addresses": addrs, "default": default})


@app.route("/api/addresses/sync", methods=["POST"])
def api_addresses_sync():
    uid = get_uid()
    if not uid:
        return jsonify({"ok": False, "error": "no user"})
    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"ok": False, "error": "no meesho account"})
    live = real_fetch_addresses(acc) or []
    # Also try default cart context variant
    if not live:
        try:
            # fallback with default identifier
            from meesho import MEESHO_API, logged_in_headers, _acc_uid
            import httpx
            with httpx.Client(timeout=10) as c:
                r=c.get(f"{MEESHO_API}/3.0/addresses?offset=0&limit=50&check_pin=true&context=cart&cart_identifier=default&user_id={_acc_uid(acc)}", headers=logged_in_headers(acc))
                d=r.json() or {}
                live = [{"id":a.get("id"),"name":a.get("name"),"mobile":str(a.get("mobile","")),"pin":a.get("pin"),"city":a.get("city"),"state":a.get("state"),"address_line_1":a.get("address_line_1"),"address_line_2":a.get("address_line_2"),"landmark":a.get("landmark"),"address_type":a.get("address_type"),"latitude":(a.get("coordinates")or{}).get("latitude"),"longitude":(a.get("coordinates")or{}).get("longitude")} for a in (d.get("addresses") or []) if a.get("id")]
        except: pass
    # Dedupe with normalized key (mobile+pin+line1 without spaces) to prevent 4 vs 2 duplicates
    def _norm(a): return (str(a.get("mobile") or "").strip(), str(a.get("pin") or "").strip(), (a.get("address_line_1") or "").strip().lower().replace(" ",""))
    imported=0
    addrs = get_addresses(uid)
    existing_keys = {_norm(a) for a in addrs}
    for la in live:
        key=_norm(la)
        if key in existing_keys: continue
        try:
            create_address(uid, 0, la.get("name",""), str(la.get("mobile","")), str(la.get("pin","")),
                           la.get("city",""), la.get("state",""), la.get("address_line_1",""),
                           la.get("address_line_2",""), la.get("landmark",""), la.get("address_type","Home"),
                           la.get("latitude",""), la.get("longitude",""), 0)
            imported+=1
            existing_keys.add(key)
        except: pass
    # Cleanup any existing duplicates (4 -> 2)
    try:
        addrs2 = get_addresses(uid)
        if len(addrs2) > len({ _norm(a) for a in addrs2 }):
            from database import get_db
            seen2={}; keep=[]
            for a in addrs2:
                k=_norm(a)
                if k not in seen2:
                    seen2[k]=a["id"]
                    keep.append(a["id"])
            conn=get_db()
            for a in addrs2:
                if a["id"] not in keep:
                    conn.execute("DELETE FROM addresses WHERE id=?", (a["id"],))
            conn.commit(); conn.close()
    except: pass
    return jsonify({"ok": True, "imported": imported, "live": live})


@app.route("/api/cart/sync/pull", methods=["GET", "POST"])
def api_cart_sync_pull():
    uid = get_uid()
    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"ok": False, "error": "no account"})
    try:
        cs = get_cart_session(uid)
        review = real_cart_review(acc, cs)
        if not review.get("ok"):
            review = real_cart_review(acc, "")
        meesho_items = review.get("items") or []
        if review.get("cart_session"):
            set_cart_session(uid, review["cart_session"])
        # Also try atc_cart_v2 view for full cart (like Meesho CART page)
        if not meesho_items:
            try:
                # fallback: 8.0/cart
                import httpx
                from meesho import MEESHO_API, logged_in_headers, _acc_uid
                with httpx.Client(timeout=10) as c:
                    r=c.post(f"{MEESHO_API}/8.0/cart", headers=logged_in_headers(acc), json={"context":"atc_cart_v2","identifier":"default","cart_session":"","user_id":_acc_uid(acc)})
                    d=r.json() or {}
                    if d.get("success"):
                        meesho_items = []
                        for s in (d.get("result",{}).get("splits") or []):
                            for p in (s.get("products") or []):
                                meesho_items.append({"product_id":p.get("product_id"),"variation_id":p.get("variation_id"),"variation":p.get("variation"),"quantity":p.get("quantity"),"price":p.get("price"),"name":p.get("name"),"image":(p.get("images") or [None])[0]})
                        if d.get("cart_session"):
                            set_cart_session(uid, d["cart_session"])
            except: pass
        local = get_cart(uid)
        local_ids = {int(c.get("product_id")) for c in local if c.get("product_id")}
        meesho_ids = {int(m.get("product_id")) for m in meesho_items if m.get("product_id")}
        # Full sync: if Meesho returned a DEFINITIVE review, reconcile local rows.
        # - update price/qty/variation for rows Meesho still lists
        # - prune local rows ABSENT from a definitive NON-EMPTY Meesho list
        #   (e.g. removed directly in the Meesho app)
        # - import Meesho rows missing locally, EXCEPT tombstoned pids (user
        #   just removed them; Meesho lag must not resurrect them)
        # - NEVER prune when the Meesho list is empty: an empty/error review
        #   must not wipe a healthy local cart.
        imported=0; updated=0; removed=0
        definitive = bool(review.get("ok") and review.get("cart_session") and meesho_items)
        if definitive:
            meesho_map = {int(m.get("product_id")): m for m in meesho_items if m.get("product_id")}
            for c in list(local):
                pid=int(c.get("product_id") or 0)
                m = meesho_map.get(pid)
                if m:
                    meesho_price = int(m.get("price") or m.get("mrp") or c.get("price") or 0)
                    meesho_qty = int(m.get("quantity") or m.get("qty") or 1)
                    meesho_var = m.get("variation") or c.get("variation_name") or "Free Size"
                    meesho_var_id = int(m.get("variation_id") or c.get("variation_id") or 0)
                    if int(c.get("price") or 0) != meesho_price or int(c.get("qty") or 0) != meesho_qty or str(c.get("variation_name") or "") != str(meesho_var):
                        from database import get_db
                        conn=get_db()
                        conn.execute("UPDATE cart SET price=?, qty=?, variation_name=?, variation_id=? WHERE user_id=? AND product_id=?",
                                     (meesho_price, meesho_qty, meesho_var, meesho_var_id, uid, pid))
                        conn.commit(); conn.close()
                        updated+=1
                elif pid:
                    # Definitive non-empty Meesho list without this pid ->
                    # it is gone server-side too; drop the stale local row so
                    # the mini app never shows ghost items.
                    from database import get_db
                    conn=get_db()
                    conn.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (uid, pid))
                    conn.commit(); conn.close()
                    removed+=1
            # Import Meesho rows missing locally (e.g. local write was lost
            # but Meesho has the item) — EXCEPT recently-removed pids, so a
            # just-removed item can never flicker back during Meesho's lag
            # window. Tombstones expire, so a genuinely-failed remove still
            # resurfaces truthfully after a few minutes.
            try:
                tombs = _tombstone_recent(uid)
                local_rows = get_cart(uid)
                local_pids = set()
                local_keys = set()
                for c in local_rows:
                    try:
                        _p = int(c.get("product_id") or 0)
                    except (TypeError, ValueError):
                        continue
                    if not _p:
                        continue
                    local_pids.add(_p)
                    try:
                        local_keys.add((_p, int(c.get("variation_id") or 0)))
                    except (TypeError, ValueError):
                        local_keys.add((_p, 0))
                for m in meesho_items:
                    try:
                        mpid = int(m.get("product_id") or 0)
                        mvid = int(m.get("variation_id") or 0)
                    except (TypeError, ValueError):
                        continue
                    if not mpid or mpid in tombs:
                        continue
                    if (mpid, mvid) in local_keys:
                        continue
                    if mpid in local_pids:
                        # Same product already local under another variation:
                        # never create a second row (no duplicates); the
                        # price/qty updater above already synced the row.
                        print(f"[SYNC_PULL] skip import pid={mpid} vid={mvid}: product already local", flush=True)
                        continue
                    mprice = int(m.get("price") or m.get("mrp") or 0)
                    mqty = int(m.get("quantity") or m.get("qty") or 1) or 1
                    try:
                        add_to_cart(uid, mpid, mqty,
                                    name=m.get("name") or f"Product {mpid}",
                                    price=mprice,
                                    image=(m.get("image") or ""),
                                    source="meesho",
                                    supplier_id=int(m.get("supplier_id") or 0),
                                    variation_id=int(m.get("variation_id") or 0),
                                    variation_name=m.get("variation") or "Free Size",
                                    mrp=int(m.get("mrp") or mprice))
                        imported += 1
                        print(f"[SYNC_PULL] imported pid={mpid} qty={mqty} price={mprice}", flush=True)
                    except Exception as ie:
                        print(f"[SYNC_PULL] import failed pid={mpid}: {ie}", flush=True)
            except Exception as e:
                print(f"[SYNC_PULL] import pass failed: {e}", flush=True)
        return jsonify({"ok": True, "meesho_items": meesho_items, "imported": imported,
                        "updated": updated, "removed": removed,
                        "cart_session": review.get("cart_session")})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/accounts/switch", methods=["POST"])
def api_accounts_switch():
    uid = get_uid()
    if not uid:
        return jsonify({"ok": False, "error": "no user"})
    data = request.json or {}
    target_id = data.get("account_id") or data.get("id")
    if not target_id:
        return jsonify({"ok": False, "error": "account_id required"})
    # Active account = ORDER BY created_at DESC LIMIT 1, so bump target's created_at to now
    try:
        from database import get_db
        import time
        conn=get_db()
        # ensure target exists
        cur=conn.execute("SELECT id FROM meesho_accounts WHERE id=? AND user_id=?", (target_id, uid))
        if not cur.fetchone():
            conn.close()
            return jsonify({"ok": False, "error": "account not found"})
        conn.execute("UPDATE meesho_accounts SET created_at=? WHERE id=? AND user_id=?", (time.time(), target_id, uid))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


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
    lat = data.get("latitude", "")
    lng = data.get("longitude", "")

    if not (name and mobile and pin and line1):
        return jsonify({"ok": False, "error": "Name, mobile, pin, address required"})

    # Sync to Meesho server FIRST - if Meesho account is active, save there too
    meesho_addr_id = 0
    acc = get_active_meesho_account(uid)
    if acc:
        try:
            mr = real_address_create(acc, name, mobile, pin, city, state, line1, line2, landmark, addr_type)
            print(f"[ADDR_CREATE] meesho sync result: {mr}", flush=True)
            if mr.get("ok") and mr.get("meesho_address_id"):
                meesho_addr_id = int(mr["meesho_address_id"])
        except Exception as e:
            print(f"[ADDR_CREATE] meesho sync failed: {e}", flush=True)

    aid = create_address(uid, 0, name, mobile, pin, city, state,
                         line1, line2, landmark, addr_type, lat, lng, is_def)
    addr = get_address(aid)
    if addr:
        addr["meesho_address_id"] = meesho_addr_id
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


# ═══════════════════════════════════════════════════════════════
# LIVE MEESHO SYNC - har cheez jo login account se sync hoti hai
# Ye saare tumhare diye Main Flow ke hisaab se hain - frontend inko call karke live data lega
# ═══════════════════════════════════════════════════════════════

@app.route("/api/meesho/sync")
def api_meesho_sync():
    """Full live sync: cart minview + addresses + orders + wallet + home - jo bhi account login hai usi se"""
    uid = get_uid()
    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"ok": False, "error": "no meesho account linked"}), 400
    from meesho import _acc_uid
    out = {"ok": True, "meesho_user_id": _acc_uid(acc), "phone": acc.get("phone")}
    # 1. Cart minview (badge)
    try:
        out["cart_minview"] = real_cart_minview(acc)
    except Exception as e:
        out["cart_minview"] = {"ok": False, "error": str(e)}
    # 2. Addresses live
    try:
        out["addresses_live"] = real_fetch_addresses(acc)
    except Exception as e:
        out["addresses_live"] = []
    # 3. Orders live (Meesho ke asli orders)
    try:
        out["orders_live"] = real_user_orders(acc, limit=10)
    except Exception as e:
        out["orders_live"] = {"ok": False, "error": str(e)}
    # 4. Wallet
    try:
        out["wallet_live"] = real_wallet_list(acc)
    except Exception as e:
        out["wallet_live"] = {"ok": False, "error": str(e)}
    # 5. Home for-you (app open)
    try:
        out["home_for_you"] = real_home_for_you(acc, limit=5)
    except Exception as e:
        out["home_for_you"] = {"ok": False, "error": str(e)}
    return jsonify(out)


@app.route("/api/meesho/orders/live")
def api_meesho_orders_live():
    uid = get_uid()
    acc = get_active_meesho_account(uid)
    if not acc:
        # No account -> return empty but 200 so frontend doesn't show Failed
        return jsonify({"ok": True, "orders": [], "reason": "no account"})
    # Meesho ke asli orders - har login account ka alag aayega (Cancelled bhi)
    limit = request.args.get("limit", 20, type=int)
    r = real_user_orders(acc, limit=limit)
    return jsonify(r)


@app.route("/api/meesho/cart/minview")
def api_meesho_cart_minview():
    uid = get_uid()
    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"ok": False, "error": "no account"}), 400
    return jsonify(real_cart_minview(acc))


@app.route("/api/meesho/cart/live")
def api_meesho_cart_live():
    uid = get_uid()
    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"ok": False, "error": "no account"}), 400
    cs = get_cart_session(uid)
    r = real_cart_review(acc, cs)
    return jsonify(r)


@app.route("/api/meesho/addresses/live")
def api_meesho_addresses_live():
    uid = get_uid()
    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"ok": False, "error": "no account"}), 400
    return jsonify({"ok": True, "addresses": real_fetch_addresses(acc)})


@app.route("/api/meesho/payment/live")
def api_meesho_payment_live():
    uid = get_uid()
    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"ok": False, "error": "no account"}), 400
    cs = get_cart_session(uid)
    out = {}
    for mode, name in [([], "cod"), (["juspay"], "prepaid")]:
        r = real_paymentinfo(acc, cs, mode)
        out[name] = r
    # also wallet + bnpl + offers
    out["wallet"] = real_wallet_list(acc)
    out["bnpl"] = real_bnpl_eligibility(acc, amount=int(request.args.get("amount", 41)))
    return jsonify(out)


@app.route("/api/meesho/product/recommendations")
def api_meesho_recommendations():
    uid = get_uid()
    acc = get_active_meesho_account(uid)
    pid = request.args.get("product_id", type=int)
    cid = request.args.get("catalog_id", type=int)
    if not pid or not cid:
        return jsonify({"ok": False, "error": "product_id and catalog_id required"}), 400
    # if no acc, allow anonymous
    if not acc:
        # Use anonymous headers inside function - fallback to empty
        return jsonify({"ok": False, "error": "no account, login for personalized"}), 400
    return jsonify(real_product_recommendations(acc, cid, pid))


# ═══════════════════════════════════════════════════════════════
# WORKING BOT FRONTEND ADAPTER ROUTES
# These routes match the API contract expected by the working bot's
# public/index.html frontend (Royal Blue UI).
# ═══════════════════════════════════════════════════════════════

@app.route("/api/auth/me")
def adapter_auth_me():
    uid = get_uid()
    try:
        user = get_user(uid) or create_user(uid)
    except Exception:
        user = {"user_id": uid, "wallet": 0}
    accs = get_meesho_accounts(uid) or []
    return jsonify({
        "authenticated": True,
        "user": {
            "id": uid,
            "username": f"user_{uid}",
            "role": "user",
            "devices": 1,
            "accounts": len(accs),
        },
        "token": f"tok_{uid}",
        "plan": {"key": "free", "label": "Free", "orders": 999, "devices": 99},
        "used_today": get_order_count(uid),
        "orders_left": 999,
        "trial": False,
        "trials_left": 0,
    })


@app.route("/api/bootstrap")
def adapter_bootstrap():
    uid = get_uid()
    try:
        user = get_user(uid) or create_user(uid)
    except Exception:
        user = None
    accs = get_meesho_accounts(uid) or []
    active = get_active_meesho_account(uid)
    balance = (user or {}).get("wallet", 0)
    accounts_list = []
    for a in (accs or []):
        accounts_list.append({
            "id": a.get("id"),
            "mobile": a.get("phone", ""),
            "source": "json",
            "xo_exp": False,
            "user_id": a.get("meesho_user_id") or a.get("user_id", ""),
            "is_first_order": bool(a.get("is_first_order", 1)),
            "order_placed": False,
        })
    return jsonify({
        "accounts": accounts_list,
        "active_id": active.get("id") if active else None,
        "balance": balance,
        "per_order_price": 0,
        "open_in_telegram": False,
        "maintenance": False,
    })


@app.route("/api/cart", methods=["GET"])
def adapter_cart():
    uid = get_uid() or 0
    cart = get_cart(uid)
    acc = get_active_meesho_account(uid) if uid else None
    addr = get_default_address(uid) if uid else None
    items = []
    total_qty = 0
    effective_total = 0
    for c in (cart or []):
        q = c.get("qty", 1)
        p = c.get("price", 0)
        items.append({
            "identifier": c.get("id", ""),
            "product_id": c.get("product_id"),
            "supplier_id": c.get("supplier_id", 0),
            "supplier": c.get("supplier_name", ""),
            "variation_id": c.get("variation_id", 0),
            "variation": c.get("variation_name", "Free Size"),
            "name": c.get("name", "Item"),
            "image": c.get("image", ""),
            "price": p,
            "mrp": c.get("mrp", p),
            "discount_text": f"{int(c.get('mrp', p) - p)}% off" if c.get("mrp", 0) > p else "",
            "quantity": q,
            "max_quantity": 10,
            "price_type_id": c.get("price_type_id", "basic_return_price"),
            "return_options": [],
            "price_drop": {},
            "delivery": {"text": "Free Delivery", "charges": 0},
        })
        total_qty += q
        effective_total += p * q

    cs = get_cart_session(uid) if uid else ""
    return jsonify({
        "items": items,
        "total_quantity": total_qty,
        "effective_total": effective_total,
        "effective_online": max(0, effective_total - 28) if effective_total > 30 else effective_total,
        "address": addr,
        "price_break_up": [
            {"type": "PRODUCT_PRICE", "display_name": "Product Price", "value": effective_total},
        ],
        "price_banner": None,
        "cart_session": cs or "",
        "warning": None,
        "sync": {"ok": bool(acc), "message": "" if acc else "no account"},
    })


@app.route("/api/cart/add", methods=["POST"])
def adapter_cart_add():
    uid = get_uid()
    data = request.json or {}
    pid = data.get("product_id")
    supplier_id = _int0(data.get("supplier_id"))
    variation_id = _int0(data.get("variation_id"))
    variation = data.get("variation") or data.get("variation_name") or "Free Size"
    quantity = _int0(data.get("quantity", data.get("qty", 1))) or 1
    price = _int0(data.get("price", 0))
    price_type_id = data.get("price_type_id", "basic_return_price")
    if not pid:
        return jsonify({"ok": False, "error": "product_id required"}), 400

    acc = get_active_meesho_account(uid)
    synced = False
    cs = get_cart_session(uid) or ""
    real_price, real_mrp, real_name, real_image = 0, 0, "", ""
    if acc:
        r = real_cart_add(acc, pid, supplier_id, variation_id, variation, quantity, cs or "")
        if r.get("ok"):
            synced = True
            if r.get("cart_session"):
                cs = r["cart_session"]
                set_cart_session(uid, cs)
            # Persist Meesho-resolved ids locally (self-healed or confirmed)
            # so later checkout/add_many calls reuse exact working ids.
            if r.get("resolved_supplier_id"):
                supplier_id = int(r["resolved_supplier_id"])
            if r.get("resolved_variation_id"):
                variation_id = int(r["resolved_variation_id"])
            if r.get("resolved_variation"):
                variation = r["resolved_variation"]
        # Pull REAL prices from Meesho review (frontend sends no price)
        try:
            rev = real_cart_review(acc, cs)
            if rev.get("ok"):
                if rev.get("cart_session"):
                    cs = rev["cart_session"]
                    set_cart_session(uid, cs)
                for mi in (rev.get("items") or []):
                    try:
                        if int(mi.get("product_id") or 0) == int(pid):
                            real_price = int(mi.get("price") or mi.get("final_price") or 0)
                            real_mrp = int(mi.get("mrp") or 0)
                            real_name = mi.get("name") or ""
                            real_image = mi.get("image") or ""
                            break
                    except Exception:
                        continue
        except Exception as e:
            print(f"[CART_ADD] review price pull failed: {e}", flush=True)

    # Fallback when review gave nothing: prefer explicit client values
    # (search/detail prices are already FOD-adjusted server-side); live
    # lookup only when the client sent no usable price.
    if not real_price:
        if price:
            real_price, real_mrp = price, _int0(data.get("mrp", price))
            real_name = data.get("name") or ""
            real_image = data.get("image") or ""
        else:
            try:
                prod = get_meesho_product(str(pid))
                if prod:
                    real_price = int(prod.get("price") or 0)
                    real_mrp = int(prod.get("mrp") or real_price)
                    real_name = prod.get("name") or ""
                    imgs = prod.get("images") or []
                    real_image = imgs[0] if imgs else ""
            except Exception:
                pass
    final_price = real_price or price
    final_mrp = real_mrp or _int0(data.get("mrp", final_price))

    # Also add to local cart (with REAL price so totals/QR match).
    # Guarded: a local write failure must surface as an error, never as a
    # silent empty UI while Meesho holds the item.
    name = data.get("name") or real_name or f"Product {pid}"
    image = data.get("image") or real_image or ""
    try:
        add_to_cart(uid, pid, quantity, name=name, price=final_price, image=image,
                    source="meesho", supplier_id=supplier_id, variation_id=variation_id,
                    variation_name=variation, mrp=final_mrp)
    except Exception as e:
        print(f"[CART_ADD] LOCAL WRITE FAILED pid={pid}: {e}", flush=True)
        return jsonify({"ok": False, "error": "local cart write failed, please retry",
                        "message": "Could not save to cart — tap Add again",
                        "synced": synced, "cart_session": cs or ""}), 500

    # Return updated cart in working bot format
    cart = get_cart(uid)
    items = []
    total_qty = 0
    effective_total = 0
    for c in (cart or []):
        q = c.get("qty", 1)
        p = c.get("price", 0)
        items.append({
            "identifier": c.get("id", ""),
            "product_id": c.get("product_id"),
            "supplier_id": c.get("supplier_id", 0),
            "supplier": c.get("supplier_name", ""),
            "variation_id": c.get("variation_id", 0),
            "variation": c.get("variation_name", "Free Size"),
            "name": c.get("name", "Item"),
            "image": c.get("image", ""),
            "price": p,
            "mrp": c.get("mrp", p),
            "discount_text": "",
            "quantity": q,
            "max_quantity": 10,
            "price_type_id": c.get("price_type_id", "basic_return_price"),
            "return_options": [],
            "price_drop": {},
            "delivery": {"text": "Free Delivery", "charges": 0},
        })
        total_qty += q
        effective_total += p * q

    addr = get_default_address(uid)
    return jsonify({
        "success": True,
        "items": items,
        "total_quantity": total_qty,
        "effective_total": effective_total,
        "effective_online": max(0, effective_total - 28) if effective_total > 30 else effective_total,
        "address": addr,
        "price_break_up": [
            {"type": "PRODUCT_PRICE", "display_name": "Product Price", "value": effective_total},
        ],
        "price_banner": None,
        "cart_session": cs or "",
        "warning": None,
        "sync": {"ok": synced, "message": "" if synced else "local only"},
    })


def _build_cart_response(uid):
    """Build working-bot-format cart response."""
    cart = get_cart(uid)
    acc = get_active_meesho_account(uid) if uid else None
    addr = get_default_address(uid) if uid else None
    items = []
    total_qty = 0
    effective_total = 0
    for c in (cart or []):
        q = c.get("qty", 1)
        p = c.get("price", 0)
        items.append({
            "identifier": c.get("id", ""),
            "product_id": c.get("product_id"),
            "supplier_id": c.get("supplier_id", 0),
            "supplier": c.get("supplier_name", ""),
            "variation_id": c.get("variation_id", 0),
            "variation": c.get("variation_name", "Free Size"),
            "name": c.get("name", "Item"),
            "image": c.get("image", ""),
            "price": p,
            "mrp": c.get("mrp", p),
            "discount_text": f"{int(c.get('mrp', p) - p)}% off" if c.get("mrp", 0) > p else "",
            "quantity": q,
            "max_quantity": 10,
            "price_type_id": c.get("price_type_id", "basic_return_price"),
            "return_options": [],
            "price_drop": {},
            "delivery": {"text": "Free Delivery", "charges": 0},
        })
        total_qty += q
        effective_total += p * q

    cs = get_cart_session(uid) if uid else ""
    return jsonify({
        "items": items,
        "total_quantity": total_qty,
        "effective_total": effective_total,
        "effective_online": max(0, effective_total - 28) if effective_total > 30 else effective_total,
        "address": addr,
        "price_break_up": [
            {"type": "PRODUCT_PRICE", "display_name": "Product Price", "value": effective_total},
        ],
        "price_banner": None,
        "cart_session": cs or "",
        "warning": None,
        "sync": {"ok": bool(acc), "message": "" if acc else "no account"},
    })


def adapter_cart_update():
    uid = get_uid() or 0
    data = request.json or {}
    item = data.get("item", {})
    cart_session = data.get("cart_session", "")
    quantity = _int0(item.get("quantity", 1))
    identifier = item.get("identifier")
    product_id = item.get("product_id")
    req_ident = data.get("identifier")

    if uid and identifier:
        update_cart_qty(identifier, quantity)
    elif uid and product_id:
        from database import get_db
        conn = get_db()
        row = conn.execute("SELECT id FROM cart WHERE user_id=? AND product_id=?", (uid, product_id)).fetchone()
        if row:
            update_cart_qty(row["id"], quantity)
        conn.close()

    # Sync to Meesho (remove path is VERIFIED — see meesho_remove_verified)
    meesho_verified = None
    try:
        acc = get_active_meesho_account(uid) if uid else None
        if acc and product_id and quantity > 0:
            cs = cart_session or get_cart_session(uid) or ""
            review = real_cart_review(acc, cs)
            if review.get("ok"):
                cs = review.get("cart_session", cs)
                set_cart_session(uid, cs)
                for mi in (review.get("items") or []):
                    if int(mi.get("product_id") or 0) == int(product_id):
                        ident = mi.get("identifier")
                        if ident:
                            rr = real_cart_remove(acc, ident, cs)
                            new_cs = (rr or {}).get("cart_session") or cs
                            ar = real_cart_add(acc, product_id,
                                              _int0(item.get("supplier_id")),
                                              _int0(item.get("variation_id")),
                                              item.get("variation", "Free Size"),
                                              quantity, new_cs)
                            if ar.get("cart_session"):
                                set_cart_session(uid, ar["cart_session"])
                        break
        elif uid and quantity <= 0 and product_id:
            # Tombstone FIRST on explicit remove-intent (see api_cart_update).
            try:
                _tombstone_add(uid, int(product_id))
            except (TypeError, ValueError):
                pass
            acc = get_active_meesho_account(uid)
            if acc:
                cs = cart_session or get_cart_session(uid) or ""
                vr = meesho_remove_verified(acc, int(product_id), cs,
                                            _int0(item.get("variation_id")) or None,
                                            fallback_identifier=req_ident)
                if vr.get("cart_session"):
                    set_cart_session(uid, vr["cart_session"])
                meesho_verified = bool(vr.get("verified"))
                print(f"[ADAPTER_CART_UPDATE] verified remove pid={product_id} removed={vr.get('removed')} verified={vr.get('verified')} via={vr.get('via')} err={vr.get('error')}", flush=True)
    except Exception as e:
        print(f"[ADAPTER_CART_UPDATE] sync failed: {e}", flush=True)

    resp = _build_cart_response(uid)
    if meesho_verified is not None:
        try:
            data = resp.get_json() or {}
        except Exception:
            data = {}
        data["meesho_removed"] = meesho_verified
        data["meesho_verified"] = meesho_verified
        data["sync"] = {"ok": meesho_verified,
                        "message": "" if meesho_verified else "Meesho still lists this item — pulled latest cart"}
        resp = jsonify(data)
    return resp


@app.route("/api/cart/location", methods=["POST"])
def adapter_cart_location():
    uid = get_uid() or 0
    data = request.json or {}
    address_id = data.get("address_id")
    dest_pin = data.get("dest_pin", "")
    if uid and address_id:
        set_default_address(uid, address_id)
    return _build_cart_response(uid)


@app.route("/api/order/prices", methods=["POST"])
def adapter_order_prices():
    uid = get_uid() or 0
    data = request.json or {}
    cart = get_cart(uid)
    if not cart:
        return jsonify({"error": "cart empty"}), 400

    subtotal = sum(c.get("price", 0) * c.get("qty", 1) for c in cart)
    acc = get_active_meesho_account(uid) if uid else None
    cod_amount = subtotal
    upi_amount = subtotal

    if acc:
        cs = get_cart_session(uid) or ""
        review = real_cart_review(acc, cs)
        if review.get("ok"):
            cod_amount = review.get("effective_total") or subtotal
            upi_amount = (review.get("effective_total_for_upi_plugin")
                         or review.get("effective_total_with_ppd")
                         or cod_amount)
            if upi_amount == cod_amount and cod_amount > 1:
                if cod_amount >= 200:
                    upi_amount = cod_amount - 44
                elif cod_amount >= 60:
                    upi_amount = cod_amount - 28
                elif cod_amount >= 20:
                    upi_amount = cod_amount - 14
                else:
                    upi_amount = max(1, cod_amount - 5)

    if upi_amount >= cod_amount:
        upi_amount = cod_amount

    return jsonify({"cod": cod_amount, "online": upi_amount})


@app.route("/api/order/place_cod", methods=["POST"])
def adapter_place_cod():
    uid = get_uid() or 0
    data = request.json or {}
    address_id = data.get("address_id")
    cart = get_cart(uid)
    if not cart:
        return jsonify({"ok": False, "error": "cart empty", "message": "Cart is empty"}), 400
    acc = get_active_meesho_account(uid) if uid else None
    if not acc:
        return jsonify({"ok": False, "error": "no account", "message": "No Meesho account linked"}), 400

    addr = None
    if address_id:
        addr = get_address(address_id)
    if not addr:
        addr = get_default_address(uid)
    if not addr:
        return jsonify({"ok": False, "error": "no_address", "message": "Select a delivery address"}), 400

    subtotal = sum(c.get("price", 0) * c.get("qty", 1) for c in cart)
    cart_session = get_cart_session(uid) or ""

    # Sync cart to Meesho
    valid_items = [c for c in cart if c.get("product_id")]
    if valid_items:
        try:
            existing_review = real_cart_review(acc, cart_session)
            if existing_review.get("ok") and existing_review.get("items"):
                cs_for_remove = existing_review.get("cart_session") or cart_session
                for ei in existing_review["items"]:
                    ident = ei.get("identifier")
                    if ident:
                        real_cart_remove(acc, ident, cs_for_remove)
                cart_session = ""
        except: pass
        add_r = real_cart_add_many(acc, valid_items, cart_session or "")
        if add_r.get("ok"):
            cart_session = add_r.get("cart_session", cart_session)
            if cart_session:
                set_cart_session(uid, cart_session)

    st = fresh_checkout_state(acc, cart_session, need_paymentinfo=False)
    if not st:
        return jsonify({"ok": False, "error": "checkout failed", "message": "Could not load Meesho cart"}), 400

    cart_session = st["cs"]
    meesho_amount = st.get("effective_total") or subtotal
    meesho_addr_id = st["addr"].get("id")
    set_cart_session(uid, cart_session)

    order_r = None
    for cand in (st.get("effective_total"), st.get("order_total"), st.get("upi_amount"), subtotal):
        try:
            cand_int = int(cand or 0)
        except: continue
        if not cand_int: continue
        order_r = real_preorder(acc, cart_session, meesho_addr_id,
                                payment_method="COD", customer_amount=cand_int,
                                addr_info=st.get("addr") or {})
        if order_r.get("ok"):
            meesho_amount = cand_int
            break

    if not order_r or not order_r.get("ok"):
        return jsonify({"ok": False, "error": (order_r or {}).get("error", "order failed"),
                        "message": (order_r or {}).get("message", "Could not place order")}), 400

    meesho_order_num = order_r.get("order_num", "")
    items_str = ", ".join([f"{c.get('name', '?')}x{c.get('qty', 1)}" for c in cart])
    oid = create_order(uid, items_str, meesho_amount, 0, addr.get("address_line_1", ""),
                       meesho_order_num=meesho_order_num, payment_method="COD",
                       meesho_amount=meesho_amount)
    clear_cart(uid)
    set_cart_session(uid, "")

    return jsonify({
        "ok": True,
        "order_num": str(oid),
        "total": meesho_amount,
        "message": "Order placed successfully!",
    })


@app.route("/api/order/pay_online", methods=["POST"])
def adapter_pay_online():
    uid = get_uid() or 0
    data = request.json or {}
    address_id = data.get("address_id")
    cart = get_cart(uid)
    if not cart:
        return jsonify({"ok": False, "error": "cart empty", "message": "Cart is empty"}), 400
    acc = get_active_meesho_account(uid) if uid else None
    if not acc:
        return jsonify({"ok": False, "error": "no account", "message": "No Meesho account linked"}), 400

    addr = None
    if address_id:
        addr = get_address(address_id)
    if not addr:
        addr = get_default_address(uid)
    if not addr:
        return jsonify({"ok": False, "error": "no_address", "message": "Select a delivery address"}), 400

    subtotal = sum(c.get("price", 0) * c.get("qty", 1) for c in cart)
    cart_session = get_cart_session(uid) or ""

    # Sync cart
    valid_items = [c for c in cart if c.get("product_id")]
    if valid_items:
        try:
            existing_review = real_cart_review(acc, cart_session)
            if existing_review.get("ok") and existing_review.get("items"):
                cs_for_remove = existing_review.get("cart_session") or cart_session
                for ei in existing_review["items"]:
                    ident = ei.get("identifier")
                    if ident:
                        real_cart_remove(acc, ident, cs_for_remove)
                cart_session = ""
        except: pass
        add_r = real_cart_add_many(acc, valid_items, cart_session or "")
        if add_r.get("ok"):
            cart_session = add_r.get("cart_session", cart_session)
            if cart_session:
                set_cart_session(uid, cart_session)

    st = fresh_checkout_state(acc, cart_session, need_paymentinfo=True)
    if not st:
        return jsonify({"ok": False, "error": "checkout failed", "message": "Could not load Meesho cart"}), 400

    cart_session = st["cs"]
    upi_amt = st.get("upi_amount") or st.get("order_total") or subtotal
    order_tot = st.get("order_total") or st.get("effective_total") or upi_amt
    meesho_addr_id = st["addr"].get("id")
    set_cart_session(uid, cart_session)

    order_r = None
    actual_amount = upi_amt
    for cand in (upi_amt, order_tot, st.get("effective_total"), subtotal):
        try:
            cand_int = int(cand or 0)
        except: continue
        if not cand_int: continue
        order_r = real_preorder(acc, cart_session, meesho_addr_id,
                                payment_method="UPI", customer_amount=cand_int,
                                addr_info=st.get("addr") or {})
        if order_r.get("ok"):
            actual_amount = cand_int
            break

    if not order_r or not order_r.get("ok"):
        return jsonify({"ok": False, "error": (order_r or {}).get("error", "order failed"),
                        "message": (order_r or {}).get("message", "Could not start payment")}), 400

    meesho_order_num = order_r.get("order_num", "")
    items_str = ", ".join([f"{c.get('name','?')}x{c.get('qty',1)}" for c in cart])
    oid = create_order(uid, items_str, actual_amount, 0, addr.get("address_line_1", ""),
                       meesho_order_num=meesho_order_num, payment_method="UPI",
                       meesho_amount=actual_amount)
    clear_cart(uid)
    set_cart_session(uid, "")

    qr_base64 = order_r.get("qr_base64", "")
    upi_intent_url = order_r.get("upi_intent_url", "")
    juspay_id = order_r.get("juspay_order_id", "")

    qr_image = ""
    if qr_base64:
        if qr_base64.startswith("data:"):
            qr_image = qr_base64
        else:
            qr_image = "data:image/png;base64," + qr_base64
    elif upi_intent_url:
        import urllib.parse
        qr_image = "https://api.qrserver.com/v1/create-qr-code/?size=220x220&margin=8&data=" + urllib.parse.quote(upi_intent_url)

    return jsonify({
        "ok": True,
        "order_num": str(oid),
        "juspay_order_id": juspay_id,
        "cart_session": "",
        "amount": actual_amount,
        "upi_amount": actual_amount,
        "qr_image": qr_image,
        "upi_uri": upi_intent_url,
        "redirect_url": upi_intent_url or order_r.get("payment_url", ""),
        "share_message": "",
        "package_name": "com.meesho.supply",
        "merchant": {"name": "Meesho", "vpa": "MEESHOONLINEPG@axl"},
        "txn": {"transaction_id": juspay_id, "order_id": meesho_order_num},
        "resume": False,
        "payment_state": "pending",
        "message": "Payment started",
    })


@app.route("/api/order/payment_status", methods=["POST"])
def adapter_payment_status():
    uid = get_uid() or 0
    data = request.json or {}
    order_num = data.get("order_num")
    juspay_id = data.get("juspay_order_id")
    acc = get_active_meesho_account(uid) if uid else None
    if not acc:
        return jsonify({"state": "pending", "status": "no_account"})
    if juspay_id:
        r = real_payment_status(acc, juspay_id)
    elif order_num:
        r = real_preorder_status(acc, order_num, data.get("cart_session", ""))
    else:
        return jsonify({"state": "pending", "status": "no_reference"})

    state = str(r.get("state", "")).lower()
    status = str(r.get("status", "")).upper()
    if state in ("success", "confirmed"):
        state = "confirmed"
    elif state in ("failed",):
        state = "failed"
    else:
        state = "pending"

    return jsonify({"state": state, "status": status})


@app.route("/api/order/confirm", methods=["POST"])
def adapter_order_confirm():
    uid = get_uid() or 0
    data = request.json or {}
    order_num = data.get("order_num")
    if not order_num:
        return jsonify({"ok": False, "error": "order_num required", "message": "Missing order number"})
    try:
        oid = int(order_num)
        ord_row = get_order(oid)
        if ord_row:
            update_order_status(oid, "confirmed")
    except: pass
    return jsonify({"ok": True, "message": "Order confirmed!"})


@app.route("/api/orders", methods=["GET"])
def adapter_orders():
    uid = get_uid() or 0
    orders = get_orders(uid) if uid else []
    status_filter = request.args.get("status", "")
    filtered = orders
    if status_filter and status_filter.lower() != "all":
        filtered = [o for o in orders if str(o.get("status", "")).lower() == status_filter.lower()]

    order_list = []
    for o in filtered:
        order_list.append({
            "order_num": str(o.get("id", "")),
            "sub_order_num": "",
            "status_id": o.get("status", ""),
            "status_text": o.get("status", "pending").title(),
            "status_color": "#22B8A6" if o.get("status") == "confirmed" else "#C77C0A",
            "image": "",
            "size": "",
            "quantity": 1,
            "updated_date": o.get("created_at", ""),
            "delivery_date": "",
            "awb": "",
            "carrier_name": "",
            "tracking_url": "",
            "juspay_order_id": "",
            "cart_session": "",
            "amount": o.get("total", 0),
            "upi_amount": o.get("total", 0),
            "items_text": o.get("items", ""),
            "payment_method": o.get("payment_method", ""),
        })
    return jsonify({
        "orders": order_list,
        "filters": [
            {"id": "all", "name": "All"},
            {"id": "confirmed", "name": "Confirmed"},
            {"id": "pending", "name": "Pending"},
            {"id": "cancelled", "name": "Cancelled"},
        ],
        "cursor": "",
    })


@app.route("/api/orders/detail", methods=["POST"])
def adapter_order_detail():
    uid = get_uid() or 0
    data = request.json or {}
    order_num = data.get("order_num", "")
    try:
        oid = int(order_num)
        o = get_order(oid)
        if o:
            return jsonify({
                "product": {"product_id": 0, "name": o.get("items", ""), "images": [], "price": o.get("total", 0), "size": "", "quantity": 1},
                "tracking": {"title": o.get("status", ""), "icon": "", "delivery_by": ""},
                "milestones": [],
                "log": [],
                "address": {"line1": o.get("address", ""), "city": "", "state": "", "pin": "", "name": "", "mobile": ""},
                "payment": {"mode": o.get("payment_method", ""), "total": o.get("total", 0), "saved": 0, "price_type": ""},
                "shipment": {"awb": "", "carrier_name": "", "tracking_url": ""},
                "supplier": {"name": ""},
                "status_id": o.get("status", ""),
                "order_num": str(oid),
            })
    except: pass
    return jsonify({"error": "not found"}), 404


@app.route("/api/addresses", methods=["GET"])
def adapter_addresses():
    uid = get_uid() or 0
    acc = get_active_meesho_account(uid) if uid else None
    addrs = []
    default_addr = get_default_address(uid) if uid else None

    # Get Meesho addresses if account exists
    if acc:
        try:
            meesho_addrs = real_fetch_addresses(acc)
            for a in (meesho_addrs or []):
                addrs.append({
                    "id": a.get("id"),
                    "name": a.get("name", ""),
                    "mobile": a.get("mobile", ""),
                    "pin": a.get("pin", ""),
                    "city": a.get("city", ""),
                    "state": a.get("state", ""),
                    "address_line_1": a.get("address_line_1") or a.get("line1") or a.get("address", ""),
                    "address_line_2": a.get("address_line_2", ""),
                    "landmark": a.get("landmark", ""),
                    "address_type": a.get("address_type", "Home"),
                    "pin_serviceable": a.get("pin_serviceable", True),
                })
        except: pass

    # Fallback to local addresses
    if not addrs:
        local_addrs = get_addresses(uid) if uid else []
        for a in (local_addrs or []):
            addrs.append({
                "id": a.get("id"),
                "name": a.get("name", ""),
                "mobile": a.get("mobile", ""),
                "pin": a.get("pin", ""),
                "city": a.get("city", ""),
                "state": a.get("state", ""),
                "address_line_1": a.get("address_line_1", ""),
                "address_line_2": a.get("address_line_2", ""),
                "landmark": a.get("landmark", ""),
                "address_type": a.get("address_type", "Home"),
                "pin_serviceable": a.get("pin_serviceable", True),
            })

    return jsonify({"addresses": addrs, "default": default_addr})


@app.route("/api/addresses/create", methods=["POST"])
def adapter_address_create():
    uid = get_uid() or 0
    data = request.json or {}
    acc = get_active_meesho_account(uid) if uid else None
    if acc:
        try:
            r = real_address_create(acc, data)
            if r.get("ok"):
                return jsonify({"ok": True, "message": "Address created on Meesho"})
        except: pass
    if uid:
        create_address(uid, name=data.get("name", ""), mobile=data.get("mobile", ""),
                       pin=data.get("pin", ""), city=data.get("city", ""),
                       state=data.get("state", ""),
                       address_line_1=data.get("address_line_1", ""),
                       address_line_2=data.get("address_line_2", ""),
                       landmark=data.get("landmark", ""),
                       address_type=data.get("address_type", "Home"))
    return jsonify({"ok": True, "message": "Address saved"})


@app.route("/api/addresses/set_default", methods=["POST"])
def adapter_address_set_default():
    uid = get_uid() or 0
    data = request.json or {}
    address_id = data.get("id") or data.get("address_id")
    if uid and address_id:
        set_default_address(uid, address_id)
    return jsonify({"ok": True, "message": "Default address set"})


@app.route("/api/accounts", methods=["GET"])
def adapter_accounts_list():
    uid = get_uid() or 0
    accs = get_meesho_accounts(uid) if uid else []
    return jsonify({
        "accounts": [{
            "id": a.get("id"),
            "mobile": a.get("phone", ""),
            "source": "json",
            "xo_exp": False,
            "user_id": a.get("meesho_user_id") or a.get("user_id", ""),
        } for a in (accs or [])]
    })


@app.route("/api/accounts/select", methods=["POST"])
def adapter_account_select():
    uid = get_uid() or 0
    data = request.json or {}
    account_id = data.get("account_id")
    if uid and account_id:
        from database import get_db
        conn = get_db()
        conn.execute("UPDATE meesho_accounts SET is_active=0 WHERE user_id=?", (uid,))
        conn.execute("UPDATE meesho_accounts SET is_active=1 WHERE id=? AND user_id=?", (account_id, uid))
        conn.commit()
        conn.close()
    return jsonify({})


@app.route("/api/accounts/login_otp", methods=["POST"])
def adapter_account_login_otp():
    return api_otp_send()


@app.route("/api/accounts/login_verify", methods=["POST"])
def adapter_account_login_verify():
    data = request.json or {}
    status, out = _do_otp_verify(data.get("phone_number"), data.get("otp"),
                                 data.get("request_id"))
    return jsonify(out), status


@app.route("/api/auth/otp_send", methods=["POST"])
def adapter_auth_otp_send():
    return api_otp_send()


@app.route("/api/auth/otp_verify", methods=["POST"])
def adapter_auth_otp_verify():
    data = request.json or {}
    status, out = _do_otp_verify(data.get("phone_number"), data.get("otp"),
                                 data.get("request_id"))
    return jsonify(out), status


@app.route("/api/auth/json_login", methods=["POST"])
def adapter_auth_json_login():
    return api_json_login()


@app.route("/api/auth/login", methods=["POST"])
def adapter_auth_login():
    data = request.json or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    uid = get_uid()
    if not username or not password:
        return jsonify({"ok": False, "error": "Username and password are both required."})
    try:
        if not get_user(uid):
            create_user(uid, name=username)
    except Exception:
        pass
    user = get_user(uid) or {"user_id": uid}
    return jsonify({"ok": True, "token": f"tok_{uid}_{username}",
                    "user": {"id": uid, "username": username, "role": "user",
                             "plan": "free", "devices": 1, "accounts": 0}})


@app.route("/api/auth/logout", methods=["POST"])
def adapter_auth_logout():
    return jsonify({"ok": True, "message": "Logged out."})


@app.route("/api/auth/import_account", methods=["POST"])
def adapter_auth_import():
    """Import sheet sends a raw Meesho export (single dict / array /
    {accounts:[...]} with mobile+authorization). Normalize then reuse
    the json_login parser which already handles all these shapes."""
    raw = request.json
    if isinstance(raw, dict) and ("authorization" in raw or "mobile" in raw) and "user_id" not in raw and "userId" not in raw:
        # Bare export without explicit user_id — try composite-xo decode for
        # uid/instance, else fall through to json_login's helpful error.
        pass
    return api_json_login()


@app.route("/api/search/suggest", methods=["POST"])
def adapter_search_suggest():
    data = request.json or {}
    prefix = data.get("prefix", "")
    return api_search_suggest()


@app.route("/api/product/by_link", methods=["POST"])
def adapter_product_by_link():
    return api_product_by_link()


@app.route("/api/variation", methods=["POST"])
def adapter_variation():
    """Size/variation pricing for the product page. Uses live product data
    (same source as search) so price/in-stock match what Meesho shows."""
    data = request.json or {}
    pid = data.get("product_id")
    if not pid:
        return jsonify({"error": "product_id required"}), 400
    try:
        prod = get_meesho_product(str(pid))
    except Exception as e:
        return jsonify({"error": f"Could not load size details: {e}"}), 400
    if not prod:
        return jsonify({"error": "Could not load size details"}), 400
    price = int(prod.get("price") or 0)
    mrp = int(prod.get("mrp") or price)
    return jsonify({
        "ok": True,
        "price": price, "mrp": mrp, "list_price": price,
        "discount_text": prod.get("discount_text", "OFF"),
        "discount": max(0, mrp - price),
        "in_stock": prod.get("in_stock", True),
        "cod_available": True,
        "price_type_id": "basic_return_price",
        "shipping": {"charges": 0, "estimated_delivery": {"title": "Free Delivery"}},
    })


@app.route("/api/wallet/history", methods=["GET"])
def adapter_wallet_history():
    uid = get_uid() or 0
    user = get_user(uid) if uid else None
    return jsonify({"balance": user.get("wallet", 0) if user else 0, "txns": []})


@app.route("/api/price/check", methods=["POST"])
def adapter_price_check():
    return jsonify({"product": {}, "results": []})


@app.route("/api/referral/stats", methods=["GET"])
def adapter_referral_stats():
    return jsonify({"done": 0, "pending": 0, "rejected": 0, "earned": 0, "pending_amount": 0, "reward_per": 0, "has_link": False, "link": ""})


@app.route("/api/saas/plans", methods=["GET"])
def adapter_saas_plans():
    return jsonify({"plans": [{"key": "free", "label": "Free", "price": 0, "devices": 99, "orders": 999, "blurb": "Unlimited"}]})


@app.route("/api/check_registered", methods=["POST"])
def adapter_check_registered():
    # Frontend expects {ok, verified, registered, sign_up_date}; our
    # check_number returns {ok, eligible, live, registered, ...} — map it.
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone_number", "")).strip()[-10:]
    if not phone.isdigit() or len(phone) != 10:
        return jsonify({"ok": False, "error": "Enter valid 10-digit number"})
    try:
        r = check_number(phone)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
    registered = bool(r.get("registered", False))
    return jsonify({"ok": True, "verified": True, "live": True,
                    "registered": registered, "phone": phone,
                    "sign_up_date": r.get("sign_up_date", ""),
                    "title": r.get("title", ""), "subtitle": r.get("subtitle", "")})


@app.route("/api/admin/users", methods=["GET"])
def adapter_admin_users():
    return jsonify({"users": []})


@app.route("/api/fod/roll", methods=["GET"])
def adapter_fod_roll():
    return api_fod_roll()


@app.route("/api/fod/continue", methods=["POST"])
def adapter_fod_continue():
    return jsonify({"ok": True})


@app.route("/api/fod/bind/login_otp", methods=["POST"])
def adapter_fod_bind_otp():
    return api_otp_send()


@app.route("/api/fod/bind/login_verify", methods=["POST"])
def adapter_fod_bind_verify():
    return api_otp_verify()


@app.route("/api/geocode", methods=["GET"])
def adapter_geocode():
    return api_geocode()


# ── Missing working-bot routes (frontend calls these; lightweight adapters) ──

@app.route("/api/accounts/list", methods=["GET"])
def adapter_accounts_list2():
    uid = get_uid()
    accs = get_meesho_accounts(uid)
    return jsonify({"accounts": [
        {"id": a.get("id"), "mobile": a.get("phone", ""), "source": "otp",
         "xo_exp": False, "user_id": a.get("meesho_user_id") or "",
         "is_first_order": bool(a.get("is_first_order", 1))}
        for a in (accs or [])]})


@app.route("/api/accounts/order_status", methods=["GET"])
def adapter_accounts_order_status():
    uid = get_uid()
    accs = get_meesho_accounts(uid) or []
    orders = get_orders(uid) if uid else []
    placed = bool(orders)
    return jsonify({"statuses": {str(a.get("id")): placed for a in accs}})


@app.route("/api/account/fod", methods=["GET"])
def adapter_account_fod():
    return jsonify({"offer": None, "message": "", "rolled": False, "bound": False})


@app.route("/api/account/export_file", methods=["POST"])
def adapter_account_export_file():
    return jsonify({"ok": True, "message": "Session export is available from Account → Import/Export."})


@app.route("/api/addresses/copy_to_active", methods=["POST"])
def adapter_addresses_copy():
    uid = get_uid()
    dflt = get_default_address(uid)
    if not dflt:
        return jsonify({"ok": False, "error": "no_default",
                        "message": "No default address to copy. Add one in the Address tab first."})
    return jsonify({"ok": True, "message": "Default address is already active for checkout."})


@app.route("/api/addresses/random_update", methods=["POST"])
def adapter_addresses_random():
    return jsonify({"ok": True, "message": "Address kept as-is.",
                    "used": {"city": "", "pin": ""}})


@app.route("/api/orders/cancel_reasons", methods=["GET"])
def adapter_cancel_reasons():
    return jsonify({"reasons": [
        {"id": 1, "description": "Ordered by mistake", "comment_required": False},
        {"id": 2, "description": "Found cheaper elsewhere", "comment_required": False},
        {"id": 3, "description": "Delivery taking too long", "comment_required": False},
        {"id": 4, "description": "Want to change size/address", "comment_required": False},
        {"id": 5, "description": "Other", "comment_required": True},
    ]})


@app.route("/api/orders/cancel", methods=["POST"])
def adapter_orders_cancel():
    data = request.json or {}
    uid = get_uid()
    onum = str(data.get("order_num") or "")
    try:
        oid = int(onum)
        o = get_order(oid)
        if o and int(o.get("user_id", 0)) == int(uid):
            update_order_status(oid, "cancelled")
            return jsonify({"ok": True, "message": "Order cancelled."})
    except Exception:
        pass
    return jsonify({"ok": False, "error": "Order not found."}), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

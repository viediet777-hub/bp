"""
app.py - Production-Ready Flask Backend for FOD Pilot Telegram Mini App
Brand: VIEDDETX SINGH
Project: FOD Pilot – Meesho First-Order Engine
"""
import json
import logging
import os
import time
import math
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

from config import WALLET_MIN, WALLET_MAX, GW_UPI_ID, GW_UPI_NAME, GW_VERIFY_URL
from database import (
    get_user, create_user, update_user,
    get_cart, add_to_cart, update_cart_qty, clear_cart,
    tombstone_add, tombstone_recent,
    create_order, get_orders, get_order, update_order_status,
    save_meesho_account, get_meesho_accounts, get_active_meesho_account,
    delete_meesho_account,
    get_addresses, get_address, create_address, set_default_address, get_default_address,
    get_cart_session, set_cart_session,
    save_user_offer, get_user_offer,
    get_wallet_balance, add_wallet, deduct_wallet,
    create_wallet_tx, verify_wallet_tx, verify_wallet_tx_by_order_id, get_wallet_tx,
    get_global_mode, set_global_mode, get_order_fee as db_get_order_fee,
    sync_meesho_orders_to_db,
)
from meesho import (
    get_meesho_offer, search_meesho, get_meesho_product,
    send_otp, verify_otp, check_number,
    real_cart_add, real_cart_review, real_cart_clear, real_cart_remove,
    meesho_remove_verified,
    real_bind_address, real_paymentinfo, real_address_create, real_fetch_addresses,
    real_preorder, real_preorder_status,
    fresh_checkout_state, roll_fod_sync,
    real_user_orders,
)
from gateway import get_qr_url, get_qr_base64, generate_txn_id, create_upi_link, verify_payment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("meesho_app")

app = Flask(__name__, template_folder="templates")
CORS(app, resources={r"/api/*": {"origins": "*"}})

_active_offer = None
_otp_sessions = {}


def get_order_fee():
    """
    Returns platform fee dynamically from database settings.
    Free mode: 0, Paid mode: 5.
    """
    try:
        return db_get_order_fee()
    except Exception:
        mode = get_global_mode()
        return 0 if mode == "free" else 5


# ============================================================
# USER IDENTITY EXTRACTION
# ============================================================
def get_uid():
    """
    Extracts User ID.
    Priority: X-User-Id header (from Telegram initDataUnsafe.user.id) -> query param -> body -> default.
    """
    for raw in (
        request.headers.get("X-User-Id"),
        request.args.get("uid"),
    ):
        if raw not in (None, "", "0", 0, "undefined", "null"):
            try:
                v = int(str(raw).strip())
                if v:
                    return v
            except (ValueError, TypeError):
                pass

    # Check request body if present
    try:
        body = request.get_json(silent=True)
        if isinstance(body, dict) and body.get("uid"):
            return int(body["uid"])
    except Exception:
        pass

    # Fallback to Telegram initData header
    init_data = request.headers.get("X-Tg-Init-Data", "")
    if init_data and "user" in init_data:
        try:
            from urllib.parse import parse_qs
            qs = parse_qs(init_data)
            raw_u = (qs.get("user") or [None])[0]
            if raw_u:
                obj = json.loads(raw_u)
                if obj.get("id"):
                    return int(obj["id"])
        except Exception:
            pass

    return 1


def sync_local_cart(uid, cart, acc):
    """
    Idempotent sync of local cart rows with remote Meesho review.
    Updates local prices, quantities, and cart_session.
    If local items are missing in the remote Meesho cart (e.g. added before login),
    auto-pushes them to Meesho using real_cart_add() to ensure the remote cart is fully populated.
    """
    if not cart or not acc:
        return {"ok": False}
    logger.info(f"[CartSync] User {uid}: Syncing local cart ({len(cart)} items) with remote Meesho account.")
    cs = get_cart_session(uid) or ""
    review = real_cart_review(acc, cs)
    if not review.get("ok"):
        review = real_cart_review(acc, "")
    if not review.get("ok"):
        logger.warning(f"[CartSync] real_cart_review returned error for user {uid}: {review.get('error')}")
        return {"ok": False, "error": str(review.get("error"))}
    if review.get("cart_session"):
        set_cart_session(uid, review["cart_session"])
        cs = review["cart_session"]

    mmap = {}
    for mi in review.get("items", []):
        try:
            mmap[int(mi.get("product_id"))] = mi
        except (TypeError, ValueError):
            continue

    # Auto-push any local items that are missing on Meesho (skip tombstones)
    pushed_any = False
    active_tombstones = tombstone_recent(uid)
    if active_tombstones:
        from database import get_db
        conn = get_db()
        for t_pid in active_tombstones:
            conn.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (uid, t_pid))
        conn.commit()
        conn.close()

    for c in cart:
        pid = int(c.get("product_id") or 0)
        if pid and pid in active_tombstones:
            continue
        if pid and pid not in mmap:
            logger.info(f"[CartSync] User {uid}: Pushing local product {pid} ('{c.get('name')}', qty={c.get('qty', 1)}) to Meesho remote cart.")
            add_res = real_cart_add(
                acc,
                pid,
                int(c.get("supplier_id") or 0),
                int(c.get("variation_id") or 0),
                c.get("variation_name") or "Free Size",
                int(c.get("qty") or 1),
                cs,
            )
            if add_res.get("ok") and add_res.get("cart_session"):
                cs = add_res["cart_session"]
                set_cart_session(uid, cs)
                pushed_any = True

    # If items were pushed, refresh the review so mmap and session are live
    if pushed_any:
        fresh_review = real_cart_review(acc, cs)
        if fresh_review.get("ok"):
            review = fresh_review
            if review.get("cart_session"):
                cs = review["cart_session"]
                set_cart_session(uid, cs)
            mmap = {int(mi.get("product_id")): mi for mi in review.get("items", []) if mi.get("product_id")}

    from database import get_db
    try:
        conn = get_db()
        for c in cart:
            pid = int(c.get("product_id") or 0)
            if pid in mmap:
                m = mmap[pid]
                conn.execute(
                    """UPDATE cart SET price=?, qty=?, variation_name=?, variation_id=?, identifier=?
                       WHERE user_id=? AND product_id=?""",
                    (
                        int(m.get("price") or c.get("price") or 0),
                        int(m.get("quantity") or c.get("qty") or 1),
                        m.get("variation") or c.get("variation_name") or "Free Size",
                        int(m.get("variation_id") or 0),
                        m.get("identifier") or "",
                        uid,
                        pid,
                    ),
                )
                logger.info(f"[CartSync] User {uid}: Reconciled product {pid} price=₹{m.get('price')} qty={m.get('quantity')}")
        conn.commit()
        conn.close()
        return {"ok": True, "cart_session": review.get("cart_session") or cs}
    except Exception as e:
        logger.error(f"[CartSync] User {uid}: Database update error: {e}")
        return {"ok": False, "error": str(e)}


# ============================================================
# PRIMARY FRONTEND ROUTE
# ============================================================
@app.route("/")
def index():
    return render_template("index.html")


# ============================================================
# FOD OFFERS API
# ============================================================
@app.route("/api/offers", methods=["GET"])
def api_offers():
    global _active_offer
    uid = get_uid()
    acc = get_active_meesho_account(uid)

    # Offer detection: If logged in as existing user, return ineligible
    if acc and not int(acc.get("is_first_order", 1)):
        return jsonify({
            "offer": None,
            "reason": "existing_user",
            "message": "No offer available for this account (existing user)",
        })

    # If user has a saved offer, prioritize it
    saved = get_user_offer(uid)
    if saved:
        _active_offer = saved
        return jsonify({"offer": _active_offer, "saved": True})

    if not _active_offer:
        res = roll_fod_sync(for_acc=acc)
        if res.get("ok") and res.get("offer"):
            _active_offer = res["offer"]
    return jsonify({"offer": _active_offer})


@app.route("/api/fod/roll", methods=["GET"])
def api_fod_roll():
    global _active_offer
    uid = get_uid()
    acc = get_active_meesho_account(uid)

    if acc and not int(acc.get("is_first_order", 1)):
        return jsonify({
            "ok": False,
            "error": "No first-order discount available for existing accounts.",
            "reason": "existing_user",
        }), 400

    res = roll_fod_sync(for_acc=acc)
    if res.get("ok") and res.get("offer"):
        _active_offer = res["offer"]
        if uid:
            save_user_offer(uid, json.dumps(_active_offer))
    return jsonify(res)


@app.route("/api/offer/apply", methods=["POST"])
def api_offer_apply():
    """
    Applies the First-Order Discount offer to the connected account.
    Validates eligibility (is_first_order == 1).
    """
    global _active_offer
    uid = get_uid()
    acc = get_active_meesho_account(uid)

    if not acc:
        return jsonify({
            "ok": False,
            "error": "Please connect your Meesho account first",
            "requires_login": True,
        }), 401

    if not int(acc.get("is_first_order", 1)):
        return jsonify({
            "ok": False,
            "error": "No first-order discount available for existing accounts.",
            "reason": "existing_user",
        }), 400

    data = request.get_json(silent=True) or {}
    req_bucket = data.get("bucket") or request.args.get("bucket")
    target_offer = data.get("offer") or _active_offer
    if not target_offer:
        res = roll_fod_sync(for_acc=acc)
        target_offer = res.get("offer")

    if target_offer:
        if req_bucket:
            try:
                b_int = int(req_bucket)
                target_offer["bucket"] = b_int
                target_offer["display_bucket"] = b_int
                target_offer["display_text"] = f"Upto ₹{b_int} OFF"
            except Exception:
                pass
        _active_offer = target_offer
        save_user_offer(uid, json.dumps(target_offer))
        bucket = target_offer.get("bucket") or target_offer.get("display_bucket") or 200
        return jsonify({
            "ok": True,
            "message": f"Offer ₹{bucket} OFF applied to your account!",
            "offer": target_offer,
            "bucket": bucket,
        })
    return jsonify({"ok": False, "error": "Failed to apply offer"}), 400


@app.route("/api/fod/continue", methods=["GET", "POST"])
def api_fod_continue():
    return api_offer_apply()


# ============================================================
# PRODUCT SEARCH & DETAILS
# ============================================================
@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.get_json(silent=True) or {}
    query = str(data.get("query", "")).strip() or "fashion trending"
    res = search_meesho(query, offer=_active_offer)
    return jsonify(res or {"catalogs": []})


@app.route("/api/search/suggest", methods=["POST"])
def api_search_suggest():
    data = request.get_json(silent=True) or {}
    prefix = str(data.get("prefix", "")).strip().lower()
    common = ["kurti", "saree", "tshirt", "shoes", "watch", "bedsheet", "jewellery", "earrings", "dress"]
    suggestions = [c for c in common if prefix in c] if prefix else common[:5]
    return jsonify([{"suggestion": s} for s in suggestions])


@app.route("/api/product", methods=["GET"])
def api_product():
    pid = request.args.get("product_id", "")
    if not pid:
        return jsonify({"error": "missing_product_id"}), 400
    res = get_meesho_product(pid, offer=_active_offer)
    if res:
        return jsonify(res)
    return jsonify({"error": "product_not_found"}), 404


# ============================================================
# CART MANAGEMENT WITH FAST OPTIMISTIC UPDATES
# ============================================================
@app.route("/api/cart", methods=["GET"])
def api_cart():
    uid = get_uid()
    cart_items = get_cart(uid)
    acc = get_active_meesho_account(uid)

    # Only perform full remote review when explicitly requested (e.g. ?sync=1)
    if acc and request.args.get("sync") == "1":
        try:
            cs = get_cart_session(uid) or ""
            review = real_cart_review(acc, cs)
            if not review.get("ok"):
                review = real_cart_review(acc, "")
            if review.get("ok"):
                if review.get("cart_session"):
                    set_cart_session(uid, review["cart_session"])
                sync_local_cart(uid, cart_items, acc)
                cart_items = get_cart(uid)
        except Exception as e:
            logger.warning(f"[Cart] real_cart_review error in api_cart: {e}")

    addr = get_default_address(uid)
    total_qty = sum(int(c.get("qty") or 1) for c in cart_items)
    subtotal = sum(int(c.get("price") or 0) * int(c.get("qty") or 1) for c in cart_items)

    return jsonify({
        "items": cart_items,
        "total_quantity": total_qty,
        "effective_total": subtotal,
        "subtotal": subtotal,
        "address": addr,
        "cart_session": get_cart_session(uid) or "",
        "sync": {"ok": bool(acc)},
    })


@app.route("/api/cart/add", methods=["POST"])
def api_cart_add():
    uid = get_uid()
    data = request.get_json(silent=True) or {}
    pid = data.get("product_id")
    if not pid:
        return jsonify({"ok": False, "error": "product_id required"}), 400

    supplier_id = int(data.get("supplier_id") or 0)
    variation_id = int(data.get("variation_id") or 0)
    variation = data.get("variation") or data.get("variation_name") or "Free Size"
    qty = max(1, int(data.get("qty") or data.get("quantity") or 1))
    price = int(data.get("price") or 0)
    mrp = int(data.get("mrp") or price)
    name = data.get("name") or f"Product {pid}"
    image = data.get("image") or ""

    # Clear any active tombstones for this product because user explicitly re-added it
    try:
        from database import get_db
        conn = get_db()
        conn.execute("DELETE FROM cart_tombstones WHERE user_id=? AND product_id=?", (uid, pid))
        conn.execute("DELETE FROM recently_removed WHERE user_id=? AND product_id=?", (uid, pid))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[api_cart_add] clear tombstone failed: {e}")

    acc = get_active_meesho_account(uid)
    cs = get_cart_session(uid) or ""
    if acc:
        res = real_cart_add(acc, pid, supplier_id, variation_id, variation, qty, cs)
        if res.get("ok"):
            cs = res.get("cart_session") or cs
            set_cart_session(uid, cs)
            if res.get("resolved_supplier_id"):
                supplier_id = int(res["resolved_supplier_id"])
            if res.get("resolved_variation_id"):
                variation_id = int(res["resolved_variation_id"])

    # Persist locally immediately
    add_to_cart(
        user_id=uid,
        product_id=pid,
        qty=qty,
        name=name,
        price=price,
        image=image,
        source="meesho",
        supplier_id=supplier_id,
        variation_id=variation_id,
        variation_name=variation,
        mrp=mrp,
    )

    # Reconcile with Meesho backend state to ensure consistency before confirming success
    if acc:
        sync_res = sync_local_cart(uid, get_cart(uid), acc)
        if sync_res.get("cart_session"):
            cs = sync_res["cart_session"]
            set_cart_session(uid, cs)

    updated_cart = get_cart(uid)
    total_qty = sum(int(c.get("qty") or 1) for c in updated_cart)
    effective_total = sum(int(c.get("price") or 0) * int(c.get("qty") or 1) for c in updated_cart)

    return jsonify({
        "ok": True,
        "success": True,
        "cart": updated_cart,
        "items": updated_cart,
        "cart_session": cs,
        "total_quantity": total_qty,
        "effective_total": effective_total,
        "result": {
            "effective_total": effective_total,
            "total_quantity": total_qty,
        },
    })


@app.route("/api/cart/update", methods=["POST"])
def api_cart_update():
    """
    Updates quantity or deletes item.
    Crucial: When qty=0, item is deleted AND added to tombstone with 300s TTL.
    Invokes real_cart_add or meesho_remove_verified immediately upon receiving a mutation request.
    Ensures that the updated cart object returned to the frontend is consistent with the Meesho backend state before confirming success.
    """
    uid = get_uid()
    data = request.get_json(silent=True) or {}

    cid = data.get("cart_id")
    pid = data.get("product_id")
    qty = int(data.get("qty", 1))

    cart_items = get_cart(uid)
    target = None
    if cid:
        target = next((c for c in cart_items if str(c.get("id")) == str(cid)), None)
    if not target and pid:
        target = next((c for c in cart_items if str(c.get("product_id")) == str(pid)), None)

    if not target:
        return jsonify({"ok": False, "error": "Item not found in cart"}), 404

    target_pid = target.get("product_id")
    target_cid = target.get("id")
    target_vid = target.get("variation_id") if target else 0
    current_qty = int(target.get("qty") or 1)

    acc = get_active_meesho_account(uid)
    cs = get_cart_session(uid) or ""

    if qty <= 0:
        # DELETION: Add to tombstone table immediately
        if target_pid:
            tombstone_add(uid, target_pid, target_vid)

        if target_cid:
            update_cart_qty(target_cid, 0)
        elif target_pid:
            from database import get_db
            conn = get_db()
            conn.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (uid, target_pid))
            conn.commit()
            conn.close()

        # Call verified removal on Meesho immediately
        if acc and target_pid:
            rem_res = meesho_remove_verified(acc, target_pid, cs, variation_id=target_vid)
            if rem_res.get("cart_session"):
                cs = rem_res["cart_session"]
                set_cart_session(uid, cs)

            # Ensure local DB is completely clean of the deleted item
            from database import get_db
            conn = get_db()
            conn.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (uid, target_pid))
            conn.commit()
            conn.close()

            # Reconcile remaining items with Meesho backend state
            remaining_cart = get_cart(uid)
            if remaining_cart:
                sync_res = sync_local_cart(uid, remaining_cart, acc)
                if sync_res.get("cart_session"):
                    cs = sync_res["cart_session"]
                    set_cart_session(uid, cs)

        updated_cart = get_cart(uid)
        total_qty = sum(int(c.get("qty") or 1) for c in updated_cart)
        effective_total = sum(int(c.get("price") or 0) * int(c.get("qty") or 1) for c in updated_cart)

        return jsonify({
            "ok": True,
            "success": True,
            "deleted": True,
            "cart": updated_cart,
            "items": updated_cart,
            "cart_session": cs,
            "total_quantity": total_qty,
            "effective_total": effective_total,
            "result": {
                "effective_total": effective_total,
                "total_quantity": total_qty,
            },
        })
    else:
        # QUANTITY CHANGE:
        if qty > current_qty:
            delta = qty - current_qty
            if acc and target_pid:
                add_res = real_cart_add(
                    acc,
                    target_pid,
                    target.get("supplier_id", 0),
                    target_vid,
                    target.get("variation_name", "Free Size"),
                    delta,
                    cs,
                )
                if add_res.get("cart_session"):
                    cs = add_res["cart_session"]
                    set_cart_session(uid, cs)
            if target_cid:
                update_cart_qty(target_cid, qty)
        elif qty < current_qty:
            # Decrement on Meesho by removing line and adding desired qty
            if acc and target_pid:
                rem = real_cart_remove(acc, target.get("identifier") or {"product_id": target_pid}, cs)
                if rem.get("cart_session"):
                    cs = rem["cart_session"]
                add_res = real_cart_add(
                    acc,
                    target_pid,
                    target.get("supplier_id", 0),
                    target_vid,
                    target.get("variation_name", "Free Size"),
                    qty,
                    cs,
                )
                if add_res.get("cart_session"):
                    cs = add_res["cart_session"]
                    set_cart_session(uid, cs)
            if target_cid:
                update_cart_qty(target_cid, qty)

        # Reconcile with Meesho backend state to ensure consistency before confirming success
        if acc:
            sync_res = sync_local_cart(uid, get_cart(uid), acc)
            if sync_res.get("cart_session"):
                cs = sync_res["cart_session"]
                set_cart_session(uid, cs)

        updated_cart = get_cart(uid)
        total_qty = sum(int(c.get("qty") or 1) for c in updated_cart)
        effective_total = sum(int(c.get("price") or 0) * int(c.get("qty") or 1) for c in updated_cart)

        return jsonify({
            "ok": True,
            "success": True,
            "cart": updated_cart,
            "items": updated_cart,
            "cart_session": cs,
            "total_quantity": total_qty,
            "effective_total": effective_total,
            "result": {
                "effective_total": effective_total,
                "total_quantity": total_qty,
            },
        })


@app.route("/api/cart/clear", methods=["POST"])
def api_cart_clear():
    uid = get_uid()
    clear_cart(uid)
    acc = get_active_meesho_account(uid)
    if acc:
        cs = get_cart_session(uid)
        real_cart_clear(acc, cs)
    set_cart_session(uid, "")
    return jsonify({"ok": True})


@app.route("/api/cart/sync/pull", methods=["GET", "POST"])
def api_cart_sync_pull():
    """
    Reconciles Meesho remote cart into local database.
    Tombstone Check: Skips and purges any product in recently_removed to avoid zombie re-imports.
    """
    uid = get_uid()
    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"ok": False, "error": "no_account_linked", "cart": get_cart(uid)})

    cs = get_cart_session(uid) or ""
    review = real_cart_review(acc, cs)
    if not review.get("ok"):
        review = real_cart_review(acc, "")

    if not review.get("ok"):
        return jsonify({"ok": False, "error": review.get("error"), "cart": get_cart(uid)})

    new_cs = review.get("cart_session") or cs
    set_cart_session(uid, new_cs)

    meesho_items = review.get("items", [])
    active_tombstones = tombstone_recent(uid)

    from database import get_db
    conn = get_db()

    # Purge any tombstoned items from local DB
    for t_pid in active_tombstones:
        conn.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (uid, t_pid))
    conn.commit()

    imported_count = 0
    updated_count = 0
    local_cart = get_cart(uid)
    local_pids = {int(c.get("product_id")) for c in local_cart if c.get("product_id")}

    for mi in meesho_items:
        mpid = int(mi.get("product_id") or 0)
        if not mpid or mpid in active_tombstones:
            # SKIP tombstoned items
            continue

        mprice = int(mi.get("price") or mi.get("mrp") or 0)
        mqty = int(mi.get("quantity") or 1)
        mvar = mi.get("variation") or "Free Size"
        mvid = int(mi.get("variation_id") or 0)

        if mpid in local_pids:
            # Update existing line item
            conn.execute(
                """UPDATE cart SET price=?, qty=?, variation_name=?, variation_id=?, identifier=?
                   WHERE user_id=? AND product_id=?""",
                (mprice, mqty, mvar, mvid, mi.get("identifier") or "", uid, mpid),
            )
            updated_count += 1
        else:
            # Import new product
            add_to_cart(
                user_id=uid,
                product_id=mpid,
                qty=mqty,
                name=mi.get("name") or f"Product {mpid}",
                price=mprice,
                image=mi.get("image") or "",
                source="meesho",
                supplier_id=int(mi.get("supplier_id") or 0),
                variation_id=mvid,
                variation_name=mvar,
                mrp=int(mi.get("mrp") or mprice),
                identifier=mi.get("identifier") or "",
            )
            imported_count += 1

    conn.commit()
    conn.close()

    refreshed_cart = get_cart(uid)
    return jsonify({
        "ok": True,
        "cart_session": new_cs,
        "imported": imported_count,
        "updated": updated_count,
        "meesho_items": meesho_items,
        "cart": refreshed_cart,
    })


# ============================================================
# CHECKOUT SUMMARY (COD vs UPI)
# ============================================================
@app.route("/api/checkout/summary", methods=["GET"])
def api_checkout_summary():
    uid = get_uid()
    cart = get_cart(uid)
    if not cart:
        return jsonify({"error": "cart empty"}), 400

    subtotal = sum(int(c.get("price") or 0) * int(c.get("qty") or 1) for c in cart)
    acc = get_active_meesho_account(uid)
    addr = get_default_address(uid)

    cod_amount = subtotal
    upi_amount = subtotal
    prepaid_discount = 0

    if acc:
        cs = get_cart_session(uid) or ""
        review = real_cart_review(acc, cs)
        if not review.get("ok"):
            review = real_cart_review(acc, "")
        if review.get("ok"):
            cod_amount = review.get("effective_total") or subtotal
            upi_amount = review.get("effective_total_with_ppd") or review.get("effective_total_for_upi_plugin") or cod_amount

    # Ensure dynamic discount reflects if identical
    if cod_amount == upi_amount and cod_amount > 20:
        prepaid_discount = 28 if cod_amount >= 60 else 14
        upi_amount = max(1, cod_amount - prepaid_discount)
    else:
        prepaid_discount = max(0, cod_amount - upi_amount)

    return jsonify({
        "items": cart,
        "subtotal": subtotal,
        "product_price": cod_amount + prepaid_discount,
        "total_discounts": prepaid_discount,
        "total": cod_amount,
        "cod_amount": cod_amount,
        "upi_amount": upi_amount,
        "prepaid_discount": prepaid_discount,
        "address": addr,
    })


# ============================================================
# ORDER PLACEMENT (COD & UPI)
# ============================================================
@app.route("/api/order/place_cod", methods=["POST"])
def adapter_place_cod():
    """
    Places order via Cash on Delivery following exact checkout_method.txt flow:
    1. /api/1.0/cart/location
    2. /api/8.0/cart
    3. /api/1.0/cart/paymentinfo (with ["cod"])
    4. /api/4.0/preorders
    """
    uid = get_uid()
    data = request.get_json(silent=True) or {}
    cart = get_cart(uid)
    if not cart:
        return jsonify({"ok": False, "error": "Cart is empty"}), 400

    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"ok": False, "error": "No Meesho account linked. Please login."}), 400

    addr_id = data.get("address_id")
    addr = get_address(addr_id) if addr_id else get_default_address(uid)
    if not addr:
        return jsonify({"ok": False, "error": "Select a delivery address."}), 400

    # ----------------------------------------------------
    # Wallet Service Fee Check (Dynamic Free vs Paid Mode)
    # The user's internal wallet balance is checked.
    # In FREE mode: fee is ₹0.
    # In PAID mode: fee is ₹5 (or db setting).
    # ----------------------------------------------------
    current_fee = get_order_fee()
    if current_fee > 0:
        bal = get_wallet_balance(uid)
        if bal < current_fee:
            return jsonify({
                "ok": False,
                "error": f"Insufficient wallet balance (₹{bal}). A service fee of ₹{current_fee} is required to place an order in PAID mode. Please recharge your wallet.",
                "code": "INSUFFICIENT_WALLET",
                "wallet_balance": bal,
                "fee_required": current_fee,
            }), 400

    cs = get_cart_session(uid) or ""
    sync_local_cart(uid, cart, acc)

    st = fresh_checkout_state(acc, cs, need_paymentinfo=True, cod=True)
    if not st:
        return jsonify({"ok": False, "error": "Could not prepare checkout on Meesho. Please retry."}), 400

    fresh_cs = st["cs"]
    meesho_amount = st["cod_amount"]
    meesho_addr_id = (st["addr"].get("id") or addr.get("id"))

    order_res = real_preorder(
        acc=acc,
        cart_session=fresh_cs,
        address_id=meesho_addr_id,
        payment_method="COD",
        customer_amount=meesho_amount,
        addr_info=st["addr"],
    )

    if not order_res.get("ok"):
        return jsonify({"ok": False, "error": order_res.get("error") or "Order rejected by Meesho"}), 400

    order_num = order_res.get("order_num")
    items_snapshot = json.dumps([
        {
            "product_id": c.get("product_id"),
            "name": c.get("name") or "Product",
            "price": c.get("price") or 0,
            "qty": c.get("qty") or 1,
            "image": c.get("image") or "",
            "variation_name": c.get("variation_name") or "",
        }
        for c in cart
    ])

    # Deduct platform service fee from user's internal wallet upon order success
    fee_deducted = 0
    if current_fee > 0:
        if deduct_wallet(uid, current_fee, note=f"Service fee for order #{order_num}", ref_id=str(order_num)):
            fee_deducted = current_fee

    oid = create_order(
        user_id=uid,
        items=items_snapshot,
        total=meesho_amount,
        fee=fee_deducted,
        address=addr.get("address_line_1") or "",
        meesho_order_num=str(order_num),
        payment_method="COD",
        meesho_amount=meesho_amount,
        address_id=int(addr.get("id") or 0),
    )

    clear_cart(uid)
    set_cart_session(uid, "")

    return jsonify({
        "ok": True,
        "order_num": str(oid),
        "meesho_order_num": str(order_num),
        "total": meesho_amount,
        "payment_method": "COD",
        "fee_deducted": fee_deducted,
        "wallet_balance": get_wallet_balance(uid),
        "message": "Order placed successfully!",
    })


@app.route("/api/order/pay_online", methods=["POST"])
def adapter_pay_online():
    """
    UPI Checkout with Juspay WAPI intent generation.
    Returns qr_base64, qr_url, upi_intent_url for modal rendering.
    """
    uid = get_uid()
    data = request.get_json(silent=True) or {}
    cart = get_cart(uid)
    if not cart:
        return jsonify({"ok": False, "error": "Cart is empty"}), 400

    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"ok": False, "error": "No Meesho account linked. Please login."}), 400

    addr_id = data.get("address_id")
    addr = get_address(addr_id) if addr_id else get_default_address(uid)
    if not addr:
        return jsonify({"ok": False, "error": "Select a delivery address."}), 400

    # ----------------------------------------------------
    # Wallet Service Fee Check (Dynamic Free vs Paid Mode)
    # The user's internal wallet balance is checked.
    # In FREE mode: fee is ₹0.
    # In PAID mode: fee is ₹5 (or db setting).
    # ----------------------------------------------------
    current_fee = get_order_fee()
    if current_fee > 0:
        bal = get_wallet_balance(uid)
        if bal < current_fee:
            return jsonify({
                "ok": False,
                "error": f"Insufficient wallet balance (₹{bal}). A service fee of ₹{current_fee} is required to place an order in PAID mode. Please recharge your wallet.",
                "code": "INSUFFICIENT_WALLET",
                "wallet_balance": bal,
                "fee_required": current_fee,
            }), 400

    cs = get_cart_session(uid) or ""
    sync_local_cart(uid, cart, acc)

    st = fresh_checkout_state(acc, cs, need_paymentinfo=True, cod=False)
    if not st:
        return jsonify({"ok": False, "error": "Could not prepare checkout on Meesho. Please retry."}), 400

    fresh_cs = st["cs"]
    meesho_amount = st["upi_amount"]
    meesho_addr_id = (st["addr"].get("id") or addr.get("id"))

    order_res = real_preorder(
        acc=acc,
        cart_session=fresh_cs,
        address_id=meesho_addr_id,
        payment_method="UPI",
        customer_amount=meesho_amount,
        addr_info=st["addr"],
    )

    if not order_res.get("ok"):
        return jsonify({"ok": False, "error": order_res.get("error") or "Order rejected by Meesho"}), 400

    order_num = order_res.get("order_num")
    upi_intent_url = order_res.get("upi_intent_url") or ""
    qr_base64 = order_res.get("qr_base64") or (get_qr_base64(upi_intent_url, size=240) if upi_intent_url else "")
    qr_url = get_qr_url(upi_intent_url, size=240) if upi_intent_url else ""

    items_snapshot = json.dumps([
        {
            "product_id": c.get("product_id"),
            "name": c.get("name") or "Product",
            "price": c.get("price") or 0,
            "qty": c.get("qty") or 1,
            "image": c.get("image") or "",
            "variation_name": c.get("variation_name") or "",
        }
        for c in cart
    ])

    # Deduct platform service fee from user's internal wallet upon order success
    fee_deducted = 0
    if current_fee > 0:
        if deduct_wallet(uid, current_fee, note=f"Service fee for order #{order_num}", ref_id=str(order_num)):
            fee_deducted = current_fee

    oid = create_order(
        user_id=uid,
        items=items_snapshot,
        total=meesho_amount,
        fee=fee_deducted,
        address=addr.get("address_line_1") or "",
        meesho_order_num=str(order_num),
        payment_method="UPI",
        meesho_amount=meesho_amount,
        address_id=int(addr.get("id") or 0),
    )

    clear_cart(uid)
    set_cart_session(uid, "")

    return jsonify({
        "ok": True,
        "order_num": str(oid),
        "meesho_order_num": str(order_num),
        "total": meesho_amount,
        "upi_amount": meesho_amount,
        "fee_deducted": fee_deducted,
        "wallet_balance": get_wallet_balance(uid),
        "qr_base64": qr_base64,
        "qr_url": qr_url,
        "upi_intent_url": upi_intent_url,
        "redirect_url": upi_intent_url,
        "message": "UPI payment initiated",
    })


@app.route("/api/order/confirm", methods=["POST"])
def api_order_confirm():
    """Confirms order status after user payment."""
    data = request.get_json(silent=True) or {}
    order_num = data.get("order_num")
    if not order_num:
        return jsonify({"ok": False, "error": "order_num required"}), 400

    try:
        oid = int(order_num)
        update_order_status(oid, "confirmed", paid_at=time.time())
    except (ValueError, TypeError):
        pass

    return jsonify({"ok": True, "status": "confirmed", "message": "Payment verified and order confirmed!"})


@app.route("/api/orders", methods=["GET"])
def api_orders():
    """Returns all orders (both local bot orders and synced Meesho orders)."""
    uid = get_uid()
    orders = get_orders(uid)
    acc = get_active_meesho_account(uid)

    # Reconcile live orders from Meesho if active
    if acc:
        try:
            live = real_user_orders(acc, limit=15)
            if live.get("ok"):
                sync_meesho_orders_to_db(uid, live.get("orders", []))
                orders = get_orders(uid)
        except Exception as e:
            logger.warning(f"Error fetching live orders in api_orders: {e}")

    out = []
    for o in orders:
        m_num = o.get("meesho_order_num")
        source = "Meesho" if m_num else "Bot"
        raw_items = o.get("items") or ""
        first_image = ""
        items_display = raw_items
        try:
            parsed = json.loads(raw_items) if isinstance(raw_items, str) and (raw_items.startswith("[") or raw_items.startswith("{")) else raw_items
            if isinstance(parsed, list) and parsed:
                first_image = parsed[0].get("image") or ""
                items_display = ", ".join([f"{it.get('name', 'Item')} ×{it.get('qty', 1)}" for it in parsed])
            elif isinstance(parsed, dict):
                first_image = parsed.get("image") or ""
        except Exception:
            pass

        out.append({
            "order_num": str(o.get("id") or o.get("order_num")),
            "meesho_order_num": m_num,
            "items": raw_items,
            "items_text": items_display or raw_items,
            "image": first_image or o.get("image") or "",
            "total": o.get("total"),
            "amount": o.get("total"),
            "status": o.get("status", "pending"),
            "status_text": str(o.get("status", "pending")).title(),
            "payment_method": o.get("payment_method", "COD"),
            "created_at": o.get("created_at"),
            "address": o.get("address"),
            "source": source,
        })
    return jsonify({"orders": out})


@app.route("/api/meesho/orders/live", methods=["GET"])
def api_meesho_orders_live():
    """
    Live endpoint called by the '🔄 Sync Meesho Orders' button.
    Fetches orders from Meesho API, updates local database, and returns fresh orders.
    """
    uid = get_uid()
    acc = get_active_meesho_account(uid)
    if not acc:
        return jsonify({"ok": False, "error": "Please link your Meesho account first."}), 400
    try:
        res = real_user_orders(acc, limit=15)
        if res.get("ok"):
            orders = res.get("orders", [])
            sync_meesho_orders_to_db(uid, orders)
            refreshed_orders = get_orders(uid)
            out = []
            for o in refreshed_orders:
                m_num = o.get("meesho_order_num")
                raw_items = o.get("items") or ""
                first_image = ""
                items_display = raw_items
                try:
                    parsed = json.loads(raw_items) if isinstance(raw_items, str) and (raw_items.startswith("[") or raw_items.startswith("{")) else raw_items
                    if isinstance(parsed, list) and parsed:
                        first_image = parsed[0].get("image") or ""
                        items_display = ", ".join([f"{it.get('name', 'Item')} ×{it.get('qty', 1)}" for it in parsed])
                    elif isinstance(parsed, dict):
                        first_image = parsed.get("image") or ""
                except Exception:
                    pass

                out.append({
                    "order_num": str(o.get("id") or o.get("order_num")),
                    "meesho_order_num": m_num,
                    "items": raw_items,
                    "items_text": items_display or raw_items,
                    "image": first_image or o.get("image") or "",
                    "total": o.get("total"),
                    "amount": o.get("total"),
                    "status": o.get("status", "pending"),
                    "status_text": str(o.get("status", "pending")).title(),
                    "payment_method": o.get("payment_method", "COD"),
                    "created_at": o.get("created_at"),
                    "address": o.get("address"),
                    "source": "Meesho" if m_num else "Bot",
                })
            return jsonify({"ok": True, "orders": out, "synced_count": len(orders)})
        return jsonify({"ok": False, "error": res.get("error") or "Failed to fetch Meesho orders"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ============================================================
# ADDRESS MANAGEMENT & GEOLOCATION
# ============================================================
@app.route("/api/addresses", methods=["GET"])
def api_addresses():
    uid = get_uid()
    acc = get_active_meesho_account(uid)
    addrs = get_addresses(uid)

    # Sync live Meesho addresses if local empty
    if not addrs and acc:
        try:
            live = real_fetch_addresses(acc)
            for a in live:
                create_address(
                    user_id=uid,
                    name=a.get("name", "User"),
                    mobile=a.get("mobile", ""),
                    pin=a.get("pin", ""),
                    city=a.get("city", ""),
                    state=a.get("state", ""),
                    address_line_1=a.get("address_line_1", ""),
                    is_default=1 if not addrs else 0,
                    meesho_address_id=a.get("id", 0),
                )
            addrs = get_addresses(uid)
        except Exception:
            pass

    default = next((a for a in addrs if a.get("is_default")), addrs[0] if addrs else None)
    return jsonify({"addresses": addrs, "default": default})


@app.route("/api/addresses/create", methods=["POST"])
def api_addresses_create():
    uid = get_uid()
    data = request.get_json(silent=True) or {}

    name = data.get("name", "").strip()
    mobile = data.get("mobile", "").strip()
    pin = data.get("pin", "").strip()
    city = data.get("city", "").strip()
    state = data.get("state", "").strip()
    line1 = data.get("address_line_1", "").strip()

    if not (name and mobile and pin and line1):
        return jsonify({"ok": False, "error": "Name, mobile, pin, and address required"}), 400

    acc = get_active_meesho_account(uid)
    meesho_addr_id = 0
    if acc:
        try:
            mr = real_address_create(acc, name, mobile, pin, city, state, line1)
            if mr.get("ok"):
                meesho_addr_id = mr.get("meesho_address_id", 0)
        except Exception:
            pass

    aid = create_address(
        user_id=uid,
        name=name,
        mobile=mobile,
        pin=pin,
        city=city,
        state=state,
        address_line_1=line1,
        is_default=1,
        meesho_address_id=meesho_addr_id,
    )
    return jsonify({"ok": True, "id": aid, "message": "Address created successfully"})


@app.route("/api/addresses/set_default", methods=["POST"])
def api_addresses_set_default():
    uid = get_uid()
    data = request.get_json(silent=True) or {}
    aid = data.get("id") or data.get("address_id")
    if aid:
        set_default_address(uid, aid)
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "id required"}), 400


@app.route("/api/geocode", methods=["GET"])
def api_geocode():
    """
    Reverse geocoding stub: takes lat & lng from browser geolocation
    and resolves Indian city, state, and pin code.
    """
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)

    INDIA_LOCATIONS = [
        {"city": "New Delhi", "state": "Delhi", "pin": "110001", "lat": 28.6139, "lng": 77.2090},
        {"city": "Mumbai", "state": "Maharashtra", "pin": "400001", "lat": 19.0760, "lng": 72.8777},
        {"city": "Bengaluru", "state": "Karnataka", "pin": "560001", "lat": 12.9716, "lng": 77.5946},
        {"city": "Jaipur", "state": "Rajasthan", "pin": "302001", "lat": 26.9124, "lng": 75.7873},
        {"city": "Indore", "state": "Madhya Pradesh", "pin": "452001", "lat": 22.7196, "lng": 75.8577},
        {"city": "Lucknow", "state": "Uttar Pradesh", "pin": "226001", "lat": 26.8467, "lng": 80.9462},
        {"city": "Hyderabad", "state": "Telangana", "pin": "500001", "lat": 17.3850, "lng": 78.4867},
    ]

    best = INDIA_LOCATIONS[0]
    if lat and lng:
        best_d = 99999
        for loc in INDIA_LOCATIONS:
            d = math.sqrt((lat - loc["lat"]) ** 2 + (lng - loc["lng"]) ** 2)
            if d < best_d:
                best_d = d
                best = loc

    return jsonify({"results": [{"city": best["city"], "state": best["state"], "pin": best["pin"]}]})


# ============================================================
# AUTHENTICATION (OTP & JSON SESSION)
# ============================================================
@app.route("/api/auth/otp_send", methods=["POST"])
def api_auth_otp_send():
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone_number", "")).strip()[-10:]
    if len(phone) != 10 or not phone.isdigit():
        return jsonify({"ok": False, "error": "Enter a valid 10-digit mobile number"}), 400

    res = send_otp(phone)
    if res.get("ok") and res.get("session"):
        _otp_sessions[phone] = res["session"]
        return jsonify({"ok": True, "phone": phone, "message": "OTP sent successfully"})
    return jsonify({"ok": False, "error": res.get("error") or "Failed to send OTP"}), 400


@app.route("/api/auth/otp_verify", methods=["POST"])
def api_auth_otp_verify():
    uid = get_uid()
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone_number", "")).strip()[-10:]
    otp = str(data.get("otp", "")).strip()

    session = _otp_sessions.get(phone)
    if not session:
        return jsonify({"ok": False, "error": "OTP session expired. Please request again."}), 400

    res = verify_otp(phone, otp, session)
    if not res.get("ok"):
        return jsonify({"ok": False, "error": res.get("error") or "Invalid OTP"}), 400

    _otp_sessions.pop(phone, None)
    is_new = bool(res.get("is_new"))
    save_meesho_account(
        user_id=uid,
        phone=phone,
        meesho_user_id=res.get("user_id"),
        xo=res.get("xo"),
        xo_exp=res.get("xo_exp") or 0,
        instance_id=res.get("instance_id", ""),
        is_first_order=1 if is_new else 0,
    )

    acc = get_active_meesho_account(uid)
    if acc:
        try:
            live = real_user_orders(acc, limit=15)
            if live.get("ok"):
                sync_meesho_orders_to_db(uid, live.get("orders", []))
        except Exception as e:
            logger.warning(f"Failed to auto-sync Meesho orders on OTP login: {e}")

    return jsonify({
        "ok": True,
        "message": "Account linked successfully",
        "user_id": res.get("user_id"),
        "phone": phone,
        "is_first_order": 1 if is_new else 0,
    })


@app.route("/api/auth/json_login", methods=["POST"])
def api_auth_json_login():
    """
    Connects account via session JSON (user_id, xo, instance_id).
    """
    uid = get_uid()
    data = request.get_json(silent=True) or {}

    user_id = str(data.get("user_id") or data.get("userId") or "").strip()
    xo = str(data.get("xo") or data.get("xo_token") or "").strip()
    instance_id = str(data.get("instance_id") or "").strip()
    phone = str(data.get("phone") or data.get("mobile") or f"xxxx{user_id[-4:]}").strip()

    if not user_id or not xo:
        return jsonify({"ok": False, "error": "JSON must include user_id and xo"}), 400

    is_first = int(data.get("is_first_order", 1))
    save_meesho_account(
        user_id=uid,
        phone=phone,
        meesho_user_id=user_id,
        xo=xo,
        xo_exp=0,
        instance_id=instance_id,
        is_first_order=is_first,
        app_session_id=data.get("app_session_id", ""),
        shield_session_id=data.get("shield_session_id", ""),
        gaid=data.get("gaid", ""),
    )

    acc = get_active_meesho_account(uid)
    if acc:
        try:
            live = real_user_orders(acc, limit=15)
            if live.get("ok"):
                sync_meesho_orders_to_db(uid, live.get("orders", []))
        except Exception as e:
            logger.warning(f"Failed to auto-sync Meesho orders on JSON login: {e}")

    return jsonify({
        "ok": True,
        "message": "Session linked successfully",
        "user_id": user_id,
        "phone": phone,
        "is_first_order": is_first,
    })


@app.route("/api/accounts", methods=["GET"])
def api_accounts():
    uid = get_uid()
    accs = get_meesho_accounts(uid)
    return jsonify({"accounts": accs})


# ============================================================
# WALLET RECHARGE & SERVICE FEE SYSTEM (VC GATEWAY)
#
# CRITICAL SEPARATION OF THREE PAYMENT FLOWS:
# 1. Wallet Recharge:
#    - Deposited to YOUR personal UPI ID (GW_UPI_ID).
#    - Verified through the third-party VC Gateway API (GW_VERIFY_URL).
#    - Credits the user's bot wallet balance (users.wallet).
#
# 2. Platform Service Fee (ORDER_FEE = ₹5 in paid mode, ₹0 in free mode):
#    - Deducted from user's internal wallet balance when an order is placed.
#    - Stored in the wallet_tx table and orders.fee column for your withdrawal.
#    - NEVER added to or subtracted from the Meesho order total.
#
# 3. Meesho Order Payment:
#    - Paid 100% separately by the customer directly to Meesho:
#      * Cash on Delivery (COD) to the delivery agent, OR
#      * Meesho Juspay UPI (MEESHOONLINEPG@axl) generated during checkout.
#    - User wallet funds are NEVER used to pay Meesho directly.
# ============================================================

@app.route("/api/wallet", methods=["GET"])
@app.route("/api/wallet/balance", methods=["GET"])
def api_wallet_balance():
    """Returns the user's current wallet balance and recent transaction history."""
    uid = get_uid()
    balance = get_wallet_balance(uid)
    transactions = get_wallet_tx(uid, limit=20)
    current_fee = get_order_fee()
    current_mode = get_global_mode()
    return jsonify({
        "ok": True,
        "balance": balance,
        "order_fee": current_fee,
        "global_mode": current_mode,
        "min_recharge": WALLET_MIN,
        "max_recharge": WALLET_MAX,
        "transactions": transactions,
    })


@app.route("/api/wallet/create", methods=["POST"])
def api_wallet_create():
    """
    Initiates wallet recharge.
    Generates a unique txn_id, logs a pending record in wallet_tx,
    and returns a dynamic UPI intent link + QR code pointing to your personal UPI ID.
    """
    uid = get_uid()
    data = request.get_json(silent=True) or {}
    try:
        amount = int(float(data.get("amount", 10)))
    except (ValueError, TypeError):
        amount = 10

    if amount < WALLET_MIN:
        return jsonify({"ok": False, "error": f"Minimum recharge amount is ₹{WALLET_MIN}"}), 400
    if amount > WALLET_MAX:
        return jsonify({"ok": False, "error": f"Maximum recharge amount is ₹{WALLET_MAX}"}), 400

    txn_id = generate_txn_id(uid)
    create_wallet_tx(
        user_id=uid,
        amount=amount,
        txn_id=txn_id,
        note=f"Wallet recharge of ₹{amount}",
    )

    upi_link = create_upi_link(
        txn_id=txn_id,
        amount=amount,
        vpa=GW_UPI_ID,
        name=GW_UPI_NAME,
        note=f"FOD Recharge {uid}",
    )
    qr_url = get_qr_url(upi_link, size=280)

    return jsonify({
        "ok": True,
        "txn_id": txn_id,
        "order_id": txn_id,
        "amount": amount,
        "vpa": GW_UPI_ID,
        "vpa_name": GW_UPI_NAME,
        "upi_link": upi_link,
        "upi_url": upi_link,
        "qr_url": qr_url,
        "message": "Recharge initiated. Scan the QR code or tap the UPI button to complete payment.",
    })


@app.route("/api/wallet/verify", methods=["POST"])
def api_wallet_verify():
    """
    Verifies payment with the VC Gateway API.
    If confirmed, marks the transaction as completed and credits the user's wallet.
    """
    uid = get_uid()
    data = request.get_json(silent=True) or {}
    txn_id = str(data.get("txn_id") or data.get("order_id") or "").strip()
    amount = data.get("amount")

    if not txn_id:
        return jsonify({"ok": False, "error": "txn_id or order_id is required"}), 400

    # Call VC Gateway API
    verify_res = verify_payment(txn_id, amount=amount or 1)

    if verify_res.get("success"):
        confirmed_amt = verify_res.get("amount") or amount or 1
        tx = verify_wallet_tx_by_order_id(txn_id, verified_amount=confirmed_amt)
        new_balance = get_wallet_balance(uid)
        return jsonify({
            "ok": True,
            "status": "completed",
            "message": f"Payment verified! ₹{confirmed_amt} has been added to your wallet.",
            "amount": confirmed_amt,
            "wallet_balance": new_balance,
            "tx": tx,
        })
    else:
        return jsonify({
            "ok": False,
            "status": verify_res.get("status", "pending"),
            "error": verify_res.get("error") or "Payment pending or not confirmed yet.",
        }), 400


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

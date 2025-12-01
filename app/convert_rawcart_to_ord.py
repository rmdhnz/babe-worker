from modules.crud_utility import *
from modules.maps_utility import *
from modules.olsera_service import *
from modules.models_sqlalchemy import Outlet, StrukLog, User, Combo, Product, combo_product
from modules.sqlalchemy_setup import get_db_session
from collections import defaultdict
from sqlalchemy.orm import joinedload, Session
from sqlalchemy import select
from fastapi.responses import JSONResponse
import requests
import json
import os
import threading
from datetime import datetime, timedelta

load_dotenv()
APP_MODE = os.getenv("APP_ENV", "local")
WEBHOOK_URL = os.getenv("WEBHOOK_LARAVEL_ORDER_CALLBACK")
OLSERA_STRUK = os.getenv(
    "STRUK_OLSERA",
    "https://invoice.olsera.co.id/pos-receipt?lang=id&store=kulkasbabe&order_no=",
)
URL_DRIVER = os.getenv("URL_LIST_DRIVER")


class StrukMaker:
    def __init__(self):
        self.variant_priority_order = ["C", "P", "L", "X"]

    # 🔹 Hitung jumlah driver
    def count_driver_available(self) -> int:
        response = requests.get(URL_DRIVER)
        if response.status_code == 200:
            data = response.json()
            return sum(1 for d in data if d.get("status") == "STAY")
        return -1

    # 🔹 Agregasi item by prodvar
    def aggregate_cart_by_prodvar(self, cart: list) -> list:
        agg = defaultdict(lambda: {
            "prodvar_id": None, "name": None, "qty": 0,
            "disc": 0.0, "harga_satuan": 0.0
        })
        for item in cart:
            pvar = str(item["prodvar_id"])
            if agg[pvar]["prodvar_id"] is None:
                agg[pvar]["prodvar_id"] = pvar
                agg[pvar]["name"] = item["name"]
            agg[pvar]["qty"] += item["qty"]
            agg[pvar]["disc"] += float(item.get("disc", 0))
            agg[pvar]["harga_satuan"] += float(item["harga_satuan"])
        return list(agg.values())

    # 🔹 Agregasi item by combo
    def aggregate_cart_by_combo(self, cart: list, db: Session) -> list:
        olsera_combo_ids = list({item["combo_id"] for item in cart if item.get("combo_id")})
        if not olsera_combo_ids:
            return []
        rows = db.execute(
            select(
                combo_product.c.combo_id,
                combo_product.c.olsera_combo_id,
                combo_product.c.product_id,
                combo_product.c.qty,
                combo_product.c.item_id,
                combo_product.c.olsera_prod_id,
                Product.name,
                Product.has_variant,
                Product.variants,
            )
            .join(Product, Product.id == combo_product.c.product_id)
            .where(combo_product.c.olsera_combo_id.in_(olsera_combo_ids))
        ).all()
        combo_reqs = {}
        combo_id_map = {}
        for combo_id, olsera_combo_id, product_id, req_qty, item_id, olsera_prod_id, prod_name, _, variants in rows:
            combo_reqs.setdefault(olsera_combo_id, {})[olsera_prod_id] = {
                "req_qty": req_qty, "item_id": item_id,
                "name": prod_name, "variants": variants
            }
            combo_id_map[olsera_combo_id] = combo_id
        combos = db.query(Combo).filter(Combo.id.in_(combo_id_map.values())).all()
        combo_map = {c.id: c for c in combos}

        result = []
        for olsera_combo_id, reqs in combo_reqs.items():
            combo_cart_items = [i for i in cart if i.get("combo_id") == olsera_combo_id]
            cart_qty_map = defaultdict(int)
            for i in combo_cart_items:
                cart_qty_map[i["product_id"]] += i["qty"]
            combo_qty_candidates = []
            for olsera_pid, meta in reqs.items():
                combo_qty_candidates.append(cart_qty_map.get(olsera_pid, 0) // meta["req_qty"])
            combo_qty = min(combo_qty_candidates) if combo_qty_candidates else 0
            combo_id = combo_id_map[olsera_combo_id]
            result.append({
                "combo_id": olsera_combo_id,
                "name": combo_map[combo_id].name if combo_id in combo_map else f"Combo-{olsera_combo_id}",
                "qty": combo_qty,
                "items": [
                    {
                        "id": meta["item_id"],
                        "product_id": olsera_pid,
                        "name": meta["name"],
                        "product_variant_id": next(
                            (i.get("variant_id") for i in combo_cart_items if i["product_id"] == olsera_pid),
                            None
                        ),
                        "qty": meta["req_qty"] * combo_qty,
                    }
                    for olsera_pid, meta in reqs.items()
                ]
            })
        return result

    # 🔹 Move item to order
    def move_cart_to_order(self, cart: list, order_id: str, access_token: str, is_combo=False):
        if not is_combo:
            for idx, item in enumerate(cart):
                try:
                    success, resp = add_prod_with_update_detail(
                        order_id=str(order_id),
                        product_id=str(item["prodvar_id"]),
                        quantity=item["qty"],
                        disc=item["disc"],
                        price=item["harga_satuan"],
                        access_token=access_token,
                        note="Order web"
                    )
                    if not success:
                        return False, f"Stok produk {item['name']} tidak cukup"
                except Exception as e:
                    return False, str(e)
        else:
            for combo in cart:
                try:
                    success, _ = add_combo_to_order(
                        order_id=str(order_id),
                        combo_id=str(combo["combo_id"]),
                        quantity=combo["qty"],
                        combo_items=combo["items"],
                        access_token=access_token
                    )
                    if not success:
                        return False, f"Stok Combo {combo['name']} tidak cukup"
                except Exception as e:
                    return False, str(e)
        return True, "OKE"

    # 🔹 Process Items
    def process_items(self, raw_cart, order_id, access_token) -> dict:
        carts = [c for c in raw_cart if not c.get("combo_id")]
        main = []
        add = []
        for c in carts:
            if c.get("prodvar_id"):
                main.append({
                    "product_id": c["id"],
                    "prodvar_id": c["prodvar_id"],
                    "name": c["name"],
                    "harga_satuan": c["harga_satuan"],
                    "qty": c["qty"],
                    "disc": float(c["disc"] or 0)
                })
            else:
                add.append(c)
        aggregated = self.aggregate_cart_by_prodvar(main)
        success, msg = self.move_cart_to_order(aggregated, order_id, access_token)
        if not success:
            update_status(order_id=order_id, status="X", access_token=access_token)
            return {"success": False, "message": msg}
        for add_item in add:
            success, _ = add_prod_to_order(
                order_id=order_id,
                product_id=add_item["product_id"],
                quantity=add_item["qty"],
                access_token=access_token,
            )
            if not success:
                update_status(order_id=order_id, status="X", access_token=access_token)
                return {"success": False, "message": f"Stock produk {add_item['name']} tidak cukup"}
        return {"success": True, "message": "Items berhasil"}

    # 🔹 Process Combo
    def process_combo(self, raw_cart, order_id, db, access_token):
        carts = [cart for cart in raw_cart["cells"] if cart.get("combo_id")]
        aggregated = self.aggregate_cart_by_combo(carts, db)
        success, msg = self.move_cart_to_order(aggregated, order_id, access_token, True)
        if not success:
            update_status(order_id, "X", access_token)
            return {"success": False, "message": msg}
        return {"success": True, "message": "Combo berhasil"}

    # 🔥 HANDLE ORDER (FULL)
    def handle_order(self, raw_cart):
        print(f"[STRUK] Mulai proses order untuk user_id={raw_cart['user_id']}")
        if raw_cart["express_delivery"]:
            total_driver = self.count_driver_available()
            if total_driver < 2:
                return JSONResponse(
                    content={
                        "success": False,
                        "message": "Express tidak tersedia saat ini.",
                        "total_driver": total_driver,
                    }
                )

        access_token = get_token_by_outlet_id(raw_cart["outlet_id"])
        with get_db_session() as session:
            try:
                user = session.query(User).filter(User.id == raw_cart["user_id"]).first()
                if raw_cart["payment_type"] == "Cash" and user.qris_used < 2:
                    return JSONResponse(content={
                        "success": False,
                        "message": "Minimal 2x QRIS sebelum Cash",
                        "data": {}
                    })

                cust_telp = raw_cart["telepon"]
                cust_name = raw_cart["name"]
                today = datetime.now().strftime("%Y-%m-%d")

                order_id, order_no = create_order(
                    order_date=today,
                    customer_id=cust_telp,
                    nama_kastamer=cust_name,
                    nomor_telepon=cust_telp,
                    notes=(raw_cart["notes"] or ""),
                    access_token=access_token,
                )

            except Exception as e:
                return JSONResponse(content={"success": False, "message": f"Gagal create order: {e}", "data": {}})

            if not raw_cart["cells"]:
                update_status(order_id=order_id, status="X", access_token=access_token)
                return JSONResponse(content={"success": False, "message": "Cart kosong"})

            combo_cart = [c for c in raw_cart["cells"] if c.get("combo_id")]
            item_cart = [i for i in raw_cart["cells"] if i not in combo_cart]

            if combo_cart:
                res = self.process_combo(raw_cart, order_id, session, access_token)
                if not res["success"]:
                    return JSONResponse(content={"success": False, "message": res["message"]})

            if item_cart:
                res = self.process_items(item_cart, order_id, access_token)
                if not res["success"]:
                    return JSONResponse(content={"success": False, "message": res["message"]})

            payment_modes = list_payment_modes(order_id, access_token)
            selected = next((pm for pm in payment_modes if pm["name"].lower() == raw_cart["payment_type"].lower()), None)

            if not selected:
                update_status(order_id=order_id, status="X", access_token=access_token)
                return JSONResponse(content={"success": False, "message": "Metode pembayaran tidak dikenali"})

            payment_id = selected["id"]
            detail = fetch_order_details(order_id, access_token)
            total_amount = int(float(detail["data"]["total_amount"]))

            update_payment(
                order_id=order_id,
                payment_amount=total_amount,
                payment_date=today,
                payment_mode_id=payment_id,
                access_token=access_token,
                payment_payee="Order Web",
                payment_seq="0",
                payment_currency_id="IDR",
            )
            update_status(order_id, "A", access_token)

            # hitung estimasi
            delivery = {"1": "FD", "2": "I", "3": "EX"}
            outlet = session.query(Outlet).options(joinedload(Outlet.conditions)).filter(Outlet.id == 1).first()
            tambahan = sum((c.nilai for c in outlet.conditions), 0)
            estimasi = estimasi_tiba(raw_cart.get("jarak", 0), delivery[str(raw_cart.get("delivery_type_id", "1"))], datetime.now())
            estimasi_dt = datetime.combine(datetime.today(), datetime.strptime(estimasi, "%H:%M").time())
            estimasi_dt += timedelta(minutes=int(float(tambahan)))
            estimasi_final = estimasi_dt.strftime("%H:%M")

            log_id = None
            with get_db_session() as log_session:
                lg = StrukLog(order_id=order_id, order_no=order_no, is_forward=False)
                log_session.add(lg)
                log_session.flush()
                log_id = lg.id
                log_session.commit()

            response_json = {
                "success": True,
                "message": "Order berhasil",
                "data": {
                    "order_id": order_id,
                    "order_no": order_no,
                    "estimasi_tiba": estimasi_final,
                    "log_id": log_id,
                },
            }

            # 🔥 CALLBACK KE LARAVEL
            try:
                requests.post(WEBHOOK_URL, json=response_json["data"], timeout=5)
                print("[CALLBACK] Sukses callback ke Laravel")
            except Exception as e:
                print(f"[CALLBACK] Gagal callback ke Laravel: {e}")

            return JSONResponse(content=response_json)

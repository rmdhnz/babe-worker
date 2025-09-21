from modules.crud_utility import *
from modules.maps_utility import *
from modules.olsera_service import *
import requests
from modules.models_sqlalchemy import Outlet, StrukLog, User,Combo,Product,combo_product
from collections import defaultdict
from modules.sqlalchemy_setup import get_db_session
from dotenv import load_dotenv
import os
import threading
from fastapi.responses import JSONResponse
from struk_forwarder import forward_struk
from sqlalchemy.orm import joinedload,Session
from sqlalchemy import select

load_dotenv()
URL_DRIVER = os.getenv("URL_LIST_DRIVER")
OLSERA_STRUK = os.getenv(
    "STRUK_OLSERA",
    "https://invoice.olsera.co.id/pos-receipt?lang=id&store=kulkasbabe&order_no=",
)


def search_ongkir_related_product(keywords: str, access_token: str) -> tuple:
    url = "https://api-open.olsera.co.id/api/open-api/v1/en/product"
    params = {
        "search_column[]": "name",
        "search_text[]": keywords,
    }

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # Akan memunculkan exception jika status bukan 2xx
        data = response.json()

        return data["data"][0]["id"]
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - Response: {response.text}")
        return None
    except Exception as err:
        print(f"Other error occurred: {err}")
        return {}


class StrukMaker:
    def __init__(self):
        self.variant_priority_order = ["C", "P", "L", "X"]

    def move_cart_to_order(self, cart: dict, order_id: str, access_token: str,type_combo:bool = False):
        """
        Pindahkan semua item dalam cart ke order dengan ID order_id.
        carts_by_product_id: dict {product_id: Cart}
        """
        # if not cart:
        #     print("Cart kosong, tidak ada item untuk dipindahkan. Struk di batalkan")
        #     return False, "Cart kosong, tidak ada item untuk dipindahkan."
        
        if not type_combo : 
            print("Move items to order...")


            # Tambahkan produk ke order
            for idx,item in enumerate(cart):
                prodvar_id = item["prodvar_id"]
                qty = item["qty"]
                try:
                    # success, resp = add_prod_to_order(
                    #     order_id, prodvar_id, qty, access_token=access_token
                    # )
                    discount = cart[idx]["disc"] if idx < len(cart) else 0.0
                    print("Mencoba API Baru...")
                    success,resp = add_prod_with_update_detail(order_id=str(order_id),product_id=str(prodvar_id),quantity=qty,disc=discount,price=item["harga_satuan"],                    access_token=access_token,note="Order web")
                    if not success:
                        print(
                            msg := f"Stok produk {item['name']} tidak mencukupi. Struk dibatalkan"
                        )
                        return False, msg
                except requests.exceptions.HTTPError:
                    print(
                        "Ada kesalahan HTTP saat memasukkan produk ke order. Struk di-voidkan."
                    )
                    return (
                        False,
                        "Ada kesalahan HTTP saat memasukkan produk ke order. Struk di-voidkan.",
                    )
                except Exception as e:
                    print(f"Ada kesalahan saat memasukkan produk ke order. Error: {e}")
                    return (
                        False,
                        f"Ada kesalahan saat memasukkan produk ke order. Error: {e}",
                    )
        else : 
            print("Move combo to order...")
            for combo in cart : 
                combo_id = combo["combo_id"]
                qty = combo["qty"]
                combo_items = combo["items"]
                try : 
                    success,_ = add_combo_to_order(
                        order_id=str(order_id),
                        combo_id=str(combo_id),
                        quantity=qty,
                        combo_items=combo_items,
                        access_token=access_token
                    )
                    if not success : 
                        print(
                            msg := f"Stok produk {combo['name']} tidak mencukupi. Struk dibatalkan"
                        )
                        return False, msg
                except Exception as e: 
                    print(msg:=f"Ada kesalahan saat memasukkan combo {combo['name']} [{combo['combo_id']}]")
                    return False,msg
        print(
            "Semua item berhasil dipindahkan ke order dan diskon paket telah diperbarui."
        )
        return (
            True,
            "Semua item berhasil dipindahkan ke order dan diskon paket telah diperbarui.",
        )

    def aggregate_cart_by_prodvar(self, cart: list) -> list:
        # Aggregation by prodvar_id
        agg_by_prodvar = defaultdict(
            lambda: {
                "prodvar_id": None,
                "name": None,
                "qty": 0,
                "disc": 0.0,
                "harga_satuan": 0.0,
            }
        )

        for item in cart:
            pvar = str(item["prodvar_id"])
            if agg_by_prodvar[pvar]["prodvar_id"] is None:
                agg_by_prodvar[pvar]["prodvar_id"] = pvar
                agg_by_prodvar[pvar]["name"] = item["name"]
                # agg_by_prodvar[pvar]["product_id"] = item["product_id"]

            agg_by_prodvar[pvar]["qty"] += item["qty"]
            agg_by_prodvar[pvar]["disc"] += float(item.get("disc", 0))
            agg_by_prodvar[pvar]["harga_satuan"] += float(item["harga_satuan"])
        aggregated_by_prodvar = list(agg_by_prodvar.values())
        return aggregated_by_prodvar
        
    def _aggregate_cart_by_combo(self, cart: list, db: Session) -> list:
        # ambil semua olsera_combo_id unik dari cart
        olsera_combo_ids = list({item["combo_id"] for item in cart if item.get("combo_id")})
        print(f"olsera_combo_ids ditemukan di cart: {olsera_combo_ids}")

        if not olsera_combo_ids:
            return []

        # ambil requirement setiap combo dari tabel pivot combo_product JOIN product
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

        print(f"Debug ROWS: {rows}")

        combo_reqs = {}
        combo_id_map = {}
        for combo_id, olsera_combo_id, product_id, req_qty, item_id, olsera_prod_id, prod_name, has_variant, variants in rows:
            combo_reqs.setdefault(olsera_combo_id, {})[product_id] = {
                "req_qty": req_qty,
                "olsera_prod_id": olsera_prod_id,
                "item_id": item_id,
                "name": prod_name,
                "variants": variants,
            }
            combo_id_map[olsera_combo_id] = combo_id

        # ambil detail combo
        combos = db.query(Combo).filter(Combo.id.in_(combo_id_map.values())).all()
        combo_map = {c.id: c for c in combos}

        result = []
        for olsera_combo_id, reqs in combo_reqs.items():
            combo_cart_items = [i for i in cart if i.get("combo_id") == olsera_combo_id]

            # hitung total qty per product_id di cart
            cart_qty_map = defaultdict(int)
            for i in combo_cart_items:
                cart_qty_map[i["product_id"]] += i["qty"]

            # berapa kali paket bisa dibentuk?
            combo_qty_candidates = []
            for pid, meta in reqs.items():
                have_qty = cart_qty_map.get(pid, 0)
                combo_qty_candidates.append(have_qty // meta["req_qty"])
            combo_qty = min(combo_qty_candidates) if combo_qty_candidates else 0

            combo_id = combo_id_map[olsera_combo_id]
            result.append({
                "combo_id": olsera_combo_id,
                "name": combo_map[combo_id].name if combo_id in combo_map else f"Combo-{olsera_combo_id}",
                "qty": combo_qty,
                "items": [
                    {
                        "id": meta["item_id"],
                        "product_id": meta["olsera_prod_id"],
                        "name": meta["name"],
                        "product_variant_id": next((i.get("variant_id") for i in combo_cart_items if i["product_id"] == pid), None),
                        "qty": meta["req_qty"] * combo_qty,
                    }
                    for pid, meta in reqs.items()
                ]
            })

        print("Hasil akhir agregasi:", result)
        return result

    def aggregate_cart_by_combo(self, cart: list, db: Session) -> list:
        # ambil semua olsera_combo_id unik dari cart
        olsera_combo_ids = list({item["combo_id"] for item in cart if item.get("combo_id")})
        print(f"olsera_combo_ids ditemukan di cart: {olsera_combo_ids}")

        if not olsera_combo_ids:
            return []

        # ambil requirement setiap combo dari tabel pivot combo_product JOIN product
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

        print(f"Debug ROWS: {rows}")

        combo_reqs = {}
        combo_id_map = {}
        for combo_id, olsera_combo_id, product_id, req_qty, item_id, olsera_prod_id, prod_name, has_variant, variants in rows:
            combo_reqs.setdefault(olsera_combo_id, {})[olsera_prod_id] = {   # 🔑 pakai olsera_prod_id
                "req_qty": req_qty,
                "item_id": item_id,
                "name": prod_name,
                "variants": variants,
            }
            combo_id_map[olsera_combo_id] = combo_id

        # ambil detail combo
        combos = db.query(Combo).filter(Combo.id.in_(combo_id_map.values())).all()
        combo_map = {c.id: c for c in combos}

        result = []
        for olsera_combo_id, reqs in combo_reqs.items():
            combo_cart_items = [i for i in cart if i.get("combo_id") == olsera_combo_id]

            # hitung total qty per olsera_prod_id di cart
            cart_qty_map = defaultdict(int)
            for i in combo_cart_items:
                cart_qty_map[i["product_id"]] += i["qty"]   # 🔑 pakai "id" dari cart (olsera_prod_id)

            # berapa kali paket bisa dibentuk?
            combo_qty_candidates = []
            for olsera_pid, meta in reqs.items():
                have_qty = cart_qty_map.get(olsera_pid, 0)
                combo_qty_candidates.append(have_qty // meta["req_qty"])
            combo_qty = min(combo_qty_candidates) if combo_qty_candidates else 0

            combo_id = combo_id_map[olsera_combo_id]
            result.append({
                "combo_id": olsera_combo_id,
                "name": combo_map[combo_id].name if combo_id in combo_map else f"Combo-{olsera_combo_id}",
                "qty": combo_qty,
                "items": [
                    {
                        "id": meta["item_id"],
                        "product_id": olsera_pid,   # 🔑 pakai olsera_prod_id
                        "name": meta["name"],
                        "product_variant_id": next((i.get("variant_id") for i in combo_cart_items if i["product_id"] == olsera_pid), None),  # 🔑 match ke cart.id
                        "qty": meta["req_qty"] * combo_qty,
                    }
                    for olsera_pid, meta in reqs.items()
                ]
            })

        print("Hasil akhir agregasi:", result)
        return result



    def count_driver_available(self) -> int:
        response = requests.get(URL_DRIVER)
        if response.status_code == 200:
            data = response.json()
            total_driver_availabel = sum(1 for d in data if d.get("status") == "STAY")
            return total_driver_availabel
        else:
            return -1

    def handle_order(self, raw_cart):
        print(f"Memproses : {json.dumps(raw_cart['cells'],indent=2)}")
        if raw_cart["express_delivery"]:
            total_driver = self.count_driver_available()
            if total_driver < 20:
                print(
                    "Jumlah driver tidak memenuhi untuk express. Jumlah driver saat ini ",
                    total_driver,
                )
                return JSONResponse(
                    content={
                        "success": False,
                        "message": "Jumlah Driver untuk Express sedang tidak tersedia, silahkan pilih Free Delivery atau Instant Delivery",
                        "data": {},
                        "total_driver": total_driver,
                    }
                )
        access_token = get_token_by_outlet_id(raw_cart["outlet_id"])
        with get_db_session() as session:
            user = session.query(User).filter(User.id == raw_cart["user_id"]).first()

            # 1. Create order
            customer = cek_kastamer(
                nomor_telepon=raw_cart["telepon"], access_token=access_token
            )
            cust_telp = raw_cart["telepon"]
            cust_name = raw_cart["name"]

            today_str = datetime.now().strftime("%Y-%m-%d")

            try:
                print(f"Membuat order atas nama {raw_cart['name']}...")
                order_id, order_no = create_order(
                    order_date=today_str,
                    customer_id=customer[0] if customer else None,
                    nama_kastamer=cust_name,
                    nomor_telepon=cust_telp,
                    notes=(raw_cart["notes"] or "Tidak ada catatan tambahan."),
                    access_token=access_token,
                )
                print(
                    f"Order berhasil dibuat dengan ID: {order_id} dan Nomor: {order_no}. Order dimasukkan ke dalam log."
                )
                log_dir = "log"
                log_file = os.path.join(log_dir,"order.log")
                os.makedirs(log_dir,exist_ok=True)
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                with open(log_file,"a",encoding="utf-8") as f : 
                    f.write(f"{order_no}|{order_id}|{now_str}\n")

                if raw_cart["payment_type"] == "QRIS":
                    return JSONResponse(
                        content={
                            "success": True,
                            "message": "Order berhasil dibuat untuk pembayaran QRIS",
                            "data": {
                                "order_id": order_id,
                                "order_no": order_no,
                            },
                        }
                    )

            except Exception as e:
                print(f"Gagal membuat order: {e}")
                return JSONResponse(
                    content={
                        "success": False,
                        "message": f"Gagal membuat order: {e}",
                        "data": {},
                    }
                )
                # return None, None, f"Gagal membuat order: {e}"
            print("Memproses combo...")
            if not raw_cart["cells"] : 
                print(msg:="Cart kosong, tidak ada item untuk dipindahkan. Struk di batalkan")
                update_status(order_id=order_id,status="X",access_token=access_token)
                return JSONResponse(content={
                    "success" : False,
                    "message" : msg,
                })

            combo_cart = [combo for combo in raw_cart["cells"] if (combo.get("prodvar_id") and combo.get("combo_id"))]
            item_cart = [item for item in raw_cart["cells"] if item not in combo_cart]

            if combo_cart :   
                result = self.process_combo(
                    raw_cart=raw_cart,
                    order_id=order_id,
                    db=session,
                    access_token=access_token
                )
                if not result["success"] : 
                    return JSONResponse(
                        content={
                            "success" : False,
                            "message" : result["message"],
                            "data" : {}
                        }
                    )
            
            if item_cart :
                print("Mulai memproses item")


                result = self.process_items(item_cart, order_id, access_token)
                if not result["success"]:
                    return JSONResponse(
                        content={"success": False, "message": result["message"], "data": {}}
                    )
                

            payment_modes = list_payment_modes(order_id, access_token)

            order_details = fetch_order_details(order_id, access_token)
            selected_mode = next(
                (
                    pm
                    for pm in payment_modes
                    if pm["name"].lower() == raw_cart["payment_type"].lower()
                ),
                None,
            )
            if not selected_mode:
                update_status(order_id=order_id, status="X", access_token=access_token)
                # return None, None, "Metode Pembayaran tidak dikenali. Struk divoidkan"
                return JSONResponse(
                    content={
                        "success": False,
                        "message": "Metode Pembayaran tidak dikenali. Struk divoidkan",
                        "data": {},
                    }
                )
            payment_id = selected_mode["id"]
            total_amount = int(float(order_details["data"]["total_amount"]))

            update_payment(
                order_id=order_id,
                payment_amount=str(total_amount),
                payment_date=today_str,
                payment_mode_id=str(payment_id),
                access_token=access_token,
                payment_payee="Order Web",
                payment_seq="0",
                payment_currency_id="IDR",
            )
            update_status(order_id=order_id, status="Z", access_token=access_token)
            outlet = (
                session.query(Outlet)
                .options(joinedload(Outlet.conditions))
                .filter(Outlet.id == raw_cart["outlet_id"])
                .first()
            )
            tambahan_waktu = sum((cond.nilai for cond in outlet.conditions), 0)
            delivery = {"1": "FD", "2": "I", "3": "EX"}
            location = parse_address(raw_cart["formatted_address"])
            payload_request = {
                "order_id": order_id,
                "order_no": order_no,
                "cust_name": raw_cart["name"],
                "phone_number": raw_cart["telepon"],
                "distance": raw_cart.get("jarak", 0.0),
                "address": raw_cart.get("address", "Tidak diketahui"),
                "kecamatan": location["kecamatan"],
                "kelurahan": location["kelurahan"],
                "total_amount": total_amount,
                "payment_type": raw_cart.get("payment_type", "unknown"),
                "jenis_pengiriman": delivery[
                    str(raw_cart.get("delivery_type_id", "1"))
                ],
                "notes": raw_cart.get("notes"),
                "struk_url": f"{OLSERA_STRUK}{order_no}",
                "status": "lunas",
                "tambahan_waktu": tambahan_waktu,
                "from_number": outlet.phone,
            }

            max_luncur_str = estimasi_tiba(
                raw_cart.get("jarak", 0),
                delivery[str(raw_cart.get("delivery_type_id", "1"))],
                datetime.now(),
            )

            max_luncur_dt = datetime.combine(
                datetime.today(), datetime.strptime(max_luncur_str, "%H:%M").time()
            )
            tambahan_waktu = sum((cond.nilai for cond in outlet.conditions), 0)
            max_luncur_dt += timedelta(minutes=int(float(tambahan_waktu)))

            estimasi_final = max_luncur_dt.strftime("%H:%M")

            # membuat log struk
            log_id = None
            with get_db_session() as log_session:
                log_entry = StrukLog(
                    order_id=order_id,
                    order_no=order_no,
                    is_forward=False,
                )
                log_session.add(log_entry)
                log_session.flush()
                log_id = log_entry.id
                log_session.commit()

            print("Mengirim invoice ke grup...")
            # forward_struk(payload_request)
            threading.Thread(target=forward_struk, args=(payload_request,)).start()
            print("Struk berhasil diteruskan ke Grup")

            # return (
            #     order_id,
            #     order_no,
            #     "Order berhasil dibuat dan ongkir telah diperbarui.",
            #     estimasi_final,
            #     log_id,
            # )
            return JSONResponse(
                content={
                    "success": True,
                    "message": "Order berhasil dibuat dan ongkir telah diperbarui.",
                    "data": {
                        "order_id": order_id,
                        "order_no": order_no,
                        "estimasi_tiba": estimasi_final,
                        "log_id": log_id,
                    },
                }
            )

    def process_items(self, raw_cart, order_id, access_token) -> dict:
        carts = [cart for cart in raw_cart if not cart.get("combo_id")]
        main_product = []
        additional_product = []
        for cart in carts:
            if cart.get("prodvar_id"):
                main_product.append(
                    {
                        "product_id": cart["id"],
                        "prodvar_id": cart["prodvar_id"],
                        "name": cart["name"],
                        "harga_satuan" : cart["harga_satuan"],
                        "qty": cart["qty"],
                        "product_type_id": cart["product_type_id"],
                        "disc": float(cart["disc"] or 0),
                    }
                )
            else:
                additional_product.append(
                    {
                        "product_id": cart["id"],
                        "name": cart["name"],
                        "qty": cart["qty"],
                        "harga_satuan" : cart.get("harga_satuan",0.0),
                        "product_type_id": cart["product_type_id"],
                        "disc": float(cart.get("disc") or 0),
                    }
                )
        
        print("Mulai agregasi produk...")

        aggregated_carts = self.aggregate_cart_by_prodvar(main_product)
        print("SELESAI AGREGASI...")
        print("Move cart to order..")
        success, msg = self.move_cart_to_order(
            aggregated_carts, order_id, access_token=access_token
        )
        if not success:
            update_status(order_id=order_id, status="X", access_token=access_token)
            return {"success": False, "message": msg}

        for add_item in additional_product:
            try:
                if add_item["product_type_id"] == 3:
                    print(f"Additional product (Combo) : {add_item['name']}")
                    # Combo
                    combo_details = fetch_product_combo_details(
                        add_item["product_id"], access_token
                    )
                    combo_items = combo_details["data"]["items"]["data"]
                    for item in combo_items:
                        success, data = add_prod_to_order(
                            order_id=order_id,
                            product_id=item.get("product_id"),
                            quantity=1,
                            access_token=access_token,
                        )
                        if not success:
                            update_status(
                                order_id=order_id, status="X", access_token=access_token
                            )
                            return {
                                "success": False,
                                "message": f"Stock Produk {item} tidak mencukupi",
                            }
                elif add_item["product_type_id"] == 4:
                    print(f"Additional Product (Merch) : {add_item['name']}")

                    success, _ = add_prod_to_order(
                        order_id=order_id,
                        product_id=add_item["product_id"],
                        access_token=access_token,
                        quantity=1,
                    )

                    if not success:
                        update_status(
                            order_id=order_id, status="X", access_token=access_token
                        )
                        return {
                            "success": False,
                            "message": f"Stock produk {add_item['name']} tidak mencukupi",
                        }
                    order_details = fetch_order_details(
                        order_id=order_id, access_token=access_token
                    )
                    order_details = order_details["data"]["orderitems"]
                    matching_detail = next(
                        (
                            detail
                            for detail in order_details
                            if detail["product_id"] == add_item["product_id"]
                        ),
                        None,
                    )

                    if matching_detail:
                        success, _ = update_order_detail(
                            order_id=order_id,
                            id=matching_detail["id"],
                            disc="0",
                            qty=1,
                            price="0",
                            note="Tukar Koin",
                            access_token=access_token,
                        )
                        if not success:
                            update_status(
                                order_id=order_id, status="X", access_token=access_token
                            )
                            return {
                                "success": False,
                                "message": f"Gagal Update detail merchandise di order",
                            }
                    else:
                        update_status(
                            order_id=order_id,
                            status="X",
                            access_token=access_token,
                        )
                        print(
                            f"Order detail tidak ditemukan untuk produk {add_item['name']}"
                        )
                        return {
                            "success": False,
                            "message": f"Order detail tidak ditemukan untuk produk {add_item['name']}",
                        }
                else:
                    success, msg = add_prod_to_order(
                        order_id=order_id,
                        product_id=add_item["product_id"],
                        quantity=1,
                        access_token=access_token,
                    )
                    if not success:
                        update_status(
                            order_id=order_id, status="X", access_token=access_token
                        )
                        return {
                            "success": True,
                            "message": f"Stock Produk {item} tidak mencukupi",
                        }

            except Exception as e:
                update_status(order_id=order_id, status="X", access_token=access_token)
                print(
                    f"Gagal menambahkan produk tambahan yaitu {add_item['name']} :  {e}"
                )
                return {
                    "success": False,
                    "message": f"Gagal menambahkan produk tambahan yaitu {add_item['name']}, stok tidak mencukupi. Struk dibatalkan.",
                }

        return {"success": True, "message": "Berhasil proses per item dari carts"}
    
    def process_combo(self,raw_cart,order_id,db: Session,access_token) -> dict : 
        carts = [cart for cart in raw_cart["cells"] if cart.get("combo_id")]
        main_combo = []
        additional_combo = []

        for cart in carts : 
            if cart.get("prodvar_id") : 
                main_combo.append(
                    {
                        "product_id": cart["id"],
                        "combo_id" : cart["combo_id"],
                        "prodvar_id": cart["prodvar_id"],
                        "name": cart["name"],
                        "harga_satuan" : cart["harga_satuan"],
                        "qty": cart["qty"],
                        "product_type_id": cart["product_type_id"],
                        "disc": float(cart["disc"] or 0),
                    }
                )
            else : 
                additional_combo.append(
                    {
                        "product_id": cart["id"],
                        "combo_id" : cart["combo_id"],
                        "name": cart["name"],
                        "qty": cart["qty"],
                        "harga_satuan" : cart.get("harga_satuan",0.0),
                        "product_type_id": cart["product_type_id"],
                        "disc": float(cart.get("disc") or 0),
                    }
                )
            
        print("Mulai agregasi combo...")
        aggregated_combos = self.aggregate_cart_by_combo(main_combo,db)
        print("Selesai AGREGASI COMBO...")
        print(f"Hasil aggregasi : {json.dumps(aggregated_combos,indent=2)}")
        print("Move cart to order...")
        success,msg = self.move_cart_to_order(
            aggregated_combos,
            order_id,
            access_token,
            True
        )
        if not success : 
            update_status(order_id,"X",access_token)
            return { 
                "success" : False,
                "message" : msg
            }
        
        return { 
            "success" : True,
            "message" : f"Berhasil Proses per combo dari carts"
        }




    def process_qris_payment(self, raw_cart):
        access_token = get_token_by_outlet_id(raw_cart["outlet_id"])
        result = self.process_items(
            raw_cart=raw_cart, order_id=raw_cart["order_id"], access_token=access_token
        )
        if not result["success"]:
            return JSONResponse(
                content={"success": False, "message": result["message"], "data": {}}
            )
        payment_modes = list_payment_modes(
            order_id=raw_cart["order_id"], access_token=access_token
        )
        order_details = fetch_order_details(raw_cart["order_id"], access_token)
        selected_mode = next(
            (
                pm
                for pm in payment_modes
                if pm["name"].lower() == raw_cart["payment_type"].lower()
            ),
            None,
        )

        if not selected_mode:
            update_status(
                order_id=raw_cart["order_id"], status="X", access_token=access_token
            )
            return JSONResponse(
                content={
                    "success": False,
                    "message": "Metode pembayaran tidak dikenali",
                    "data": {},
                }
            )

        payment_id = selected_mode["id"]
        total_amount = int(float(order_details["data"]["total_amount"]))
        today_str = datetime.now().strftime("%Y-%m-%d")
        update_payment(
            order_id=raw_cart["order_id"],
            payment_amount=str(total_amount),
            payment_date=today_str,
            payment_mode_id=str(payment_id),
            access_token=access_token,
            payment_payee="Order Web",
            payment_seq="0",
            payment_currency_id="IDR",
        )
        update_status(
            order_id=raw_cart["order_id"], status="Z", access_token=access_token
        )
        with get_db_session() as session:
            outlet = (
                session.query(Outlet)
                .options(joinedload(Outlet.conditions))
                .filter(Outlet.id == raw_cart["outlet_id"])
                .first()
            )
            tambahan_waktu = sum((cond.nilai for cond in outlet.conditions), 0)
            delivery = {"1": "FD", "2": "I", "3": "EX"}
            location = parse_address(raw_cart["formatted_address"])
            payload_request = {
                "order_id": raw_cart["order_id"],
                "order_no": raw_cart["order_no"],
                "cust_name": raw_cart["name"],
                "phone_number": raw_cart["telepon"],
                "distance": raw_cart.get("jarak", 0.0),
                "address": raw_cart.get("address", "Tidak diketahui"),
                "kecamatan": location["kecamatan"],
                "kelurahan": location["kelurahan"],
                "total_amount": total_amount,
                "payment_type": raw_cart.get("payment_type", "unknown"),
                "jenis_pengiriman": delivery[
                    str(raw_cart.get("delivery_type_id", "1"))
                ],
                "notes": raw_cart.get("notes"),
                "struk_url": f"{OLSERA_STRUK}{raw_cart['order_no']}",
                "status": "lunas",
                "tambahan_waktu": tambahan_waktu,
                "from_number": outlet.phone,
            }
            max_luncur_str = estimasi_tiba(
                raw_cart.get("jarak", 0),
                delivery[str(raw_cart.get("delivery_type_id", "1"))],
                datetime.now(),
            )
            max_luncur_dt = datetime.combine(
                datetime.today(), datetime.strptime(max_luncur_str, "%H:%M").time()
            )
            tambahan_waktu = sum((cond.nilai for cond in outlet.conditions), 0)
            max_luncur_dt += timedelta(minutes=int(float(tambahan_waktu)))
            estimasi_final = max_luncur_dt.strftime("%H:%M")
            log_id = None
            with get_db_session() as log_session:
                log_entry = StrukLog(
                    order_id=raw_cart["order_id"],
                    order_no=raw_cart["order_no"],
                    is_forward=False,
                )
                log_session.add(log_entry)
                log_session.flush()
                log_id = log_entry.id
                log_session.commit()
            print("Mengirim invoice ke grup...")
            # forward_struk(payload_request)
            threading.Thread(target=forward_struk, args=(payload_request,)).start()
            print("Struk berhasil diteruskan ke Grup")
            return JSONResponse(
                content={
                    "success": True,
                    "message": "Order berhasil diupdate setelah pembayaran QRIS Sukses",
                    "data": {
                        "order_id": raw_cart["order_id"],
                        "order_no": raw_cart["order_no"],
                        "estimasi_tiba": estimasi_final,
                        "log_id": log_id,
                    },
                }
            )

from modules.crud_utility import *
from modules.maps_utility import *
from modules.olsera_service import *
import requests
from modules.models_sqlalchemy import User
from collections import defaultdict
from modules.sqlalchemy_setup import get_db_session
from dotenv import load_dotenv
import os


load_dotenv()
URL_DRIVER = os.getenv("URL_LIST_DRIVER")


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

    def move_cart_to_order(self, cart: dict, order_id: str, access_token: str):
        """
        Pindahkan semua item dalam cart ke order dengan ID order_id.
        carts_by_product_id: dict {product_id: Cart}
        """
        if not cart:
            print("Cart kosong, tidak ada item untuk dipindahkan.")
            return False, "Cart kosong, tidak ada item untuk dipindahkan."

        # Tambahkan produk ke order
        for item in cart:
            prodvar_id = item["prodvar_id"]
            qty = item["qty"]
            try:
                success, resp = add_prod_to_order(
                    order_id, prodvar_id, qty, access_token=access_token
                )
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

        # Update diskon item berdasarkan data cart
        try:
            ord_detail = fetch_order_details(
                order_id=order_id, access_token=access_token
            )
            orders = ord_detail["data"]["orderitems"]
        except Exception as e:
            return False, f"Gagal mengambil detail order: {e}"

        for idx, item in enumerate(orders):
            item_id = item["id"]
            item_qty = item["qty"]
            item_disc = cart[idx]["disc"] if idx < len(cart) else 0.0
            item_price = int(float(item.get("fprice", 0).replace(".", "")))

            try:
                update_order_detail(
                    order_id=str(order_id),
                    id=str(item_id),
                    disc=str(item_disc),
                    price=str(item_price),
                    qty=str(item_qty),
                    note="Promo Paket",
                    access_token=access_token,
                )
            except Exception as e:
                return False, "Gagal update detail paket di order."
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
                "harga_total": 0.0,
            }
        )

        for item in cart:
            pvar = str(item["prodvar_id"])
            if agg_by_prodvar[pvar]["prodvar_id"] is None:
                agg_by_prodvar[pvar]["prodvar_id"] = pvar
                agg_by_prodvar[pvar]["name"] = item["name"]
                agg_by_prodvar[pvar]["product_id"] = item["product_id"]

            agg_by_prodvar[pvar]["qty"] += item["qty"]
            agg_by_prodvar[pvar]["disc"] += float(item.get("disc", 0))
        aggregated_by_prodvar = list(agg_by_prodvar.values())
        return aggregated_by_prodvar

    def count_driver_available(self) -> int:
        response = requests.get(URL_DRIVER)
        if response.status_code == 200:
            data = response.json()
            total_driver_availabel = sum(1 for d in data if d.get("status") == "STAY")
            return total_driver_availabel
        else:
            return -1

    def handle_order(self, raw_cart):
        if raw_cart["express_delivery"]:
            total_driver = self.count_driver_available()
            if total_driver < 20:
                print(
                    "Jumlah driver tidak memenuhi untuk express. Jumlah driver saat ini ",
                    total_driver,
                )
                return (
                    None,
                    -1,
                    "Jumlah Driver untuk Express sedang tidak tersedia, silahkan pilih Free Delivery atau Instant Delivery",
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
                print(f"Membuat order atas nama {user.name}...")
                order_id, order_no = create_order(
                    order_date=today_str,
                    customer_id=customer[0] if customer else None,
                    nama_kastamer=cust_name,
                    nomor_telepon=cust_telp,
                    notes="Buat order web",
                    access_token=access_token,
                )
                print(
                    f"Order berhasil dibuat dengan ID: {order_id} dan Nomor: {order_no}"
                )
            except Exception as e:
                print(f"Gagal membuat order: {e}")
                return None, None, f"Gagal membuat order: {e}"

            # 2. Masukkan item ke cart
            carts = raw_cart["cells"]
            main_products = []
            additional_products = []

            for cart in carts:
                if cart.get("prodvar_id"):
                    main_products.append(
                        {
                            "product_id": cart["id"],
                            "prodvar_id": cart["prodvar_id"],
                            "name": cart["name"],
                            "qty": cart["qty"],
                            "product_type_id": cart["product_type_id"],
                            "disc": float(cart["disc"] or 0),
                        }
                    )
                else:
                    additional_products.append(
                        {
                            "product_id": cart["id"],
                            "name": cart["name"],
                            "qty": cart["qty"],
                            "product_type_id": cart["product_type_id"],
                            "disc": float(cart.get("disc") or 0),
                        }
                    )

            # 2. AGGREGASI CART BY PRODVAR
            aggregated_carts = self.aggregate_cart_by_prodvar(main_products)

            # 3. Move aggregated cart to order
            success, msg = self.move_cart_to_order(
                aggregated_carts,
                order_id,
                access_token=access_token,
            )
            if not success:
                update_status(order_id=order_id, status="X", access_token=access_token)
                return None, None, msg
            for add_item in additional_products:
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
                                return (
                                    None,
                                    None,
                                    f"Stock Produk {item} tidak mencukupi",
                                )

                    elif add_item["product_type_id"] == 4:
                        print(f"Additional product (Merch) : {add_item['name']}")
                        # Merchandise, tambahkan dulu produknya
                        sucess, data = add_prod_to_order(
                            order_id=order_id,
                            product_id=add_item["product_id"],
                            quantity=1,
                            access_token=access_token,
                        )
                        if not success:
                            return (
                                None,
                                None,
                                f"Stock Produk {item} tidak mencukupi",
                            )

                        # Ambil detail order terbaru berdasarkan product_id
                        order_details = fetch_order_details(order_id, access_token)
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
                            update_order_detail(
                                order_id=order_id,
                                id=matching_detail[
                                    "id"
                                ],  # Ini ID dari order detail, bukan product
                                disc="0",
                                qty=1,
                                price="0",
                                note="Tukar Koin",
                                access_token=access_token,
                            )
                        else:
                            print(
                                f"Order detail tidak ditemukan untuk produk {add_item['name']}"
                            )

                    else:
                        # Produk tambahan biasa
                        add_prod_to_order(
                            order_id=order_id,
                            product_id=add_item["product_id"],
                            quantity=1,
                            access_token=access_token,
                        )

                except Exception as e:
                    print(
                        f"Gagal menambahkan produk tambahan yaitu {add_item['name']}: {e}"
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
                return None, None, "Metode Pembayaran tidak dikenali. Struk divoidkan"
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

            if not success:
                return None, None, msg
            return (
                order_id,
                order_no,
                "Order berhasil dibuat dan ongkir telah diperbarui.",
            )

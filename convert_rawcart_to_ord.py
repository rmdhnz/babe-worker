from modules.crud_utility import *
from modules.maps_utility import *
import requests
from modules.models_sqlalchemy import Cart
from sqlalchemy.orm import sessionmaker
from modules.sqlalchemy_setup import engine


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

    def move_cart_to_order(
        self, carts_by_product_id: dict, order_id: str, access_token: str
    ):
        """
        Pindahkan semua item dalam cart ke order dengan ID order_id.
        carts_by_product_id: dict {product_id: Cart}
        """
        if not carts_by_product_id:
            return False, "Cart kosong, tidak ada item untuk dipindahkan."

        carts = list(carts_by_product_id.values())

        # Tambahkan produk ke order
        for item in carts:
            prodvar_id = item.prodvar_id
            qty = item.quantity
            try:
                resp = add_prod_to_order(
                    order_id, prodvar_id, qty, access_token=access_token
                )
                if resp is None:
                    return (
                        False,
                        "Gagal menambahkan produk ke order, produk habis. Struk di-voidkan.",
                    )
            except requests.exceptions.HTTPError:
                return (
                    False,
                    "Ada kesalahan HTTP saat memasukkan produk ke order. Struk di-voidkan.",
                )
            except Exception as e:
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

        if len(orders) != len(carts):
            return (
                False,
                "Jumlah item order dan cart tidak sama. Tidak bisa update diskon.",
            )

        for order_item in orders:
            prodvar_id = order_item.get("product_variant_id") or order_item.get(
                "product_id"
            )
            cart_item = next(
                (c for c in carts if c.prodvar_id == prodvar_id),
                None,
            )
            if cart_item is None:
                continue

            try:
                update_order_detail(
                    order_id=str(order_id),
                    id=str(order_item["id"]),
                    disc=str(cart_item.discount),
                    price=str(cart_item.harga_total - cart_item.discount),
                    qty=str(order_item["qty"]),
                    note="",
                    access_token=access_token,
                )
            except Exception as e:
                return False, f"Gagal update detail paket di order. Error: {e}"

        return (
            True,
            "Semua item berhasil dipindahkan ke order dan diskon paket telah diperbarui.",
        )

    def handle_order(self, raw_cart):
        access_token = get_token_by_outlet_id(raw_cart["outlet_id"])
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()

        # 1. Create order
        customer = cek_kastamer(
            nomor_telepon=raw_cart["telepon"], access_token=access_token
        )
        cust_telp = raw_cart["telepon"]
        cust_name = raw_cart["name"]

        today_str = datetime.now().strftime("%Y-%m-%d")

        try:
            print("Membuat order...")
            order_id, order_no = create_order(
                order_date=today_str,
                customer_id=customer[0] if customer else None,
                nama_kastamer=cust_name,
                nomor_telepon=cust_telp,
                notes="Buat order web",
                access_token=access_token,
            )
            print(f"Order berhasil dibuat dengan ID: {order_id} dan Nomor: {order_no}")
        except Exception as e:
            return None, None, f"Gagal membuat order: {e}"

        ongkir_name = distance_cost_rule(raw_cart["jarak"], raw_cart["is_free_ongkir"])
        id_ongkir = search_ongkir_related_product(ongkir_name, access_token)

        if ongkir_name != "Gratis Ongkir":
            add_prod_to_order(
                order_id=order_id,
                product_id=id_ongkir,
                quantity=1,
                access_token=access_token,
            )
        else:
            pass

        # 2. Masukkan item ke cart
        carts = (
            session.query(Cart)
            .filter(
                Cart.user_id == raw_cart["user_id"],
                Cart.outlet_id == raw_cart["outlet_id"],
            )
            .all()
        )
        carts_by_product_id = {cart.product_id: cart for cart in carts}

        # 4. Move aggregated cart to order
        success, msg = self.move_cart_to_order(
            carts_by_product_id,
            order_id,
            access_token=access_token,
        )
        if not success:
            return None, None, msg
        # 5. Update ongkir
        return order_id, order_no, "Order berhasil dibuat dan ongkir telah diperbarui."

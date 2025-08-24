import requests
import time
import logging
from modules.models_sqlalchemy import Product
from modules.sqlalchemy_setup import get_db_session
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)


def cek_kastamer(nomor_telepon: str, access_token: str) -> tuple:
    url = "https://api-open.olsera.co.id/api/open-api/v1/en/customersupplier/customer"
    params = {
        "search_column[]": "phone",
        "search_text[]": (
            "+62" + nomor_telepon[1:]
            if nomor_telepon.startswith("0")
            else nomor_telepon
        ),
    }

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # Akan memunculkan exception jika status bukan 2xx
        data = response.json()

        return data["data"][0]["id"], data["data"][0]["name"] if data["data"] else None
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - Response: {response.text}")
        return None
    except Exception as err:
        print(f"Other error occurred: {err}")
        return {}


def list_payment_modes(order_id: str, access_token: str) -> list:
    url = "https://api-open.olsera.co.id/api/open-api/v1/en/order/openorder/editpayment"

    params = {"order_id": order_id}

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # Akan memunculkan exception jika status bukan 2xx
        data = response.json()
        payment_modes = data["data"]["payment_modes"]
        return payment_modes

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - Response: {response.text}")
    except Exception as err:
        print(f"Other error occurred: {err}")
        return None


def update_payment(
    order_id: str,
    payment_amount: str,
    payment_date: str,
    payment_mode_id: str,
    access_token: str,
    payment_payee: str = "",
    payment_seq: str = "0",
    payment_currency_id: str = "IDR",
):
    url = (
        "https://api-open.olsera.co.id/api/open-api/v1/en/order/openorder/updatepayment"
    )
    params = {
        "order_id": order_id,
        "payment_amount": payment_amount,
        "payment_date": payment_date,
        "payment_mode_id": payment_mode_id,
        "payment_payee": payment_payee,
        "payment_seq": payment_seq,
        "payment_currency_id": payment_currency_id,
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=params, headers=headers)
        response.raise_for_status()  # Akan memunculkan exception jika status bukan 2xx
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(
            f"HTTP error occurred on order detail update: {http_err} - Response: {response.text}"
        )
    except Exception as err:
        print(f"Other error occurred on order detail update: {err}")


def update_order_detail(
    order_id: str,
    id: str,
    disc: int,
    note: str,
    price: str,
    qty: int,
    access_token: str,
) -> None:
    url = (
        "https://api-open.olsera.co.id/api/open-api/v1/en/order/openorder/updatedetail"
    )
    params = {
        "order_id": order_id,
        "id": id,
        "discount": disc,
        "note": note,
        "price": price,
        "qty": qty,
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=params, headers=headers)
        response.raise_for_status()  # Akan memunculkan exception jika status bukan 2xx
        return True, response.json()
    except requests.exceptions.HTTPError as http_err:
        print(
            f"HTTP error occurred on order detail update: {http_err} - Response: {response.text}"
        )
        return False, None
    except Exception as err:
        print(f"Other error occurred on order detail update: {err}")
        return False, None


def update_status(order_id: str, status: str, access_token: str) -> None:
    url = (
        "https://api-open.olsera.co.id/api/open-api/v1/en/order/openorder/updatestatus"
    )
    params = {"order_id": order_id, "status": status}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=params, headers=headers)
        response.raise_for_status()  # Akan memunculkan exception jika status bukan 2xx
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(
            f"HTTP error occurred on order status update: {http_err} - Response: {response.text}"
        )
    except Exception as err:
        print(f"Other error occurred on order status update: {err}")


def create_order(
    order_date: str,
    access_token: str,
    customer_id: str = None,
    nomor_telepon: str = None,
    nama_kastamer: str = None,
    notes: str = "",
) -> tuple:

    url = "https://api-open.olsera.co.id/api/open-api/v1/en/order/openorder"

    if customer_id is not None:
        params = {
            "order_date": order_date,
            "currency_id": "IDR",
            "customer_id": customer_id,
            "notes": notes,
        }
    else:
        params = {
            "order_date": order_date,
            "currency_id": "IDR",
            "customer_phone": nomor_telepon,
            "customer_name": nama_kastamer,
            "customer_type_id": "195972",
            "notes": notes,
        }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=params, headers=headers)
        response.raise_for_status()
        json_response = response.json()
        order_id = json_response["data"]["id"]
        order_no = json_response["data"]["order_no"]
        return order_id, order_no
    except requests.exceptions.HTTPError as http_err:
        print(
            f"HTTP error occurred on product inputting: {http_err} - Response: {response.text}"
        )
    except Exception as err:
        print(f"Other error occurred on product inputting: {err}")


def fetch_open_ord_id_via_resi(resi: str, access_token: str):
    url = "https://api-open.olsera.co.id/api/open-api/v1/en/order/openorder"

    params = {
        "search_column[]": "order_no",
        "search_text[]": resi,
    }

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # Raise error kalau bukan status 200-an
        data = response.json()
        if data and "data" in data:
            return data["data"][0]["id"]
        else:
            print("No order found for the given resi.")
            return None
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - Response: {response.text}")


def fetch_close_ord_id_via_resi(resi: str, access_token: str):
    url = "	https://api-open.olsera.co.id/api/open-api/v1/en/order/closeorder"

    params = {
        "search_column[]": "order_no",
        "search_text[]": resi,
    }

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # Raise error kalau bukan status 200-an
        data = response.json()
        if data and "data" in data:
            return data["data"][0]["id"]
        else:
            print("No order found for the given resi.")
            return None
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - Response: {response.text}")
        return None


def fetch_order_details(order_id: str, access_token: str):
    url = "https://api-open.olsera.co.id/api/open-api/v1/en/order/openorder/detail"
    params = {
        "id": order_id,
    }

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # Raise error kalau bukan status 200-an
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - Response: {response.text}")
    except Exception as err:
        print(f"Other error occurred: {err}")


def add_prod_to_order(
    order_id: str, product_id: str, quantity: int, access_token: str
) -> None:
    url = "https://api-open.olsera.co.id/api/open-api/v1/en/order/openorder/additem"
    params = {"order_id": order_id, "item_products": product_id, "item_qty": quantity}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(url, json=params, headers=headers)
        response.raise_for_status()  # Akan memunculkan exception jika status bukan 2xx
        return True, response.json()
    except requests.exceptions.HTTPError as http_err:
        print(
            f"HTTP error occurred on product inputting: {http_err} - Response: {response.text}"
        )
        print(f"Produk dengan ID : {product_id} stock tidak tersedia")
        return False, None
    except Exception as err:
        print(f"Other error occurred on product inputting: {err}")
        return False, None


def fetch_product_combo_details(combo_id: str, access_token: str):
    url = "https://api-open.olsera.co.id/api/open-api/v1/en/productcombo/detail"
    params = {
        "id": combo_id,
    }

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # Raise error kalau bukan status 200-an
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - Response: {response.text}")
    except Exception as err:
        print(f"Other error occurred: {err}")


def fetch_products_page(token: str, page: int, per_page: int = 15):
    url = f"https://api-open.olsera.co.id/api/open-api/v1/en/product"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"page": page, "per_page": per_page}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 429:
        print("[WARNING] Rate limited (429), menunggu 20 detik...")
        time.sleep(20)
        return fetch_products_page(token, page, per_page)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"[ERROR] API failed: {response.status_code} - {response.text}")
        return None


def fetch_combos_page(token, page=1, per_page=15):
    url = f"https://api-open.olsera.co.id/api/open-api/v1/en/productcombo"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"page": page, "per_page": per_page}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 429:
        print("[WARNING] Rate limited (429), menunggu 20 detik...")
        time.sleep(20)
        return fetch_combos_page(token, page)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"[ERROR] API failed: {response.status_code} - {response.text}")
        return None


def fetch_combo_detail(token, combo_id):
    import time

    url = "https://api-open.olsera.co.id/api/open-api/v1/en/productcombo/detail"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"id": combo_id}

    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 429:
                wait = 10 + attempt * 5
                print(f"[RATE LIMIT] 429 Too Many Requests, retrying after {wait}s...")
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json().get("data", {})
        except requests.exceptions.HTTPError as http_err:
            print(
                f"[ERROR] HTTP error saat fetch combo detail ID {combo_id}: {http_err}"
            )
            break
        except Exception as err:
            print(f"[ERROR] Unknown error saat fetch combo detail ID {combo_id}: {err}")
            break
    return {}


def process_item(
    order_id: str, nama_produk: str, qty: int, cart: list, access_token: str
):
    outlet_id = 1
    with get_db_session() as session:
        produk = (
            session.query(Product)
            .options(joinedload(Product.stock))
            .filter(
                Product.name.ilike(f"%{nama_produk}%"), Product.outlet_id == outlet_id
            )
            .first()
        )
        if not produk:
            logger.error("Produk cocok dengan '%s' tidak ditemukan.", nama_produk)
            update_status(order_id, "X", access_token=access_token)
            return (
                False,
                f"Gagal menemukan produk dengan nama '{nama_produk}'. Coba gunakan nama lengkap produk sesuai database.",
            )

import os
from unicodedata import category
import pymysql
from datetime import datetime
import pandas as pd
import time
from dotenv import load_dotenv
import requests
from sqlalchemy.orm import joinedload, sessionmaker
from modules.sqlalchemy_setup import SessionLocal, engine
import json

from modules.models_sqlalchemy import Product

# Load .env file
load_dotenv()

# ENV
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT"))
DB_NAME = os.getenv("DB_DATABASE")
DB_USER = os.getenv("DB_USERNAME")
DB_PASS = os.getenv("DB_PASSWORD")


def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        port=DB_PORT,
        autocommit=True,
    )


def get_all_products_with_stock():
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    products = session.query(Product).options(joinedload(Product.stock)).limit(5).all()
    return products


def get_product_by_olsera_id(olsera_id, outlet_id: int):
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    product = (
        session.query(Product)
        .options(joinedload(Product.stock))
        .filter(Product.olsera_id == olsera_id, Product.outlet_id == outlet_id)
        .first()
    )
    return product


def get_all_tokens():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT outlet_id, token FROM token_caches")
        result = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        cursor.close()
    conn.close()
    return OutletResult(result, columns)


def get_token_by_outlet_id(outlet_id: int) -> str:
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT token FROM token_caches WHERE outlet_id = %s", (outlet_id,)
        )
        result = cursor.fetchone()
    conn.close()
    if not result:
        raise Exception(f"Token not found for outlet_id {outlet_id}")
    return result[0]


def get_outlet_name(outlet_id: int) -> str:
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT name FROM outlets WHERE id = %s", (outlet_id,))
        result = cursor.fetchone()
    conn.close()
    if not result:
        raise Exception(f"Outlet not found for id {outlet_id}")
    return result[0]


def get_all_outlets():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM outlets")
        result = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        cursor.close()
        conn.close()
        return OutletResult(result, columns)
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching outlet: {e}")
        exit(1)


def update_product_details(
    olsera_id, outlet_id, category, percentage_alcohol, alias, keywords
):
    try:
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        product = session.query(Product).filter(Product.olsera_id == olsera_id).first()
        if product:
            # Cek apakah percentage_alcohol valid
            if (
                isinstance(percentage_alcohol, str)
                and percentage_alcohol.replace(".", "", 1).isdigit()
            ):
                product.percentage_alcohol = float(percentage_alcohol)
            else:
                product.percentage_alcohol = 0.0
                print(f"Invalid percentage alcohol for product {olsera_id}. Set to 0.")

            product.keywords = keywords
            product.tag = category
            product.alias = alias
            session.commit()
            print(f"Product {olsera_id} updated successfully.")
        else:
            print(
                f"Product with olsera_id {olsera_id} and outlet_id {outlet_id} not found."
            )
    except Exception as e:
        print(f"Error updating product [{olsera_id}]: {e}")


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


def get_product_variants_by_olsera_id(olsera_id, outlet_id):

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT variants FROM products WHERE olsera_id = %s AND outlet_id = %s",
            (olsera_id, outlet_id),
        )
        row = cursor.fetchone()
    conn.close()
    if not row or not row[0]:
        return []
    try:
        variants = json.loads(row[0])
        return variants if isinstance(variants, list) else []
    except Exception as e:
        print(f"[ERROR] Gagal decode variants untuk olsera_id={olsera_id}: {e}")
        return []


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
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(
            f"HTTP error occurred on order detail update: {http_err} - Response: {response.text}"
        )
    except Exception as err:
        print(f"Other error occurred on order detail update: {err}")


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

    # response = requests.post(url, json=params, headers=headers)
    # response.raise_for_status()  # Akan memunculkan exception jika status bukan 2xx
    # return response.json()

    try:
        response = requests.post(url, json=params, headers=headers)
        response.raise_for_status()  # Akan memunculkan exception jika status bukan 2xx
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(
            f"HTTP error occurred on product inputting: {http_err} - Response: {response.text}"
        )
        return response.json()
    except Exception as err:
        print(f"Other error occurred on product inputting: {err}")


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


class OutletResult:
    def __init__(self, result, columns):
        self.result = result
        self.columns = columns

    def json(self):
        return [dict(zip(self.columns, row)) for row in self.result]

    def panda(self):
        return pd.DataFrame(self.result, columns=self.columns)

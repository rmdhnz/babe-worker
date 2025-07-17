import os
import pymysql
from datetime import datetime
import pandas as pd
import time
from dotenv import load_dotenv
import requests

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


class OutletResult:
    def __init__(self, result, columns):
        self.result = result
        self.columns = columns

    def json(self):
        return [dict(zip(self.columns, row)) for row in self.result]

    def panda(self):
        return pd.DataFrame(self.result, columns=self.columns)

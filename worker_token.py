import os
import time
import json
import pymysql
import threading
import schedule
import requests
from datetime import datetime
from dotenv import load_dotenv
from modules.crud_utility import get_outlet_id_by_name

# Load .env file
load_dotenv()

# Ambil ENV
APP_ID = os.getenv("APP_ID_SMG")
SECRET_KEY = os.getenv("SECRET_KEY_SMG")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT"))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
OUTLET_NAME = os.getenv("OUTLET_NAME")
OUTLET_ID = get_outlet_id_by_name()


def get_access_token(app_id, secret_key):
    url = "https://api-open.olsera.co.id/api/open-api/v1/id/token"
    params = {"app_id": app_id, "secret_key": secret_key, "grant_type": "secret_key"}

    try:
        response = requests.post(url, params=params)
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.exceptions.HTTPError as http_err:
        print(f"[{datetime.now()}] ❌ HTTP error: {http_err} - {response.text}")
    except Exception as err:
        print(f"[{datetime.now()}] ❌ General error: {err}")
    return None


# Simpan token ke database
def insert_token_to_db(token: str):
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            port=DB_PORT,
            autocommit=True,
        )
        with conn.cursor() as cursor:
            now = datetime.now().isoformat(sep=" ", timespec="microseconds")

            # Cek apakah data dengan outlet_id sudah ada
            cursor.execute(
                "SELECT COUNT(*) FROM token_caches WHERE outlet_id = %s", (OUTLET_ID,)
            )
            exists = cursor.fetchone()[0]

            if exists:
                # UPDATE token dan timestamp_column
                cursor.execute(
                    """
                    UPDATE token_caches
                    SET token = %s,
                        timestamp_column = %s,
                        updated_at = %s
                    WHERE outlet_id = %s
                """,
                    (token, now, now, OUTLET_ID),
                )
                print(f"[{datetime.now()}] Token updated for outlet_id {OUTLET_ID}")
            else:
                # INSERT baris baru
                cursor.execute(
                    """
                    INSERT INTO token_caches (outlet_id, token, timestamp_column, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (OUTLET_ID, token, now, now, now),
                )
                print(f"[{datetime.now()}] Token inserted for outlet_id {OUTLET_ID}")

    except Exception as e:
        print(f"[{datetime.now()}]  DB insert/update error: {e}")


# Fungsi utama
def job():
    print(f"[{datetime.now()}] Fetching access token...")
    token = get_access_token(APP_ID, SECRET_KEY)
    if token:
        insert_token_to_db(token)
    else:
        print(f"[{datetime.now()}] ❌ Failed to retrieve token.")


# Jalankan scheduler
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    print(
        f"[{datetime.now()}] Worker started for outlet '{OUTLET_NAME}'. Interval: 240 minutes."
    )
    job()  # Run once on start
    schedule.every(240).minutes.do(job)
    threading.Thread(target=run_scheduler).start()

import os
import time
import json
import pymysql
import threading
import schedule
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Ambil ENV
APP_ID = os.getenv("APP_ID_SMG")
SECRET_KEY = os.getenv("SECRET_KEY_SMG")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT"))
DB_NAME = os.getenv("DB_DATABASE")
DB_USER = os.getenv("DB_USERNAME")
DB_PASS = os.getenv("DB_PASSWORD")
OUTLET_SEMARANG = os.getenv("OUTLET_NAME_SEMARANG")
OUTLET_SOLO = os.getenv("OUTLET_NAME_SOLO")
OUTLET_ID_SOLO = os.getenv("OUTLET_ID_SOLO")
OUTLET_ID_SMG = os.getenv("OUTLET_ID_SMG")
TOKEN_FILE_PATH_SOLO = os.getenv("TOKEN_FILE_PATH_SOLO")


def get_token_from_file(access_token):
    try:
        with open(access_token, "r") as f:
            data = json.load(f)
            token = data.get("access_token")
            timestamp = data.get("timestamp") or datetime.now().isoformat(
                sep=" ", timespec="microseconds"
            )
            return token, timestamp
    except Exception as e:
        print(f"[{datetime.now()}] Failed to read token file: {e}")
        return None, None


def get_access_token(app_id, secret_key):
    url = "https://api-open.olsera.co.id/api/open-api/v1/id/token"
    params = {"app_id": app_id, "secret_key": secret_key, "grant_type": "secret_key"}

    try:
        response = requests.post(url, params=params)
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.exceptions.HTTPError as http_err:
        print(f"[{datetime.now()}] HTTP error: {http_err} - {response.text}")
    except Exception as err:
        print(f"[{datetime.now()}] General error: {err}")
    return None


# Simpan token ke database
def insert_token_to_db(token: str, outlet_id, timestamp: str = None):
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
            now = timestamp or datetime.now().isoformat(
                sep=" ", timespec="microseconds"
            )

            # Cek apakah data dengan outlet_id sudah ada
            cursor.execute(
                "SELECT COUNT(*) FROM token_caches WHERE outlet_id = %s", (outlet_id,)
            )
            exists = cursor.fetchone()[0]

            if exists:
                cursor.execute(
                    """
                    UPDATE token_caches
                    SET token = %s,
                        timestamp_column = %s,
                        updated_at = %s
                    WHERE outlet_id = %s
                """,
                    (token, now, now, outlet_id),
                )
                print(f"[{datetime.now()}] Token updated for outlet_id {outlet_id}")
            else:
                cursor.execute(
                    """
                    INSERT INTO token_caches (outlet_id, token, timestamp_column, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (outlet_id, token, now, now, now),
                )
                print(f"[{datetime.now()}] Token inserted for outlet_id {outlet_id}")

    except Exception as e:
        print(f"[{datetime.now()}] DB insert/update error: {e}")


# Fungsi utama
def job():
    print(f"[{datetime.now()}] Fetching access token...")
    token_smg = get_access_token(APP_ID, SECRET_KEY)
    token_solo, ts_solo = get_token_from_file(TOKEN_FILE_PATH_SOLO)
    if token_smg and token_solo:
        insert_token_to_db(token_smg, OUTLET_ID_SMG)
        insert_token_to_db(token_solo, OUTLET_ID_SOLO, ts_solo)
    else:
        print(f"[{datetime.now()}] Failed to retrieve token.")


# Jalankan scheduler
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    print(
        f"[{datetime.now()}] Worker started for outlet '{OUTLET_SEMARANG} and {OUTLET_SOLO}'. Interval: 240 minutes."
    )
    job()  # Run once on start
    schedule.every(240).minutes.do(job)
    threading.Thread(target=run_scheduler).start()

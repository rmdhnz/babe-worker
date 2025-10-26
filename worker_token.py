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
APP_ID_SOLO = os.getenv("APP_ID_SOLO")
SECRET_KEY_SOLO = os.getenv("SECRET_KEY_SOLO")

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
    """
    Ambil access_token dari Olsera dengan retry otomatis jika kena rate-limit (HTTP 429).
    """
    url = "https://api-open.olsera.co.id/api/open-api/v1/id/token"
    params = {"app_id": app_id, "secret_key": secret_key, "grant_type": "secret_key"}
    backoff_times = [3, 5, 10]  # detik jeda untuk retry

    for attempt, delay in enumerate(backoff_times, start=1):
        try:
            response = requests.post(url, params=params)
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                if token:
                    print(f"[{datetime.now()}] Access token retrieved successfully.")
                    return token
                else:
                    print(f"[{datetime.now()}] Response tidak mengandung access_token: {data}")
                    return None

            elif response.status_code == 429:
                print(f"[{datetime.now()}] ⚠️ Rate limited (429). Attempt {attempt}/{len(backoff_times)}. Retry in {delay}s...")
                time.sleep(delay)
                continue  # coba lagi

            else:
                print(f"[{datetime.now()}] HTTP Error {response.status_code}: {response.text}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"[{datetime.now()}] Network/Request error: {e}")
            # jika bukan 429, jangan retry
            if attempt == len(backoff_times):
                return None
            time.sleep(delay)

    # Kalau sampai di sini berarti semua retry gagal
    print(f"[{datetime.now()}] ❌ Gagal dapat token setelah {len(backoff_times)} percobaan.")
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
    token_solo = get_access_token(APP_ID_SOLO, SECRET_KEY_SOLO)
    while not token_solo  : 
        print(f"[{datetime.now()}] Retrying to fetch token for SOLO...")
        token_solo = get_access_token(APP_ID_SOLO, SECRET_KEY_SOLO)
    
    if token_solo: 
        insert_token_to_db(token_solo, OUTLET_ID_SOLO)
    else:
        print(f"[{datetime.now()}] Failed to retrieve token.")


# Jalankan scheduler
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    print(
        f"[{datetime.now()}] Worker started for outlet Solo. Interval: 240 minutes."
    )
    job()  # Run once on start
    schedule.every(240).minutes.do(job)
    threading.Thread(target=run_scheduler).start()

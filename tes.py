import pymysql
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path="/root/babe-worker/.env")
DB_USER = os.getenv("DB_USERNAME")
DB_PASS = os.getenv("DB_PASSWORD")
try:
    conn = pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USERNAME"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_DATABASE"),
    )
    print("DB_USER:", DB_USER)
    print("DB_PASS:", repr(DB_PASS))
    print("✅ Sukses konek ke MySQL!")
except Exception as e:
    print("❌ Gagal konek ke MySQL:", e)

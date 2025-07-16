import os
import pymysql
from datetime import datetime
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ENV
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT"))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")


def get_outlet_id_by_name(outlet):
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            port=DB_PORT,
            autocommit=True,
        )
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM outlets WHERE name = %s", (outlet,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            return result[0]
        else:
            raise Exception(f"Outlet '{outlet}' not found in database.")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Error fetching outlet_id: {e}")
        exit(1)

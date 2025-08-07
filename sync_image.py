from modules.crud_utility import *
from modules.olsera_service import *
import json
import time
from modules.crud_utility import get_all_outlets
import threading
import schedule

allowed_klasifikasi = [
    "Inventory Produk",
    "Inventory Mixer",
    "Inventory Snack",
    "Inventory Rokok",
]


def sync_product_images(outlet_id: int):
    token = get_token_by_outlet_id(outlet_id)
    outlet_name = get_outlet_name(outlet_id)

    page = 1
    total_updated = 0
    conn = get_db_connection()  # pindah ke luar loop
    with conn.cursor() as cursor:
        while True:
            result = fetch_products_page(token, page, per_page=100)
            if result is None:
                print(
                    f"[{outlet_name}] [WARN] Retry page {page} after 20s (429 or timeout)"
                )
                time.sleep(20)
                continue

            data = result.get("data", [])
            meta = result.get("meta", {})
            last_page = meta.get("last_page", page)

            for item in data:
                klasifikasi = item.get("klasifikasi")
                if klasifikasi not in allowed_klasifikasi:
                    continue

                olsera_id = item.get("id")
                image_data = item.get("photo_md")

                cursor.execute(
                    """
                    UPDATE products
                    SET image = %s, updated_at = NOW()
                    WHERE olsera_id = %s AND outlet_id = %s
                    """,
                    (image_data, olsera_id, outlet_id),
                )
                total_updated += 1

            print(f"[{outlet_name}] Page {page} selesai update variants.")

            if page >= last_page:
                break
            page += 1

    conn.commit()
    conn.close()
    print(f"[{outlet_name}] Total product image updated: {total_updated}")


def job():
    try:
        print("START UPDATE image")
        # all_outlets = get_all_outlets().json()
        sync_product_images(outlet_id=1)
        print("ANJAY KELAR")
    except Exception as e:
        print(f"[ERROR] [{e}]")


def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    print("Worker Image is running... ")
    job()
    schedule.every().day.at("00:30").do(job)
    threading.Thread(target=run_scheduler).start()

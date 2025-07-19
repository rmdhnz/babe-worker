import schedule
import time
import threading
from modules.sync_products_all import sync_products_all
from modules.crud_utility import get_all_outlets
from modules.combo_utility import sync_combos


def job_daily():
    try:
        print("=== [FULL DB SYNC - DAILY] ===")
        all_outlets = get_all_outlets().json()
        for outlet in all_outlets:
            outlet_id = outlet["id"]
            print(f"Syncing outlet: {outlet_id}")
            sync_products_all(outlet_id)
            sync_combos(outlet_id)
    except Exception as e:
        print(f"[ERROR][DAILY SYNC] {e}")


def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    print("Worker DB (Produk Keseluruhan) is running...")
    # job_daily()
    schedule.every().day.at("00:00").do(job_daily)
    threading.Thread(target=run_scheduler).start()

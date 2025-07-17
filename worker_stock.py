import schedule
import time
import threading
from modules.sync_product_stocks import sync_product_stocks
from modules.combo_utility import sync_combo_stocks
from modules.crud_utility import get_all_outlets


def job_stock():
    try:
        print("=== [STOCK SYNC - 5 MINUTES] ===")
        all_outlets = get_all_outlets().json()
        for outlet in all_outlets:
            outlet_id = outlet["id"]
            print(f">>> Sinkronisasi Outlet ID: {outlet_id}")
            sync_product_stocks(outlet_id=outlet_id)
            sync_combo_stocks(outlet_id=outlet_id)
    except Exception as e:
        print(f"[ERROR][STOCK SYNC] {e}")


def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    print("Worker Stock is running (every 5 minutes)...")
    job_stock()
    schedule.every(5).minutes.do(job_stock)
    threading.Thread(target=run_scheduler).start()

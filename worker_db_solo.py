import schedule
import threading
import time
from sync_products import *


def job():
    try:
        print("=== Sinkronisasi Outlet SOLO ===")
        sync_products(outlet_id=1)
    except Exception as e:
        print(f"[SOLO][ERROR] {e}")


def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    print("Worker DB is running...")
    job()
    schedule.every(5).minutes.do(job)
    threading.Thread(target=run_scheduler).start()

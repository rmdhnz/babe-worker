import schedule
import threading
import time
from sync_products import *


def job():
    try:
        print("=== Sinkronisasi Outlet SEMARANG ===")
        sync_products(outlet_id=5)
    except Exception as e:
        print(f"[SEMARANG][ERROR] {e}")


def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    print("Worker DB is running...")
    job()
    schedule.every(5).minutes.do(job)
    threading.Thread(target=run_scheduler).start()

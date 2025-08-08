from modules.crud_utility import *
from modules.sync_products_all import sync_products_all
from modules.crud_utility import get_all_outlets
from modules.combo_utility import sync_combos
from sync_variants import sync_product_variants


class SyncProductAndCombo:
    def sync_now(self, req):
        try:
            outlet = get_outlet_name(req["outlet_id"])
            print(f"=== [FULL DB SYNC [{outlet}] by {req['name']}===")
            outlet_id = req["outlet_id"]
            sync_products_all(outlet_id)
            sync_combos(outlet_id)
            sync_product_variants(outlet_id)
        except Exception as e:
            print(f"[ERROR][DAILY SYNC] {e}")


# if __name__ == "__main__":
#     print("Worker DB (Produk Keseluruhan) is running...")
#     job_daily()
#     schedule.every().day.at("00:00").do(job_daily)
#     threading.Thread(target=run_scheduler).start()

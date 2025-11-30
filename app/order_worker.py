import json
from convert_rawcart_to_ord import StrukMaker
import time

agent = StrukMaker()

MAX_RETRY = 5

def process_order(data: dict):
    order_no = data.get("order_no")
    print(f"Worker menerima order: {order_no}")

    for attempt in range(1, MAX_RETRY + 1):
        try:
            response = agent.handle_order(data)
            print(f"✔ Order selesai diproses: {order_no}")
            return response

        except Exception as e:
            print(f"⚠️ Gagal proses order {order_no} (percobaan {attempt}/{MAX_RETRY}): {e}")

            time.sleep(2 ** attempt)

    print(f"❌ Order {order_no} GAGAL setelah {MAX_RETRY} percobaan")
    raise Exception(f"FinalFailure: {order_no}")

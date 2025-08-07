import requests
from modules.crud_utility import get_all_tokens, get_token_by_outlet_id, get_all_outlets
import time
import json

access_tokens = get_all_tokens().json()


def update_status(order_id: str, status: str, access_token: str) -> None:
    url = (
        "https://api-open.olsera.co.id/api/open-api/v1/en/order/openorder/updatestatus"
    )
    params = {"order_id": order_id, "status": status}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    while True:
        try:
            response = requests.post(url, json=params, headers=headers)
            if response.status_code == 429:
                print(f"[429] Rate limited on order_id={order_id}, waiting 20s...")
                time.sleep(20)
                continue  # coba lagi
            response.raise_for_status()
            print(f"[SUCCESS] Updated order_id={order_id} to status={status}")
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            print(f"[HTTP ERROR] order_id={order_id}: {http_err} - {response.text}")
            break  # keluar dari loop
        except Exception as err:
            print(f"[OTHER ERROR] order_id={order_id}: {err}")
            break  # keluar dari loop


BASE_URL = "https://api-open.olsera.co.id/api/open-api/v1/en/order/openorder"


def fetch_filtered_order_ids(outlet_id: int) -> list[dict]:
    token = get_token_by_outlet_id(outlet_id)
    headers = {"Authorization": f"Bearer {token}"}

    filtered_orders = []
    page = 1

    while True:
        response = requests.get(BASE_URL, headers=headers, params={"page": page})

        if response.status_code == 429:
            print(f"[429] Rate limited on page {page}, retrying after 10s...")
            time.sleep(10)
            continue

        if not response.ok:
            raise Exception(
                f"[{response.status_code}] Failed to fetch page {page}: {response.text}"
            )

        data = response.json()
        orders = data.get("data", [])
        meta = data.get("meta", {})

        if not orders:
            break

        for order in orders:
            order_id = order.get("id")
            order_no = order.get("order_no", "")
            if order_no.startswith("OL"):
                filtered_orders.append({"id": order_id, "order_no": order_no})

        print(
            f"[INFO] Collected {len(filtered_orders)} filtered orders up to page {page}"
        )

        if page >= meta.get("last_page", page):
            break

        page += 1
        time.sleep(0.5)

    return filtered_orders


def save_orders_to_json(orders: list, filename: str = "open_orders_OL.json"):
    with open(filename, "w") as f:
        json.dump(orders, f, indent=2)
    print(f"[SUCCESS] Saved {len(orders)} orders to {filename}")


def update_all_orders_to_X(json_path: str, outlet_id: int):
    with open(json_path, "r") as f:
        orders = json.load(f)

    token = get_token_by_outlet_id(outlet_id)

    for order in orders:
        order_id = order.get("id")
        if order_id:
            update_status(order_id=str(order_id), status="X", access_token=token)
            time.sleep(0.7)  # prevent 429


if __name__ == "__main__":
    outlet_id = 1  # ganti sesuai kebutuhan
    orders = fetch_filtered_order_ids(outlet_id)
    # save_orders_to_json(orders, filename="open_orders_OL.json")
    update_all_orders_to_X("open_orders_OL.json", 1)

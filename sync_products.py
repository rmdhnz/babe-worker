import os
import sched
import threading
import time
import requests
from dotenv import load_dotenv
import schedule
from modules.crud_utility import *


load_dotenv()

api_base = os.getenv("API_BASE")


def calculate_stock(item):
    if item.get("has_variant"):
        variants = item.get("variants", [])
        stock = sum(int(v.get("stock_qty", 0)) for v in variants)
        hold = sum(int(v.get("hold_qty", 0)) for v in variants)
    else:
        stock = int(item.get("stock_qty", 0))
        hold = int(item.get("hold_qty", 0))
    return stock, hold


allowed_klasifikasi = [
    "Inventory Produk",
    "Inventory Mixer",
    "Inventory Snack",
    "Inventory Rokok",
]


def sync_products(outlet_id: int):
    token = get_token_by_outlet_id(outlet_id)
    outlet_name = get_outlet_name(outlet_id)

    page = 1
    total_synced = 0

    while True:
        result = fetch_products_page(token, page)
        if result is None:
            print(f"Retrying page {page} after 20s due to 429 error...")
            time.sleep(20)
            continue  # ulangi fetch halaman ini
        if not result.get("data"):
            break

        data = result["data"]
        meta = result.get("meta", {})
        last_page = meta.get("last_page", page)

        conn = get_db_connection()
        with conn.cursor() as cursor:
            for item in data:
                klasifikasi_id = item.get("klasifikasi_id")
                klasifikasi = item.get("klasifikasi")
                if klasifikasi not in allowed_klasifikasi:
                    continue
                olsera_id = item["id"]
                name = item["name"]
                image = item.get("photo_md")
                price = item.get("max_sell_price")
                has_variant = bool(item.get("has_variant", False))
                stock_qty = (
                    sum(v["stock_qty"] for v in item.get("variants", []))
                    if has_variant
                    else item.get("stock_qty", 0)
                )
                hold_qty = (
                    sum(v["hold_qty"] for v in item.get("variants", []))
                    if has_variant
                    else item.get("hold_qty", 0)
                )

                # Upsert product
                cursor.execute(
                    """
                    INSERT INTO products (olsera_id, outlet_id, name, klasifikasi_id, klasifikasi, image, price, has_variant, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    ON DUPLICATE KEY UPDATE name=VALUES(name), klasifikasi_id=VALUES(klasifikasi_id), klasifikasi=VALUES(klasifikasi),
                    image=VALUES(image), price=VALUES(price), has_variant=VALUES(has_variant), updated_at=NOW()
                """,
                    (
                        olsera_id,
                        outlet_id,
                        name,
                        klasifikasi_id,
                        klasifikasi,
                        image,
                        price,
                        has_variant,
                    ),
                )

                # Get product_id
                cursor.execute(
                    "SELECT id FROM products WHERE olsera_id = %s AND outlet_id = %s",
                    (olsera_id, outlet_id),
                )
                prod_row = cursor.fetchone()
                product_id = prod_row[0]

                # Upsert stock
                cursor.execute(
                    """
                    INSERT INTO product_stocks (product_id, stock_qty, hold_qty, created_at, updated_at)
                    VALUES (%s, %s, %s, NOW(), NOW())
                    ON DUPLICATE KEY UPDATE stock_qty=VALUES(stock_qty), hold_qty=VALUES(hold_qty), updated_at=NOW()
                """,
                    (product_id, stock_qty, hold_qty),
                )

                total_synced += 1
        conn.commit()
        conn.close()

        print(f"[OUTLET {outlet_name} | {outlet_id}] Page {page} selesai.")
        if page >= last_page:
            break
        page += 1

    print(f"Total produk tersinkronisasi: {total_synced}")

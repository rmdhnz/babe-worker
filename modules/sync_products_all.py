import time
from modules.crud_utility import (
    get_db_connection,
    get_token_by_outlet_id,
    get_outlet_name,
    fetch_products_page,
)

allowed_klasifikasi = [
    "Inventory Produk",
    "Inventory Mixer",
    "Inventory Snack",
    "Inventory Rokok",
]


def sync_merchandises(outlet_id: int):
    token = get_token_by_outlet_id(outlet_id)
    outlet_name = get_outlet_name(outlet_id)

    page = 1
    total_synced = 0

    while True:
        result = fetch_products_page(token, page, per_page=100)
        if result is None:
            print(f"[{outlet_name}] [RATE LIMIT] Retrying page {page} after 20s...")
            time.sleep(20)
            continue

        if not result.get("data"):
            break

        data = result["data"]
        meta = result.get("meta", {})
        last_page = meta.get("last_page", page)

        conn = get_db_connection()
        with conn.cursor() as cursor:
            for item in data:
                klasifikasi = item.get("klasifikasi")
                if klasifikasi in allowed_klasifikasi:
                    continue

                olsera_id = item["id"]
                name = item["name"]
                # Upsert ke tabel products
                cursor.execute(
                    """
                    INSERT INTO merchandises (olsera_id, outlet_id, name, koin, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                    ON DUPLICATE KEY UPDATE 
                        name = VALUES(name),
                        koin = VALUES(koin),
                        updated_at = NOW()
                    """,
                    (
                        olsera_id,
                        outlet_id,
                        name,
                        0,  # Koin default 0 untuk merchandise
                    ),
                )
                total_synced += 1

        conn.commit()
        conn.close()

        print(f"PRODUK | [{outlet_name}] Page {page} selesai.")
        if page >= last_page:
            break
        page += 1

    print(f"[{outlet_name}] Total produk tersinkronisasi: {total_synced}")


def sync_products_all(outlet_id: int):
    token = get_token_by_outlet_id(outlet_id)
    outlet_name = get_outlet_name(outlet_id)

    page = 1
    total_synced = 0

    while True:
        result = fetch_products_page(token, page, per_page=100)
        if result is None:
            print(f"[{outlet_name}] [RATE LIMIT] Retrying page {page} after 20s...")
            time.sleep(20)
            continue

        if not result.get("data"):
            break

        data = result["data"]
        meta = result.get("meta", {})
        last_page = meta.get("last_page", page)

        conn = get_db_connection()
        with conn.cursor() as cursor:
            for item in data:
                klasifikasi = item.get("klasifikasi")
                if klasifikasi not in allowed_klasifikasi:
                    continue

                olsera_id = item["id"]
                name = item["name"]
                klasifikasi_id = item.get("klasifikasi_id")
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

                # Upsert ke tabel products
                cursor.execute(
                    """
                    INSERT INTO products (olsera_id, outlet_id, name, klasifikasi_id, klasifikasi, image, price, has_variant, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    ON DUPLICATE KEY UPDATE name=VALUES(name), klasifikasi_id=VALUES(klasifikasi_id),
                    klasifikasi=VALUES(klasifikasi), image=VALUES(image), price=VALUES(price),
                    has_variant=VALUES(has_variant), updated_at=NOW()
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

                # Ambil ID dari tabel products
                cursor.execute(
                    "SELECT id FROM products WHERE olsera_id = %s AND outlet_id = %s",
                    (olsera_id, outlet_id),
                )
                row = cursor.fetchone()
                if not row:
                    continue
                product_id = row[0]

                # Upsert ke tabel stok
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

        print(f"PRODUK | [{outlet_name}] Page {page} selesai.")
        if page >= last_page:
            break
        page += 1

    print(f"[{outlet_name}] Total produk tersinkronisasi: {total_synced}")

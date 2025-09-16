import time
from modules.crud_utility import *
from modules.olsera_service import *

EXCLUDED_KEYWORDS = [
    "merch",
    "merh",
    "tukar",
    "gratis",
    "delivery",
    "layanan",
    "komplimen",
    "garansi",
]


def should_exclude(name: str):
    name = name.lower()
    return any(word in name for word in EXCLUDED_KEYWORDS)


def sync_combos(outlet_id: int):
    token = get_token_by_outlet_id(outlet_id)
    outlet_name = get_outlet_name(outlet_id)

    page = 1
    total_synced = 0

    while True:
        result = combo_with_product(token, page, per_page=100)
        if result is None:
            print(
                f"[{outlet_name}] [WARN] Retrying page {page} after 20s (429 or error)"
            )
            time.sleep(20)
            continue

        if not result.get("data"):
            break

        data = result["data"]
        meta = result.get("meta", {})
        last_page = meta.get("last_page", page)

        conn = get_db_connection()
        with conn.cursor() as cursor:
            for combo in data:
                if should_exclude(combo["name"]):
                    continue

                olsera_id = combo["id"]
                name = combo["name"]
                description = combo.get("description")
                image = combo.get("photo_md")
                price = float(combo.get("sell_price_pos") or 0)

                # Upsert combo
                cursor.execute(
                    """
                    INSERT INTO combos (olsera_id, outlet_id, name, description, image, price, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                    ON DUPLICATE KEY UPDATE
                    name=VALUES(name), description=VALUES(description), image=VALUES(image),
                    price=VALUES(price), updated_at=NOW()
                """,
                    (olsera_id, outlet_id, name, description, image, price),
                )

                # Get local combo_id
                cursor.execute(
                    "SELECT id FROM combos WHERE olsera_id = %s AND outlet_id = %s",
                    (olsera_id, outlet_id),
                )
                res = cursor.fetchone()
                if not res:
                    continue
                combo_db_id = res[0]

                # === Ambil langsung items dari response baru ===
                items = combo.get("items", [])

                if not items:
                    continue

                # Bersihkan isi lama
                cursor.execute(
                    "DELETE FROM combo_product WHERE combo_id = %s", (combo_db_id,)
                )

                pivotData = []
                for item in items:
                    olsera_prod_id = item.get("product_id")
                    qty = item.get("qty", 1)
                    if not olsera_prod_id or qty <= 0:
                        continue

                    # Ambil product_id lokal
                    cursor.execute(
                        "SELECT id FROM products WHERE olsera_id = %s AND outlet_id = %s",
                        (olsera_prod_id, outlet_id),
                    )
                    product_res = cursor.fetchone()
                    if not product_res:
                        print(
                            f"[{outlet_name}] [SKIP] Produk ID {olsera_prod_id} tidak ditemukan."
                        )
                        continue

                    local_product_id = product_res[0]
                    pivotData.append((combo_db_id, local_product_id, qty))

                # Masukkan isi baru
                if pivotData:
                    cursor.executemany(
                        "INSERT INTO combo_product (combo_id, product_id, qty) VALUES (%s, %s, %s)",
                        pivotData,
                    )

                # === Hitung dan update stock combo ===
                cursor.execute(
                    """
                    SELECT cp.product_id, cp.qty, ps.stock_qty
                    FROM combo_product cp
                    JOIN product_stocks ps ON cp.product_id = ps.product_id
                    WHERE cp.combo_id = %s
                """,
                    (combo_db_id,),
                )
                items = cursor.fetchall()

                stock_counts = []
                for product_id, qty, stock_qty in items:
                    if qty <= 0:
                        continue
                    count = stock_qty // qty
                    stock_counts.append(count)

                combo_stock = min(stock_counts) if stock_counts else 0

                cursor.execute(
                    """
                    INSERT INTO combo_stocks
                     (combo_id, stock_qty, created_at, updated_at)
                    VALUES (%s, %s, NOW(), NOW())
                    ON DUPLICATE KEY UPDATE stock_qty = VALUES(stock_qty), updated_at = NOW()
                """,
                    (combo_db_id, combo_stock),
                )

                total_synced += 1

        conn.commit()
        conn.close()
        print(f"Combo | [{outlet_name}] Page {page} selesai.")

        if page >= last_page:
            break
        page += 1

    print(f"[{outlet_name}] Total combo tersinkronisasi: {total_synced}")
    
def sync_combo_stocks(outlet_id: int):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, name FROM combos WHERE outlet_id = %s", (outlet_id,))
        all_combos = cursor.fetchall()
        total_updated = 0

        for combo_id, name in all_combos:
            if should_exclude(name):
                continue

            cursor.execute(
                """
                SELECT cp.product_id, cp.qty, ps.stock_qty
                FROM combo_product cp
                JOIN product_stocks ps ON cp.product_id = ps.product_id
                WHERE cp.combo_id = %s
                """,
                (combo_id,),
            )
            items = cursor.fetchall()

            if not items:
                continue

            stock_counts = []
            for product_id, qty, stock_qty in items:
                if qty <= 0:
                    continue
                count = stock_qty // qty
                stock_counts.append(count)

            combo_stock = min(stock_counts) if stock_counts else 0

            cursor.execute(
                """
                INSERT INTO combo_stocks (combo_id, stock_qty, created_at, updated_at)
                VALUES (%s, %s, NOW(), NOW())
                ON DUPLICATE KEY UPDATE stock_qty = VALUES(stock_qty), updated_at = NOW()
                """,
                (combo_id, combo_stock),
            )

            total_updated += 1

    print(f"Total combo stock updated: {total_updated}")


def update_combo_prices(outlet_id: int):
    token = get_token_by_outlet_id(outlet_id)
    outlet_name = get_outlet_name(outlet_id)

    print(f"Updating combo prices for outlet: {outlet_name} ({outlet_id})")

    conn = get_db_connection()
    total_updated = 0
    page = 1

    while True:
        result = fetch_combos_page(token, page, per_page=100)
        if result is None:
            print(f"Failed to fetch page {page}, retrying in 15s...")
            time.sleep(15)
            continue

        data = result.get("data", [])
        if not data:
            break

        with conn.cursor() as cursor:
            for combo in data:
                if should_exclude(combo["name"]):
                    continue
                olsera_id = combo["id"]
                price = float(combo.get("sell_price_pos") or 0)

                cursor.execute(
                    """
                    UPDATE combos
                    SET price = %s, updated_at = NOW()
                    WHERE olsera_id = %s AND outlet_id = %s
                    """,
                    (price, olsera_id, outlet_id),
                )
                total_updated += cursor.rowcount

        page += 1

    conn.commit()
    print(f"Finished updating combo prices. Total updated: {total_updated}")

import time
from modules.crud_utility import *
from modules.olsera_service import *
from modules.models_sqlalchemy import Product, Merchandise
from modules.sqlalchemy_setup import get_db_session
from datetime import datetime

allowed_klasifikasi = [
    "Inventory Produk",
    "Inventory Mixer",
    "Inventory Snack",
    "Inventory Rokok",
]


def sync_ongkir(outlet_id: int):
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
                name = item.get("name", "").lower()
                if "ongkir" not in name:
                    continue

                olsera_id = item["id"]

                # Upsert ke tabel merchandises
                cursor.execute(
                    """
                    INSERT INTO ongkirs (olsera_id, outlet_id, name, price, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                    ON DUPLICATE KEY UPDATE 
                        name = VALUES(name),
                        updated_at = NOW()
                    """,
                    (
                        olsera_id,
                        outlet_id,
                        item["name"],
                        item["sell_price_pos"],
                    ),  # koin default
                )
                total_synced += 1

        conn.commit()
        conn.close()

        print(f"ONGKIR | [{outlet_name}] Page {page} selesai.")
        if page >= last_page:
            break
        page += 1

    print(f"[{outlet_name}] Total produk ONGKIR tersinkronisasi: {total_synced}")

import time
from modules.crud_utility import get_db_connection

def copy_product_to_merchandises(outlet_id: int):
    """
    Menyalin produk (yang bisa ditukar) dari tabel products ke tabel merchandises.
    Menggunakan ORM SQLAlchemy.
    """
    with get_db_session() as session:
        total_copied = 0

        # Ambil produk yang tukar = 1
        products = (
            session.query(Product)
            .filter(Product.outlet_id == outlet_id)
            .all()
        )

        if not products:
            print(f"[Outlet {outlet_id}] Tidak ada produk untuk disalin ke merchandises.")
            return

        for p in products:
            existing = (
                session.query(Merchandise)
                .filter(Merchandise.olsera_id == p.olsera_id)
                .filter(Merchandise.outlet_id == outlet_id)
                .first()
            )

            if existing:
                # Update data yang sudah ada
                existing.name = p.name
                existing.koin = str(p.koin or 0)
                existing.tukar = True
                existing.image = p.image
                existing.product_type_id = getattr(p, "product_type_id", 1)
                existing.updated_at = datetime.utcnow()
            else:
                # Insert data baru
                new_merch = Merchandise(
                    olsera_id=p.olsera_id,
                    outlet_id=outlet_id,
                    name=p.name,
                    koin=str(p.koin or 0),
                    tukar=True,
                    product_type_id=getattr(p, "product_type_id", 1),
                    image=p.image,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(new_merch)

            total_copied += 1

        print(f"[Outlet {outlet_id}] Total produk tersalin ke merchandises: {total_copied}")

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
                image = item.get("photo_md")
                # Upsert ke tabel products
                cursor.execute(
                    """
                    INSERT INTO merchandises (olsera_id, outlet_id, name, koin,image, created_at, updated_at)
                    VALUES (%s, %s, %s, %s,%s, NOW(), NOW())
                    ON DUPLICATE KEY UPDATE 
                        name = VALUES(name),
                        koin = VALUES(koin),
                        image = VALUES(image),
                        updated_at = NOW()
                    """,
                    (
                        olsera_id,
                        outlet_id,
                        name,
                        0,  # Koin default 0 untuk merchandise
                        image,
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

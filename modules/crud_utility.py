import os
import pymysql
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy.orm import joinedload, sessionmaker
from modules.sqlalchemy_setup import engine
import json
import logging
from modules.models_sqlalchemy import Product

logger = logging.getLogger(__name__)

# Load .env file
load_dotenv()

# ENV
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT"))
DB_NAME = os.getenv("DB_DATABASE")
DB_USER = os.getenv("DB_USERNAME")
DB_PASS = os.getenv("DB_PASSWORD")


def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        port=DB_PORT,
        autocommit=True,
    )


def get_all_products_with_stock():
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    products = session.query(Product).options(joinedload(Product.stock)).limit(5).all()
    return products


def get_product_by_olsera_id(olsera_id, outlet_id: int):
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    product = (
        session.query(Product)
        .options(joinedload(Product.stock))
        .filter(Product.olsera_id == olsera_id, Product.outlet_id == outlet_id)
        .first()
    )
    return product


def get_all_tokens():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT outlet_id, token FROM token_caches")
        result = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        cursor.close()
    conn.close()
    return OutletResult(result, columns)


def get_token_by_outlet_id(outlet_id: int) -> str:
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT token FROM token_caches WHERE outlet_id = %s", (outlet_id,)
        )
        result = cursor.fetchone()
    conn.close()
    if not result:
        raise Exception(f"Token not found for outlet_id {outlet_id}")
    return result[0]


def get_outlet_name(outlet_id: int) -> str:
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT name FROM outlets WHERE id = %s", (outlet_id,))
        result = cursor.fetchone()
    conn.close()
    if not result:
        raise Exception(f"Outlet not found for id {outlet_id}")
    return result[0]


def get_all_outlets():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM outlets")
        result = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        cursor.close()
        conn.close()
        return OutletResult(result, columns)
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching outlet: {e}")
        exit(1)


def update_product_details(
    olsera_id, outlet_id, category, percentage_alcohol, alias, keywords
):
    try:
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        product = session.query(Product).filter(Product.olsera_id == olsera_id).first()
        if product:
            # Cek apakah percentage_alcohol valid
            if (
                isinstance(percentage_alcohol, str)
                and percentage_alcohol.replace(".", "", 1).isdigit()
            ):
                product.percent_alkohol = float(percentage_alcohol)
            else:
                product.percent_alkohol = 0.0
                print(f"Invalid percentage alcohol for product {olsera_id}. Set to 0.")

            product.keywords = keywords
            product.tag = category
            product.alias = alias
            session.commit()
            print(f"Product {olsera_id} updated successfully.")
        else:
            print(
                f"Product with olsera_id {olsera_id} and outlet_id {outlet_id} not found."
            )
    except Exception as e:
        print(f"Error updating product [{olsera_id}]: {e}")


def update_product_details_by_name(
    name, outlet_id, category, percentage_alcohol, alias, keywords
):
    try:
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        products = session.query(Product).filter(Product.name == name).all()
        if products:
            for product in products:
                # Cek apakah percentage_alcohol valid
                if (
                    isinstance(percentage_alcohol, str)
                    and percentage_alcohol.replace(".", "", 1).isdigit()
                ):
                    product.percent_alkohol = float(percentage_alcohol)
                else:
                    product.percent_alkohol = 0.0
                    print(f"Invalid percentage alcohol for product {name}. Set to 0.")

                product.keywords = keywords
                product.tag = category
                product.alias = alias
                session.commit()
                print(f"Product {name} updated successfully.")
        else:
            print(f"Product with name {name} and outlet_id {outlet_id} not found.")
    except Exception as e:
        print(f"Error updating product [{name}]: {e}")


def get_product_variants_by_olsera_id(olsera_id, outlet_id):

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT variants FROM products WHERE olsera_id = %s AND outlet_id = %s",
            (olsera_id, outlet_id),
        )
        row = cursor.fetchone()
    conn.close()
    if not row or not row[0]:
        return []
    try:
        variants = json.loads(row[0])
        return variants if isinstance(variants, list) else []
    except Exception as e:
        print(f"[ERROR] Gagal decode variants untuk olsera_id={olsera_id}: {e}")
        return []


class OutletResult:
    def __init__(self, result, columns):
        self.result = result
        self.columns = columns

    def json(self):
        return [dict(zip(self.columns, row)) for row in self.result]

    def panda(self):
        return pd.DataFrame(self.result, columns=self.columns)

from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Float,
    DECIMAL,
    Boolean,
    JSON,
    DateTime,
    ForeignKey,
    Table,
    Time,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from .sqlalchemy_setup import Base

combo_product = Table(
    "combo_product",
    Base.metadata,
    Column("combo_id", ForeignKey("combos.id"), primary_key=True),
    Column("product_id", ForeignKey("products.id"), primary_key=True),
    Column("qty", Integer, nullable=False),
    Column("created_at", DateTime, default=datetime.utcnow),
    Column("updated_at", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow),
)


class Combo(Base):
    __tablename__ = "combos"

    id = Column(Integer, primary_key=True)
    olsera_id = Column(Integer)
    outlet_id = Column(Integer)
    name = Column(String(255))
    description = Column(String(255))
    image = Column(String(255))
    price = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    products = relationship("Product", secondary=combo_product, back_populates="combos")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    olsera_id = Column(Integer)
    outlet_id = Column(Integer)
    name = Column(String(255))
    klasifikasi_id = Column(BigInteger)
    klasifikasi = Column(String(255))
    image = Column(String(255))
    description = Column(Text)
    tag = Column(String(255))
    alias = Column(String(255))
    percent_alkohol = Column(DECIMAL(5, 2))
    keywords = Column(String(255))
    price = Column(DECIMAL(10, 2))
    koin = Column(BigInteger)
    has_variant = Column(Boolean)
    variants = Column(JSON)
    total_dibeli = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relasionships
    stock = relationship("ProductStock", uselist=False, back_populates="product")
    combos = relationship("Combo", secondary=combo_product, back_populates="products")


class ProductStock(Base):
    __tablename__ = "product_stocks"

    product_id = Column(Integer, ForeignKey("products.id"), primary_key=True)
    stock_qty = Column(Integer)
    product = relationship("Product", back_populates="stock")


class Cart(Base):
    __tablename__ = "carts"

    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    outlet_id = Column(BigInteger, ForeignKey("outlets.id"), nullable=False)

    product_id = Column(String(255))
    prodvar_id = Column(String(255))
    product_type_id = Column(BigInteger, nullable=False)

    name = Column(String(255))
    combo_id = Column(String(255))
    bundle_id = Column(BigInteger)

    klasifikasi_id = Column(String(255))
    klasifikasi = Column(String(255))
    variant_id = Column(String(255))
    variant = Column(String(255))

    harga_satuan = Column(BigInteger)
    discount = Column(DECIMAL(10, 3), default=0.000)

    quantity = Column(Integer)
    harga_total = Column(BigInteger)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relationships
    outlet = relationship("Outlet", back_populates="carts")


class Outlet(Base):
    __tablename__ = "outlets"

    id = Column(BigInteger, primary_key=True)
    name = Column(String(255), nullable=False)

    jam_buka = Column(Time)  # tipe time
    jam_tutup = Column(Time)  # tipe time

    latitude = Column(DECIMAL(10, 8))  # akurasi tinggi untuk koordinat
    longitude = Column(DECIMAL(11, 8))  # sesuai dengan struktur tabel

    address = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relasi ke cart
    carts = relationship("Cart", back_populates="outlet")

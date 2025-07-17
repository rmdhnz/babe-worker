from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Table
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

    combos = relationship("Combo", secondary=combo_product, back_populates="products")


class ProductStock(Base):
    __tablename__ = "product_stocks"

    product_id = Column(Integer, ForeignKey("products.id"), primary_key=True)
    stock_qty = Column(Integer)

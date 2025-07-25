from modules.models_sqlalchemy import Cart
from sqlalchemy.orm import sessionmaker
from modules.sqlalchemy_setup import SessionLocal, engine

SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

carts = session.query(Cart).filter(Cart.user_id == 18, Cart.outlet_id == 1).all()

for cart in carts:
    print(cart.name)

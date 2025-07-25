from modules.crud_utility import get_all_products_with_stock

products = get_all_products_with_stock()


for product in products:
    print(f"ID: {product.id}, Name: {product.name}, Stock: {product.stock.stock_qty}")
    print(f"Variants : {product.variants}")

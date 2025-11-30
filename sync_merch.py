from modules.sync_products_all import sync_merchandises,copy_product_to_merchandises
from modules.crud_utility import get_all_outlets

if __name__ == "__main__":
    # outlets = get_all_outlets().json()
    print(f"Syncing merchandises for outlet: {1} (ID: {1})")
    sync_merchandises(1)
    copy_product_to_merchandises(1)
    print(f"Finished syncing merchandises for outlet: {1}")

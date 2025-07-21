from modules.sync_products_all import sync_merchandises
from modules.crud_utility import get_all_outlets

if __name__ == "__main__":
    outlets = get_all_outlets().json()
    for outlet in outlets:
        print(f"Syncing merchandises for outlet: {outlet['name']} (ID: {outlet['id']})")
        sync_merchandises(outlet["id"])
        print(f"Finished syncing merchandises for outlet: {outlet['name']}")

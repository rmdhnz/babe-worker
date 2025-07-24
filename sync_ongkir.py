from modules.sync_products_all import sync_ongkir
from modules.crud_utility import get_all_outlets

if __name__ == "__main__":
    outlets = get_all_outlets().json()
    for outlet in outlets:
        print(f"Syncing Ongkir for outlet: {outlet['name']} (ID: {outlet['id']})")
        sync_ongkir(outlet["id"])
        print(f"Finished syncing Ongkir for outlet: {outlet['name']}")

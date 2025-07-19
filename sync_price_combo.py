from modules.crud_utility import get_all_outlets
from modules.combo_utility import update_combo_prices

if __name__ == "__main__":
    all_outlets = get_all_outlets().json()
    for outlet in all_outlets:
        update_combo_prices(outlet_id=outlet["id"])
        print("Update harga outlet {}".format(outlet["name"]))
    print(("ANJAY SELESAI..."))

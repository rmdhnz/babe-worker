from modules.crud_utility import get_all_outlets
from modules.combo_utility import update_combo_prices

if __name__ == "__main__":
    all_outlets = get_all_outlets().json()
    update_combo_prices(outlet_id=5)
    exit()
    for outlet in all_outlets:
        print("Update harga outlet {}".format(outlet["name"]))
    print(("ANJAY SELESAI..."))

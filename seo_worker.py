# main.py

import json
from modules import crud_utility


def import_product_details(file_path):
    with open(file_path, "r") as file:
        data = json.load(file)

    for item in data:
        olsera_id = item.get("id")
        name = item.get("name")
        category = item.get("kategori")
        percentage_alcohol = item.get("persentase_alkohol (%)")
        keywords = item.get("kata_kunci (pisahkan dengan koma)")
        alias = item.get("alias")
        crud_utility.update_product_details_by_name(
            name, 1, category, percentage_alcohol, alias, keywords
        )


if __name__ == "__main__":
    file_path = "./data/output-solo.json"  # Replace with your JSON file path
    import_product_details(file_path)

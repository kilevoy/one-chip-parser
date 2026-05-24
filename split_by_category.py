"""Перегруппировать уже сохранённый products.json в раздельные таблицы по корневой категории.

Использование:
    python split_by_category.py [папка_с_products.json]

Создаёт в той же папке:
    products.xlsx               — листы по корням + лист «Все»
    products_<категория>.csv    — отдельный CSV на каждую корневую категорию
"""
from __future__ import annotations

import json
import os
import sys

import parser as P


def main() -> None:
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    json_path = os.path.join(out_dir, "products.json")
    if not os.path.isfile(json_path):
        print(f"Не найден файл: {json_path}")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"Прочитано товаров: {len(data)}")

    products: list[P.Product] = []
    for d in data:
        vars_ = [P.Variation(**v) for v in (d.get("variations") or [])]
        products.append(
            P.Product(
                url=d.get("url", ""),
                discovered_in=d.get("discovered_in", ""),
                discovered_root=d.get("discovered_root", ""),
                category_path=d.get("category_path", ""),
                name=d.get("name", ""),
                image=d.get("image", ""),
                description_text=d.get("description_text", ""),
                description_html=d.get("description_html", ""),
                price=d.get("price", ""),
                price_text=d.get("price_text", ""),
                price_currency=d.get("price_currency", "RUB"),
                sku=d.get("sku", ""),
                in_stock=d.get("in_stock", True),
                brand=d.get("brand", ""),
                variations=vars_,
                features=d.get("features", {}) or {},
            )
        )

    products.sort(key=lambda p: (p.discovered_root, p.category_path, p.name))
    xlsx_path = P.save_xlsx(products, os.path.join(out_dir, "products.xlsx"))
    print(f"XLSX: {xlsx_path}")
    csv_paths = P.save_csv_by_root(products, out_dir)
    for c in csv_paths:
        print(f"CSV : {c}")


if __name__ == "__main__":
    main()

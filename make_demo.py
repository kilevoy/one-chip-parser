"""Сборка демо-таблицы для отклика заказчику.

Берёт небольшой репрезентативный набор товаров из обеих категорий и
формирует demo.xlsx (с листами по корням) + JSON.

Запуск:
    python make_demo.py
"""
from __future__ import annotations

import json
import os
import sys
import time

import parser as P


# подбор репрезентативных товаров: с описанием, ценой, картинкой,
# желательно с вариациями и характеристиками.
DEMO = {
    "Загрузчики": [
        # Сам ключ M&D
        ("https://one-chip.ru/klyuch-m-d-flasher/",
         "https://one-chip.ru/category/chip-tyuning/zagruzchiki/zagruzchik-m-d-flasher/"),
        # Лицензия 001 — пример «модуля»
        ("https://one-chip.ru/litsenziya-001-dacia-lada-nissan-renault-ecu-mcu-s167-bench-obdii/",
         "https://one-chip.ru/category/chip-tyuning/zagruzchiki/zagruzchik-m-d-flasher/moduli-m-d-flasher/"),
        # Адаптер DENSO
        ("https://one-chip.ru/adapter-denso-mbus-uart-dlya-md-flasher/",
         "https://one-chip.ru/category/chip-tyuning/zagruzchiki/zagruzchik-m-d-flasher/kabeli-dlya-m-d-flasher/"),
        # CombiLoader
        ("https://one-chip.ru/combiloader/",
         "https://one-chip.ru/category/chip-tyuning/zagruzchiki/combiloader/"),
        # Модуль Combiloader M74
        ("https://one-chip.ru/modul-combiloader-m74-vaz-011-019/",
         "https://one-chip.ru/category/chip-tyuning/zagruzchiki/combiloader/"),
        # PCMflash
        ("https://one-chip.ru/pcmflash/",
         "https://one-chip.ru/category/chip-tyuning/zagruzchiki/pcmflash/"),
        # OBD-II
        ("https://one-chip.ru/obd-ii/",
         "https://one-chip.ru/category/chip-tyuning/zagruzchiki/combiloader/"),
    ],
    "Редакторы": [
        # ChipTuningPRO — у него вариации
        ("https://one-chip.ru/118/",
         "https://one-chip.ru/category/chip-tyuning/redaktory/chiptuningpro/"),
        # BitEdit
        ("https://one-chip.ru/bitedit/",
         "https://one-chip.ru/category/chip-tyuning/redaktory/bitedit/"),
        # MasterEditPro
        ("https://one-chip.ru/master-edit-pro/",
         "https://one-chip.ru/category/chip-tyuning/redaktory/mastereditpro-v5/"),
        # ECULite
        ("https://one-chip.ru/eculite/",
         "https://one-chip.ru/category/chip-tyuning/redaktory/eculite/"),
        # DTС-Edit
        ("https://one-chip.ru/redaktor-dts-edit/",
         "https://one-chip.ru/category/chip-tyuning/redaktory/dts-edit/"),
        # Базовый комплект ChipTuningPRO
        ("https://one-chip.ru/119/",
         "https://one-chip.ru/category/chip-tyuning/redaktory/chiptuningpro/"),
        # Модуль ChipTuningPro M74
        ("https://one-chip.ru/modul-chiptuningpro-vaz-m74-080/",
         "https://one-chip.ru/category/chip-tyuning/redaktory/chiptuningpro/"),
    ],
}


def main() -> None:
    P.use_system_proxy(True)  # вдруг сайт открыт через VPN
    products: list[P.Product] = []
    for root_name, items in DEMO.items():
        print(f"\n=== {root_name} ===")
        for url, cat in items:
            try:
                p = P.parse_product(url, discovered_in=cat, discovered_root=root_name)
            except Exception as e:  # noqa: BLE001
                print(f"  FAIL {url}: {e}")
                continue
            if not p:
                print(f"  пусто {url}")
                continue
            products.append(p)
            print(f"  OK  {p.name[:80]}  | цена: {p.price or p.price_text}")
            time.sleep(0.2)

    if not products:
        print("Не удалось ничего загрузить — проверьте VPN/доступ к сайту.")
        sys.exit(1)

    out_dir = "."
    products.sort(key=lambda p: (p.discovered_root, p.name))
    P.save_json(products, os.path.join(out_dir, "demo.json"))
    P.save_xlsx(products, os.path.join(out_dir, "demo.xlsx"))
    P.save_csv_by_root(products, out_dir)
    # переименуем созданные демо-csv
    for fname in os.listdir(out_dir):
        if fname.startswith("products_") and fname.endswith(".csv"):
            new = fname.replace("products_", "demo_")
            try:
                os.replace(os.path.join(out_dir, fname), os.path.join(out_dir, new))
                print(f"  -> {new}")
            except Exception:  # noqa: BLE001
                pass

    print(f"\nГотово. Товаров в демо: {len(products)}")
    print("  demo.xlsx, demo.json, demo_*.csv")


if __name__ == "__main__":
    main()

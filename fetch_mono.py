#!/usr/bin/env python3
"""
fetch_mono.py — тягне транзакції з Монобанку і записує в data.json
Запускається автоматично через GitHub Actions кожні 4 години.
"""

import os
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ── Конфіг ────────────────────────────────────────────────────
MONO_TOKEN   = os.environ["MONO_TOKEN"]          # з GitHub Secrets
MONO_ACCOUNT = "24GD4rlWOKiFu_-x29DrRQ"         # чорна кредитна картка ****6687
DATA_FILE    = "data.json"

# Категорії Моно (mcc) → наші категорії
MCC_MAP = {
    # Продукти
    5411: "Продукти", 5412: "Продукти", 5422: "Продукти",
    5441: "Продукти", 5451: "Продукти", 5462: "Продукти",
    5499: "Продукти", 5300: "Продукти",
    # Кафе / ресторан
    5812: "Кафе / ресторан", 5813: "Кафе / ресторан",
    5814: "Кафе / ресторан", 5811: "Кафе / ресторан",
    # Таксі
    4121: "Таксі", 4111: "Таксі", 7512: "Таксі",
    # Одяг
    5600: "Одяг", 5611: "Одяг", 5621: "Одяг",
    5631: "Одяг", 5641: "Одяг", 5651: "Одяг",
    5661: "Одяг", 5691: "Одяг", 5699: "Одяг",
    # Аптека / медицина
    5912: "Аптека / медицина", 8011: "Аптека / медицина",
    8021: "Аптека / медицина", 8049: "Аптека / медицина",
    # Розваги
    7832: "Розваги", 7922: "Розваги", 7929: "Розваги",
    7991: "Розваги", 7993: "Розваги", 7996: "Розваги",
    # Зв'язок
    4812: "Зв'язок / інтернет", 4813: "Зв'язок / інтернет",
    4814: "Зв'язок / інтернет",
    # Комуналка
    4900: "Оренда / комуналка", 4910: "Оренда / комуналка",
    4911: "Оренда / комуналка", 4941: "Оренда / комуналка",
}

def mono_get(path):
    req = urllib.request.Request(
        f"https://api.monobank.ua{path}",
        headers={"X-Token": MONO_TOKEN}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def mcc_to_category(mcc):
    return MCC_MAP.get(mcc, "Інше")

def kopecks(amount_kopecks):
    """Монобанк повертає суми в копійках → переводимо в гривні"""
    return round(abs(amount_kopecks) / 100, 2)

def main():
    print(f"[{datetime.now()}] Починаємо синхронізацію з Монобанком...")

    data = load_data()
    processed_ids = set(data.get("mono_processed_ids", []))

    # Беремо виписку за останні 30 днів
    now_ts   = int(time.time())
    from_ts  = now_ts - 30 * 24 * 3600

    print(f"Запит виписки за останні 30 днів...")
    try:
        statements = mono_get(f"/personal/statement/{MONO_ACCOUNT}/{from_ts}/{now_ts}")
    except urllib.error.HTTPError as e:
        print(f"Помилка API: {e.code} {e.reason}")
        raise

    print(f"Отримано {len(statements)} транзакцій")

    new_count = 0
    for tx in statements:
        tx_id = tx["id"]
        if tx_id in processed_ids:
            continue  # вже записано раніше

        amount_kopecks = tx["amount"]          # від'ємне = витрата, додатнє = надходження
        amount_uah     = kopecks(amount_kopecks)
        description    = tx.get("description", "")
        mcc            = tx.get("mcc", 0)
        ts             = tx["time"]            # unix timestamp

        if amount_kopecks < 0:
            # Витрата з кредитної картки
            entry_type = "expense"
            category   = mcc_to_category(mcc)
        else:
            # Надходження (поповнення картки — тобто погашення кредиту)
            entry_type = "income"
            category   = "Переказ"

        entry = {
            "type":     entry_type,
            "bank":     "mono",
            "amount":   amount_uah,
            "category": category,
            "comment":  description,
            "ts":       ts * 1000,             # мілісекунди для JS
            "mono_id":  tx_id                  # щоб не дублювати
        }

        data["log"].append(entry)
        processed_ids.add(tx_id)
        new_count += 1
        print(f"  + {entry_type:7} {amount_uah:>10} грн | {category:25} | {description[:40]}")

    # Зберігаємо оброблені ID (останні 2000 щоб файл не ріс нескінченно)
    data["mono_processed_ids"] = list(processed_ids)[-2000:]
    data["mono_last_sync"]     = datetime.now(timezone.utc).isoformat()

    save_data(data)
    print(f"\n✓ Додано {new_count} нових транзакцій. Sync завершено.")

if __name__ == "__main__":
    main()

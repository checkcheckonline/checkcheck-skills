#!/usr/bin/env python3
"""Валидация файла импорта товаров ЧекЧек перед загрузкой.

Повторяет правила импортера: детект колонок по ключевикам, XOR баллы/процент,
числа с запятой как разделителем, построчные ошибки. Ошибки (файл или строки
не импортируются / импортируются не так, как задумано) и предупреждения
(скорее всего не то, что хотели) печатаются с номерами строк.

Использование:
  python validate_import.py file.tsv        # таб-разделитель
  python validate_import.py file.csv        # ';' — как пишет Excel
Код возврата: 0 — ошибок нет, 1 — есть ошибки.
"""
import csv
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

# Ключевые слова колонок: подстрока в заголовке, без учёта регистра.
KEYWORDS = {
    "brand": "бренд",
    "product": "наименование",
    "mask": "маска",
    "sku": "артикул",
    "fixed_points": "фиксированное количество баллов",
    "fixed_percent": "фиксированный процент",
    "min_price": "мин. цена",
    "max_price": "макс. цена",
}
PAYOUT_STEP = Decimal("0.01")  # значения, квантующиеся в 0, импортер считает нулём


def parse_decimal(cell: str):
    """Число из ячейки: запятая -> точка, пробелы вон."""
    s = (cell or "").replace(",", ".").replace(" ", "").replace(" ", "")
    if not s:
        return None
    return Decimal(s)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    path = Path(sys.argv[1])
    delim = ";" if path.suffix.lower() == ".csv" else "\t"

    errors, warnings = [], []

    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f, delimiter=delim))
    if not rows:
        sys.exit("Пустой файл")

    headers = rows[0]
    lower = [str(h or "").lower() for h in headers]

    # --- заголовок ---
    cols, claimed = {}, set()
    for field, kw in KEYWORDS.items():
        for i, h in enumerate(lower):
            if kw in h and i not in claimed:
                cols[field] = i
                claimed.add(i)
                break
    for i, h in enumerate(lower):
        hits = [kw for kw in KEYWORDS.values() if kw in h]
        if len(hits) > 1:
            warnings.append(f"заголовок «{headers[i]}» содержит несколько "
                            f"ключевиков {hits} — колонка может определиться не так")

    if "brand" not in cols:
        errors.append("нет колонки бренда (заголовок должен содержать «бренд») — файл не импортируется")
    if "product" not in cols and "sku" not in cols:
        errors.append("нет ни «наименование», ни «артикул» — файл не импортируется")
    if "mask" not in cols:
        warnings.append("нет колонки «маска» — маски по позициям чека загружены не будут")

    has_points_col = "fixed_points" in cols
    has_percent_col = "fixed_percent" in cols
    if has_points_col or has_percent_col:
        warnings.append("в файле есть колонка баллов/процента: ПУСТАЯ ячейка в ней "
                        "означает «снять автоакцию с товара», а не «оставить как есть»")

    # --- строки ---
    def cell(row, field):
        i = cols.get(field)
        return row[i].strip() if i is not None and i < len(row) else ""

    all_masks = {}  # casefold -> первый номер строки
    empty_payout_rows = 0
    for n, row in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in row):
            continue  # совсем пустые строки пропускаем

        brand_variants = [b.strip() for b in cell(row, "brand").splitlines() if b.strip()]
        if not brand_variants:
            errors.append(f"строка {n}: пустой бренд")
        if not cell(row, "product") and not cell(row, "sku"):
            errors.append(f"строка {n}: пусто и наименование, и артикул")

        # маски
        raw = cell(row, "mask")
        masks = [m.strip() for m in raw.splitlines() if m.strip()]
        variants_cf = [b.casefold() for b in brand_variants]
        for m in masks:
            if "," in m:
                warnings.append(f"строка {n}: маска «{m}» содержит запятую — "
                                f"возможно, маски не разбиты по строкам")
            if variants_cf and not any(v in m.casefold() for v in variants_cf):
                warnings.append(f"строка {n}: маска «{m}» не содержит бренд "
                                f"({'/'.join(brand_variants)}) — может матчить чужие товары")
            key = m.casefold()
            if key in all_masks:
                warnings.append(f"строка {n}: маска «{m}» дублирует строку {all_masks[key]} "
                                f"— один и тот же матч на два товара")
            else:
                all_masks[key] = n

        # баллы XOR процент
        try:
            points = parse_decimal(cell(row, "fixed_points")) if has_points_col else None
            percent = parse_decimal(cell(row, "fixed_percent")) if has_percent_col else None
        except InvalidOperation:
            errors.append(f"строка {n}: нечисловое значение в баллах/проценте")
            continue
        if points is not None and percent is not None:
            errors.append(f"строка {n}: заполнены и баллы, и процент — можно только одно")
        for label, v in (("баллы", points), ("процент", percent)):
            if v is None:
                continue
            if v < 0:
                errors.append(f"строка {n}: отрицательное значение ({label}: {v})")
            elif v > 0 and v.quantize(PAYOUT_STEP) == 0:
                errors.append(f"строка {n}: {label} {v} квантуется в 0 — строка станет «без баллов»")
        if (has_points_col or has_percent_col) \
                and points in (None, Decimal(0)) and percent in (None, Decimal(0)):
            empty_payout_rows += 1
            warnings.append(f"строка {n}: баллы/процент пустые или 0 — автоакция товара будет снята")

        # цены
        try:
            mn = parse_decimal(cell(row, "min_price"))
            mx = parse_decimal(cell(row, "max_price"))
            if mn is not None and mx is not None and mn > mx:
                warnings.append(f"строка {n}: мин. цена {mn} больше макс. {mx}")
        except InvalidOperation:
            errors.append(f"строка {n}: нечисловая цена")

    if empty_payout_rows and empty_payout_rows == len(rows) - 1:
        warnings.append("баллы/процент пустые ВО ВСЕХ строках: если файл нужен только "
                        "для масок/каталога — удалите колонку баллов и процента целиком, "
                        "тогда автоакции не будут тронуты")

    # --- отчёт ---
    for e in errors:
        print(f"ОШИБКА: {e}")
    for w in warnings:
        print(f"предупреждение: {w}")
    print(f"\nИтог: {len(rows) - 1} строк, {len(all_masks)} уникальных масок, "
          f"{len(errors)} ошибок, {len(warnings)} предупреждений")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()

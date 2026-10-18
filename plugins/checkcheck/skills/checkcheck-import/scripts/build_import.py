#!/usr/bin/env python3
"""Сборка файла импорта товаров ЧекЧек из исходника поставщика.

Берёт xlsx/csv/tsv, находит колонки по ключевым словам (как импортер ЧекЧека),
приводит колонку масок к формату импорта:
  * маски разделяются переносами строк внутри ячейки (запятые -> переносы);
  * если маска не содержит ни одного варианта написания бренда, бренд
    дописывается в начало; повтор слов на стыке убирается
    (Витамикс Марин + МАРИН ОМЕГА-3 -> Витамикс Марин ОМЕГА-3).
    Маска, в которой бренд уже есть (в любом месте, любым вариантом
    написания), не трогается;
  * дубликаты масок схлопываются без учёта регистра (матчинг ЧекЧека
    регистронезависимый), остаётся первый вариант написания.
Ячейка бренда может быть многострочной (канон + альтернативные написания) —
строки сохраняются как есть, чистятся только пустые и дубли.
Остальные колонки сохраняются. Результат — .tsv (таб, UTF-8).

Использование:
  python build_import.py input.xlsx -o output.tsv [--sheet ИмяЛиста]
  python build_import.py input.csv  -o output.tsv     # .csv читается с ';'
"""
import argparse
import csv
import re
import sys
from pathlib import Path

BRAND_KEY = "бренд"
MASK_KEY = "маска"
PRODUCT_KEY = "наименование"
SKU_KEY = "артикул"


def find_col(headers, keyword):
    """Первый заголовок, содержащий подстроку-ключевик (как в импортере)."""
    for i, h in enumerate(headers):
        if keyword in str(h or "").lower():
            return i
    return None


def parse_variants(cell: str) -> list[str]:
    """Строки ячейки бренда: strip, без пустых, без дублей (регистр не важен)."""
    seen = {}
    for line in (cell or "").splitlines():
        line = " ".join(line.split())
        if line and line.casefold() not in seen:
            seen[line.casefold()] = line
    return list(seen.values())


def merge_brand_mask(brand: str, mask: str) -> str:
    """Приклеивает бренд к маске, убирая повтор слов на стыке."""
    bw = brand.split()
    mw = mask.split()
    best = 0
    for k in range(1, min(len(bw), len(mw)) + 1):
        if [w.casefold() for w in bw[-k:]] == [w.casefold() for w in mw[:k]]:
            best = k
    return " ".join(bw + mw[best:])


def transform_masks(brand_variants: list[str], cell: str) -> str:
    """Ячейка масок -> маски по одной на строку, с брендом, без дублей."""
    variants_cf = [v.casefold() for v in brand_variants]
    seen = {}
    for part in re.split(r"[\n,]", cell or ""):
        part = " ".join(part.split())
        if not part:
            continue
        if any(v in part.casefold() for v in variants_cf):
            merged = part  # бренд уже есть в маске — не трогаем
        elif brand_variants:
            merged = merge_brand_mask(brand_variants[0], part)
        else:
            merged = part
        key = merged.casefold()
        if key not in seen:
            seen[key] = merged
    return "\n".join(seen.values())


def read_rows(path: Path, sheet: str | None):
    ext = path.suffix.lower()
    if ext in (".xlsx", ".xlsm", ".xltx"):
        import openpyxl

        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb[sheet] if sheet else wb.active
        for row in ws.iter_rows(values_only=True):
            yield ["" if v is None else str(v) for v in row]
    else:
        delim = ";" if ext == ".csv" else "\t"
        with open(path, newline="", encoding="utf-8-sig") as f:
            yield from csv.reader(f, delimiter=delim)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True,
                    help="итоговый .tsv для импорта")
    ap.add_argument("--sheet", default=None, help="имя листа xlsx (по умолчанию активный)")
    ap.add_argument("--drop-column", action="append", default=[],
                    help="удалить колонку по подстроке заголовка (можно несколько раз)")
    args = ap.parse_args()

    rows = list(read_rows(args.input, args.sheet))
    if not rows:
        sys.exit("Пустой файл")
    headers = rows[0]

    drop = set()
    for key in args.drop_column:
        i = find_col(headers, key.lower())
        if i is None:
            sys.exit(f"--drop-column: колонка «{key}» не найдена")
        drop.add(i)

    brand_i = find_col(headers, BRAND_KEY)
    mask_i = find_col(headers, MASK_KEY)
    if brand_i is None:
        sys.exit("Не найдена колонка бренда (заголовок должен содержать «бренд»)")
    if mask_i is None:
        sys.exit("Не найдена колонка масок (заголовок должен содержать «маска»)")
    if find_col(headers, PRODUCT_KEY) is None and find_col(headers, SKU_KEY) is None:
        print("ВНИМАНИЕ: нет ни «наименование», ни «артикул» — импортер требует "
              "хотя бы одну из этих колонок", file=sys.stderr)

    out_rows = [[h for i, h in enumerate(headers) if i not in drop]]
    n_masks = 0
    for row in rows[1:]:
        row = list(row) + [""] * (len(headers) - len(row))
        variants = parse_variants(row[brand_i])
        row[brand_i] = "\n".join(variants)
        row[mask_i] = transform_masks(variants, row[mask_i])
        n_masks += len(row[mask_i].splitlines())
        row = [c.strip() if isinstance(c, str) else c for c in row]
        out_rows.append([c for i, c in enumerate(row) if i not in drop])

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_MINIMAL,
                       lineterminator="\n")
        w.writerows(out_rows)
    print(f"OK: {len(out_rows) - 1} строк, {n_masks} масок -> {args.output}")


if __name__ == "__main__":
    main()

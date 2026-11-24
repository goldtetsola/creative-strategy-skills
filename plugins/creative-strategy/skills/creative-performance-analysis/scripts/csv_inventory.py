#!/usr/bin/env python3
"""Inspect CSV files without changing them or calculating performance metrics.

Usage: python3 csv_inventory.py export.csv [other.csv ...]
Overrides: --delimiter semicolon --header-row 3 --encoding utf-16

JSON is written to stdout. Exit 1 means at least one file could not be inspected;
other file results remain available. Headers/delimiters are suggestions unless
specified. Row numbers are one-based CSV records, not physical text lines.
Only exact ISO YYYY-MM-DD cells contribute to observed date ranges. No numeric
conversion, summing, formula execution, row removal or source writes occur.
"""

import argparse
from collections import Counter
import csv
from datetime import date
from itertools import islice
import json
from pathlib import Path
import re


DELIMITERS = {"comma": ",", "tab": "\t", "semicolon": ";", "pipe": "|"}
HEADER_LABELS = {
    "date", "day", "reporting starts", "reporting ends", "period start", "period end",
    "account", "account id", "campaign", "campaign name", "ad set", "ad name", "ad id",
    "spend", "amount spent", "orders", "new orders", "revenue", "new revenue",
    "impressions", "reach", "clicks", "link clicks", "sales", "net sales", "sessions",
    "customers", "new customers", "roas", "cac", "aov", "currency", "market",
}


def label(value):
    return " ".join(value.strip().lower().replace("_", " ").split())


def choose_layout(path, encoding, delimiter=None, header_row=None):
    # ponytail: one table, first 25 records; use explicit layout for longer preambles.
    candidates = []
    for sep in [delimiter] if delimiter else DELIMITERS.values():
        rows = []
        with path.open(newline="", encoding=encoding) as stream:
            try:
                for row in islice(csv.reader(stream, delimiter=sep, strict=True), header_row or 25):
                    rows.append(row)
            except csv.Error:
                pass  # Keep a readable header; the full scan will report malformed data.
        for index, row in enumerate(rows):
            if header_row and index + 1 != header_row:
                continue
            cells = [label(cell) for cell in row if cell.strip()]
            if not cells:
                continue
            hits = sum(cell in HEADER_LABELS for cell in cells)
            text_cells = sum(not re.fullmatch(r"[\d\s.,/:%+()£€$-]+", cell) for cell in cells)
            if not header_row and not text_cells:
                continue
            matches = sum(len(other) == len(row) for other in rows[index + 1:])
            score = (hits, text_cells / len(cells), len(row), matches, -index)
            candidates.append((score, sep, index + 1, row))
    if not candidates:
        raise ValueError("No readable header found; verify encoding, delimiter and --header-row.")
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, sep, number, headers = candidates[0]
    return sep, number, headers


def inspect_csv(path, *, encoding="utf-8-sig", delimiter=None, header_row=None):
    path = Path(path)
    sep, number, headers = choose_layout(path, encoding, delimiter, header_row)
    columns = [{"position": i + 1, "name": name, "blank_cells": 0,
                "absent_cells": 0, "nonblank_cells": 0, "iso_date_cells": 0,
                "iso_date_min": None, "iso_date_max": None} for i, name in enumerate(headers)]
    widths = Counter()
    flags = {name: {"count": 0, "first_csv_records": []}
             for name in ("ragged_rows", "repeated_headers", "possible_totals")}

    def flag(kind, record):
        flags[kind]["count"] += 1
        if len(flags[kind]["first_csv_records"]) < 5:
            flags[kind]["first_csv_records"].append(record)

    names = [label(name) for name in headers]
    row_count = blank_rows = 0
    with path.open(newline="", encoding=encoding) as stream:
        for record, row in enumerate(csv.reader(stream, delimiter=sep, strict=True), 1):
            if record <= number:
                continue
            if not any(cell.strip() for cell in row):
                blank_rows += 1
                continue
            row_count += 1
            widths[len(row)] += 1
            if len(row) != len(headers):
                flag("ragged_rows", record)
            if [label(cell) for cell in row] == names:
                flag("repeated_headers", record)
            if any(label(cell) in {"total", "subtotal", "grand total"} for cell in row[:3]):
                flag("possible_totals", record)
            for i, column in enumerate(columns):
                if i >= len(row):
                    column["absent_cells"] += 1
                    continue
                value = row[i].strip()
                if not value:
                    column["blank_cells"] += 1
                    continue
                column["nonblank_cells"] += 1
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    try:
                        date.fromisoformat(value)
                    except ValueError:
                        continue
                    column["iso_date_cells"] += 1
                    column["iso_date_min"] = min(column["iso_date_min"] or value, value)
                    column["iso_date_max"] = max(column["iso_date_max"] or value, value)

    duplicates = [{"name": name, "positions": [i + 1 for i, value in enumerate(names) if value == name]}
                  for name, count in Counter(names).items() if name and count > 1]
    return {
        "path": str(path.resolve()), "status": "inspected", "encoding": encoding,
        "delimiter": sep, "delimiter_selection": "explicit" if delimiter else "suggested",
        "header_csv_record": number, "header_selection": "explicit" if header_row else "suggested",
        "records_before_header": number - 1, "nonblank_rows_after_header": row_count,
        "blank_rows_after_header": blank_rows, "column_count": len(headers), "columns": columns,
        "row_width_counts": dict(sorted(widths.items())), "duplicate_headers": duplicates,
        "blank_header_positions": [i + 1 for i, name in enumerate(names) if not name],
        **flags,
        "scope": "Unfiltered file structure. Verify the header and flagged records before mapping or totals; dates are observed cells, not certified coverage."
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--delimiter", choices=DELIMITERS)
    parser.add_argument("--header-row", type=int, help="one-based CSV record; use separate calls for differing headers")
    parser.add_argument("--encoding", default="utf-8-sig", help="strict decoding; e.g. utf-16 or cp1252 when verified")
    args = parser.parse_args(argv)
    if args.header_row is not None and args.header_row < 1:
        parser.error("--header-row must be at least 1")
    files = []
    for path in args.paths:
        try:
            files.append(inspect_csv(path, encoding=args.encoding,
                                     delimiter=DELIMITERS.get(args.delimiter), header_row=args.header_row))
        except (OSError, UnicodeError, csv.Error, ValueError, LookupError) as error:
            files.append({"path": str(path), "status": "error", "error": str(error)})
    print(json.dumps({"files": files}, ensure_ascii=False, indent=2))
    return int(any(item["status"] == "error" for item in files))


if __name__ == "__main__":
    raise SystemExit(main())

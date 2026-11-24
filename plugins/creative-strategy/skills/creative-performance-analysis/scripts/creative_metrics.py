#!/usr/bin/env python3
"""Aggregate normalized creative-performance rows into validated creative groups.

Identity is the tuple (account_id, ad_id, currency). A name is a label: it never
merges, splits, or joins anything. Rows with no ad_id stay unresolved. Rows from
two different sources are never summed together.

Input is one JSON document:

    {
      "rows": [
        {
          "source": "Meta",             # required provenance label
          "source_row_id": "m1",        # required, unique within its source
          "account_id": "acct-a",       # required; no "/"
          "ad_id": "101",               # required to be groupable; no "/"
          "date": "2026-09-01",         # daily grain; OR period_start + period_end
          "currency": "USD",            # required
          "name": "Summer Sale",        # optional label, never identity
          "spend": "100",               # additive metrics; omit or null = missing
          "impressions": null,
          "link_clicks": null,
          "new_orders": null,
          "new_revenue": null,
          "video_3_sec_watched_actions": null,  # normalized count; Meta actions video_view also maps here
          "media_type": "video",        # verified video/image; unknown cannot supply a full hook rate
          "source_row_locator": "export.json#/data/0",
          "measurement_basis": {},      # per-metric scope: see below; unknown suppresses acquisition ratios
          "video_6_sec_watched_actions": null,
          "video_thruplay_watched_actions": null,
          "asset_id": "asset-x",        # optional grouping evidence
          "copy_id": "copy-x",
          "destination_id": "/one"
        }
      ],
      "groups": [                       # optional explicit creative grouping
        {
          "group_id": "summer-sale-v1",
          "members": ["acct-a/101", "acct-a/205"],
          "evidence": {"asset_id": "asset-x", "copy_id": "copy-x", "destination_id": "/one"}
        }
      ]
    }

An explicit group that joins more than one ad must carry a complete, non-empty
asset_id / copy_id / destination_id triple that matches every member exactly.
Reject the join; never assume the ads are the same creative.

A member is written "account/ad". One ad carrying two currencies is rejected:
partition the export by currency before aggregating.

Output is JSON on stdout. Amounts are exact decimal strings. A metric is null
when any row behind it is missing, or when its denominator is zero; it is never
zero-filled. Independent sources must be run separately.

unprocessed_fields lists every input row field outside this helper's contract,
including fields present only on a late row. Inspect them in the original source
and record their analytical disposition; the helper has not considered them.
The optional original_records list contains {locator, record} objects from all
original rows/pages. field_treatments maps their JSON-pointer field paths to a
specific disposition/reason and normalized_fields or an analysis_ref. Nested
list measures use action_type/type selectors; output retains actual row/item
locators. Missing treatments, missing mappings and unlinked normalized rows
make source_measure_coverage incomplete. Without originals it is not_checked,
never proof that preparation preserved every metric. Originals stay accessible.
Every original locator must link to a normalized row or have a source_row_treatments
entry with disposition "excluded" or "analyzed at original grain" and a reason.
Original-grain analysis also requires analysis_ref; a claimed representation is
not a substitute for an actual normalized row link.

measurement_basis is a row object keyed by spend/new_orders/new_revenue. Each
basis declares population, geography, date_basis, timezone and attribution as
verified non-empty strings. Unknown or differing bases suppress the affected
ncac/nc_roas/new_aov only; underlying amounts and reconciliation remain. These
are declarations to verify at source, not proof of geography or attribution.

Hook/hold rates use confirmed media_type=video rows only. Meta's exact actions
video_view entry maps to video_3_sec_watched_actions, preserving missing values
and rejecting a conflicting explicit count. hook_rate is a fraction; multiply
by 100 for percentage display. video_view_per_impression is already percent
and is checked separately. Original actions remain unprocessed fields so other
measures cannot silently disappear. See the source contract's Hook Rate owner.

Period exports use inclusive period_start and period_end instead of date.
Overlapping periods for the same ad are rejected; never invent daily rows.
Default groups are ad totals, not proof of an unchanged creative. Check
creative_identity and identity_evidence before making asset-level claims.
references_match means the supplied asset, copy and page references agree;
the tool has not opened those references or verified the actual creative.

Numeric contract. Amounts must be finite, non-negative, smaller than 1e15, and
carry at most 12 decimal places. Anything outside that is rejected as a data
error; verify the units or revise the supported contract for an out-of-range
source. Sums inside that range are exact up to 10 million input rows. Rates are computed at 40
significant digits; a quotient that does not terminate is therefore rounded at
the 40th significant digit. This keeps the arithmetic bounded and auditable
without an arbitrary-precision numeric layer.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date as _date
from decimal import Decimal, InvalidOperation
from decimal import localcontext
from pathlib import Path


ADDITIVE_METRICS = (
    "spend",
    "impressions",
    "link_clicks",
    "new_orders",
    "new_revenue",
    "video_3_sec_watched_actions",
    "video_6_sec_watched_actions",
    "video_thruplay_watched_actions",
)

EVIDENCE_FIELDS = ("asset_id", "copy_id", "destination_id")

BASIS_FIELDS = ("population", "geography", "date_basis", "timezone", "attribution")

REQUIRED_FIELDS = ("source", "source_row_id", "account_id", "currency")

# Group ids and member references are written "account/ad", so a raw identifier
# containing "/" could not be represented unambiguously.
KEY_DELIMITER = "/"

RECONCILED_METRICS = ("spend", "new_revenue", "new_orders")

SCALAR_TYPES = (str, int, float, Decimal)

# datetime.date.fromisoformat also accepts the basic "20260901" form; the
# contract wants the calendar form so a value is never ambiguous.
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

# Supported numeric range. See the module docstring for the contract.
MAX_ADJUSTED_EXPONENT = 15
MAX_DECIMAL_PLACES = 12
WORKING_PRECISION = 40
MAX_INPUT_ROWS = 10_000_000


class MetricsError(ValueError):
    """Raised when rows cannot be safely grouped, joined, or aggregated."""


def _plain(value: Decimal) -> str:
    """Render a Decimal without scientific notation."""
    return format(value, "f")


def _scalar(value: object, where: str, field: str) -> str:
    if isinstance(value, bool):
        raise MetricsError(f"{where}: {field} must not be a boolean")
    if isinstance(value, SCALAR_TYPES):
        return str(value).strip()
    raise MetricsError(f"{where}: {field} must be a single value, got {type(value).__name__}")


def _text(row: dict, field: str, where: str) -> str:
    value = row.get(field)
    if value is None:
        raise MetricsError(f"{where}: missing required field {field!r}")
    text = _scalar(value, where, field)
    if text == "":
        raise MetricsError(f"{where}: missing required field {field!r}")
    return text


def _metric(value: object, where: str) -> Decimal | None:
    """Return an exact non-negative Decimal, or None when the value is missing.

    Vendor formatting is normalized upstream. A currency symbol, thousands
    separator, or percent sign is an error here, not something to guess at.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise MetricsError(f"{where}: expected a number, got a boolean")
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, int):
        number = Decimal(value)
    elif isinstance(value, (str, float)):
        text = str(value).strip()
        if text == "":
            return None
        try:
            number = Decimal(text)
        except InvalidOperation as exc:
            raise MetricsError(f"{where}: {value!r} is not a number") from exc
    else:
        raise MetricsError(f"{where}: expected a number, got {type(value).__name__}")

    if not number.is_finite():
        raise MetricsError(f"{where}: {value!r} is not a finite number")
    if number < 0:
        raise MetricsError(f"{where}: {value!r} is negative; a count or amount cannot be")
    if number == 0:
        return Decimal(0)
    if (
        number.adjusted() >= MAX_ADJUSTED_EXPONENT
        or number.as_tuple().exponent < -MAX_DECIMAL_PLACES
    ):
        raise MetricsError(
            f"{where}: {value!r} is outside the supported range (magnitude below "
            f"1e{MAX_ADJUSTED_EXPONENT}, at most {MAX_DECIMAL_PLACES} decimal places)"
        )
    return number


def _optional_text(value: object, where: str, field: str) -> str | None:
    if value is None:
        return None
    text = _scalar(value, where, field)
    return text or None


def _bucket(account_id: str, ad_id: str, currency: str) -> tuple[str, str, str]:
    return (account_id, ad_id, currency)


def _iso_date(raw: dict, field: str, where: str) -> str:
    value = _text(raw, field, where)
    if not ISO_DATE.fullmatch(value):
        raise MetricsError(f"{where}: {field} {value!r} is not an ISO date (YYYY-MM-DD)")
    try:
        _date.fromisoformat(value)
    except ValueError as exc:
        raise MetricsError(f"{where}: {field} {value!r} is not a real date") from exc
    return value


def _prepare_rows(rows: list[dict]) -> list[dict]:
    """Validate required fields, duplicates, and source boundaries."""
    if not isinstance(rows, list) or not rows:
        raise MetricsError("rows: expected a non-empty list")

    seen_rows: set[tuple[str, str]] = set()
    seen_grain: dict[tuple[str, str, str, str, str, str], str] = {}
    periods: dict[tuple[str, str, str, str], list[tuple[str, str, str]]] = {}
    sources: set[str] = set()
    prepared: list[dict] = []

    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise MetricsError(f"rows[{index}]: expected an object")
        for field in REQUIRED_FIELDS:
            if raw.get(field) is None or _scalar(raw[field], f"rows[{index}]", field) == "":
                raise MetricsError(f"rows[{index}]: missing required field {field!r}")

        source = _text(raw, "source", f"rows[{index}]")
        row_id = _text(raw, "source_row_id", f"rows[{index}]")
        where = f"{source}:{row_id}"

        account_id = _text(raw, "account_id", where)
        ad_id = _optional_text(raw.get("ad_id"), where, "ad_id")
        currency = _text(raw, "currency", where)

        if KEY_DELIMITER in account_id:
            raise MetricsError(
                f"{where}: account_id {account_id!r} contains '/', which is reserved for group "
                "references; keep the raw identifier and expose it as-is"
            )
        if ad_id is not None and KEY_DELIMITER in ad_id:
            raise MetricsError(
                f"{where}: ad_id {ad_id!r} contains '/', which group references cannot "
                "represent unambiguously"
            )

        if raw.get("date") is not None:
            if raw.get("period_start") is not None or raw.get("period_end") is not None:
                raise MetricsError(f"{where}: use date OR period_start/period_end, not both")
            raw_date = _iso_date(raw, "date", where)
            start = end = raw_date
        else:
            raw_date = None
            if raw.get("period_start") is None and raw.get("period_end") is None:
                raise MetricsError(f"{where}: missing required field 'date' or period_start/period_end")
            start = _iso_date(raw, "period_start", where)
            end = _iso_date(raw, "period_end", where)
            if end < start:
                raise MetricsError(f"{where}: period_end precedes period_start")

        duplicate = (source, row_id)
        if duplicate in seen_rows:
            raise MetricsError(f"duplicate source row: {where}")
        seen_rows.add(duplicate)

        if ad_id is not None:
            grain = (source, account_id, ad_id, start, end, currency)
            if grain in seen_grain:
                raise MetricsError(
                    f"duplicate source-grain row {'/'.join(grain)}: {where} repeats "
                    f"{seen_grain[grain]}"
                )
            seen_grain[grain] = where
            periods.setdefault((source, account_id, ad_id, currency), []).append((start, end, where))

        sources.add(source)
        metrics = {
            metric: _metric(raw.get(metric), f"{where}.{metric}")
            for metric in ADDITIVE_METRICS
        }
        if source.casefold() == "meta" and "actions" in raw:
            count = _action_value(raw["actions"], "video_view", f"{where}.actions")
            supplied = metrics["video_3_sec_watched_actions"]
            if supplied is not None and count is not None and supplied != count:
                raise MetricsError(f"{where}: normalized 3-second views disagree with Meta video_view")
            if supplied is None:
                metrics["video_3_sec_watched_actions"] = count
        basis = raw.get("measurement_basis")
        if basis is not None and not isinstance(basis, dict):
            raise MetricsError(f"{where}: measurement_basis must be an object")
        prepared.append(
            {
                "where": where,
                "source": source,
                "row_id": row_id,
                "account_id": account_id,
                "ad_id": ad_id,
                "date": raw_date,
                "period_start": start,
                "period_end": end,
                "currency": currency,
                "name": _optional_text(raw.get("name"), where, "name"),
                "source_row_locator": _optional_text(raw.get("source_row_locator"), where, "source_row_locator"),
                "measurement_basis": basis or {},
                "media_type": _optional_text(raw.get("media_type"), where, "media_type"),
                "video_view_per_impression": (
                    _action_value(raw["video_view_per_impression"], "video_view", f"{where}.video_view_per_impression")
                    if source.casefold() == "meta" and "video_view_per_impression" in raw else None
                ),
                "metrics": metrics,
                "evidence": {
                    field: _optional_text(raw.get(field), where, field)
                    for field in EVIDENCE_FIELDS
                },
            }
        )

    for intervals in periods.values():
        ordered = sorted(intervals)
        for previous, current in zip(ordered, ordered[1:]):
            if current[0] <= previous[1]:
                raise MetricsError(
                    f"overlapping source periods: {previous[2]} and {current[2]}; "
                    "choose non-overlapping rows instead of summing the same days twice"
                )

    if len(sources) > 1:
        raise MetricsError(
            "rows mix independent sources "
            + ", ".join(sorted(sources))
            + ": run each source separately. Meta and AdBeacon spend must not be summed."
        )
    return prepared


def _unmapped_row(row: dict) -> dict:
    return {
        "source": row["source"],
        "source_row_id": row["row_id"],
        "source_row_locator": row["source_row_locator"],
        "measurement_basis": row["measurement_basis"],
        "account_id": row["account_id"],
        "date": row["date"],
        "period_start": row["period_start"],
        "period_end": row["period_end"],
        "currency": row["currency"],
        "name": row["name"],
        "metrics": {
            metric: (None if value is None else _plain(value))
            for metric, value in row["metrics"].items()
        },
        "reason": "no ad_id: a name is a label, not an identity; needs a verified join",
    }


def _reference(account_id: str, ad_id: str) -> str:
    return f"{account_id}/{ad_id}"


def _parse_reference(spec: object, where: str) -> tuple[str, str]:
    if not isinstance(spec, str) or spec.strip() == "":
        raise MetricsError(f"{where}: a member must be written 'account/ad'")
    text = spec.strip()
    account_id, separator, ad_id = text.partition("/")
    if separator == "" or account_id == "" or ad_id == "" or "/" in ad_id:
        raise MetricsError(f"{where}: member {spec!r} must be written 'account/ad'")
    return (account_id, ad_id)


def _resolve_groups(
    prepared: list[dict], groups: list[dict] | None
) -> tuple[list[dict], list[dict], dict[tuple[str, str, str], list[dict]]]:
    """Return (group definitions, unresolved rows, buckets)."""
    buckets: dict[tuple[str, str, str], list[dict]] = {}
    unresolved: list[dict] = []
    for row in prepared:
        if row["ad_id"] is None:
            unresolved.append(row)
            continue
        buckets.setdefault(_bucket(row["account_id"], row["ad_id"], row["currency"]), []).append(row)

    currencies_per_ad: dict[tuple[str, str], set[str]] = {}
    for account_id, ad_id, currency in buckets:
        currencies_per_ad.setdefault((account_id, ad_id), set()).add(currency)
    mixed = sorted(key for key, values in currencies_per_ad.items() if len(values) > 1)
    if mixed:
        account_id, ad_id = mixed[0]
        raise MetricsError(
            f"ad {account_id}/{ad_id} carries {sorted(currencies_per_ad[mixed[0]])}: partition "
            "the export by currency before aggregating. Amounts in different currencies are "
            "never summed."
        )

    def default_id(key: tuple[str, str, str]) -> str:
        return _reference(key[0], key[1])

    def resolve(spec: object, where: str) -> tuple[str, str, str]:
        account_id, ad_id = _parse_reference(spec, where)
        matches = [key for key in buckets if key[0] == account_id and key[1] == ad_id]
        if not matches:
            raise MetricsError(
                f"{where}: member {spec!r} has no rows: a group cannot claim an ad that is "
                "absent or has no ad_id"
            )
        return matches[0]

    definitions: list[dict] = []
    claimed: dict[tuple[str, str, str], str] = {}
    used_ids: dict[str, str] = {}

    def claim_group_id(group_id: str, where: str) -> None:
        if group_id in used_ids:
            raise MetricsError(
                f"{where}: group_id {group_id!r} is already used by {used_ids[group_id]}; "
                "group ids must be unique"
            )
        used_ids[group_id] = where

    for index, group in enumerate(groups or []):
        where = f"groups[{index}]"
        if not isinstance(group, dict):
            raise MetricsError(f"{where}: expected an object")
        group_id = group.get("group_id")
        if not isinstance(group_id, str) or group_id.strip() == "":
            raise MetricsError(f"{where}: missing group_id")
        group_id = group_id.strip()
        claim_group_id(group_id, where)

        members = group.get("members")
        if not isinstance(members, list) or not members:
            raise MetricsError(f"{where}: members must be a non-empty list")
        evidence = group.get("evidence") or {}
        if not isinstance(evidence, dict):
            raise MetricsError(f"{where}: evidence must be an object")
        for field in evidence:
            if field not in EVIDENCE_FIELDS:
                raise MetricsError(f"{where}: unknown evidence field {field!r}")

        keys: list[tuple[str, str, str]] = []
        for member in members:
            key = resolve(member, where)
            if key in claimed:
                raise MetricsError(
                    f"{where}: {default_id(key)} is claimed by both {claimed[key]} and "
                    f"{group_id}: an ambiguous mapping is rejected, not resolved by guessing"
                )
            claimed[key] = group_id
            keys.append(key)

        accounts = {key[0] for key in keys}
        currencies = {key[2] for key in keys}
        if len(accounts) != 1:
            raise MetricsError(
                f"{where} ({group_id}) spans accounts {sorted(accounts)}: grouping preserves "
                "account identity"
            )
        if len(currencies) != 1:
            raise MetricsError(
                f"{where} ({group_id}) spans currencies {sorted(currencies)}: grouping "
                "preserves currency identity"
            )

        ad_ids = {key[1] for key in keys}
        if len(ad_ids) > 1 and set(evidence) != set(EVIDENCE_FIELDS):
            raise MetricsError(
                f"{where} ({group_id}) merges ads {sorted(ad_ids)} without complete evidence: "
                "asset_id, copy_id, and destination_id are all required before ads are called "
                "one creative"
            )

        clean_evidence: dict[str, str] = {}
        for field, expected in evidence.items():
            expected = _optional_text(expected, where, f"evidence.{field}")
            if expected is None:
                raise MetricsError(f"{where}: evidence.{field} is empty")
            for key in keys:
                observed = {row["evidence"][field] for row in buckets[key]}
                if observed != {expected}:
                    raise MetricsError(
                        f"{where} ({group_id}) joins {default_id(key)} whose {field} is "
                        f"{sorted(str(value) for value in observed)} against {expected!r}: "
                        "evidence must match exactly; reject the join instead of assuming"
                    )
            clean_evidence[field] = expected

        definitions.append({"group_id": group_id, "keys": keys, "evidence": clean_evidence})

    for key in sorted(buckets):
        if key in claimed:
            continue
        group_id = default_id(key)
        claim_group_id(group_id, "default grouping")
        definitions.append({"group_id": group_id, "keys": [key], "evidence": {}})

    return definitions, unresolved, buckets


def _sum(rows: list[dict], metric: str) -> Decimal | None:
    values = [row["metrics"][metric] for row in rows]
    if any(value is None for value in values):
        return None
    return sum(values, Decimal(0))


def _rate(numerator: Decimal | None, denominator: Decimal | None) -> str | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return _plain(numerator / denominator)


def _action_value(items: object, action: str, where: str) -> Decimal | None:
    """Read one exact Meta action; missing is not zero and aliases are not added."""
    if items is None:
        return None
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise MetricsError(f"{where}: expected a list of action objects")
    values = [item.get("value") for item in items if item.get("action_type") == action]
    if len(values) > 1:
        raise MetricsError(f"{where}: duplicate action_type {action!r}")
    return _metric(values[0], where) if values else None


def _compatible_basis(rows: list[dict], numerator: str, denominator: str) -> dict:
    """Check declared comparison bases; source verification remains the analyst's job."""
    observed = []
    unknown = []
    for row in rows:
        for metric in (numerator, denominator):
            basis = row["measurement_basis"].get(metric)
            if not isinstance(basis, dict) or any(
                not isinstance(basis.get(field), str) or not basis[field].strip()
                or basis[field].strip().casefold().startswith(("unknown", "unconfirmed"))
                for field in BASIS_FIELDS
            ):
                unknown.append(f"{row['where']}.{metric}")
            else:
                observed.append(tuple(basis[field].strip() for field in BASIS_FIELDS))
    status = "unknown" if unknown else "compatible" if len(set(observed)) == 1 else "incompatible"
    return {"status": status, "unknown": unknown, "declared_bases": [list(b) for b in sorted(set(observed))]}


def _source_coverage(document: dict, rows: list[dict]) -> dict:
    """Compare original scalar fields, including nested typed measures, with treatment."""
    originals = document.get("original_records")
    if originals is None:
        return {"status": "not_checked", "reason": "Original records were not supplied."}
    if not isinstance(originals, list) or not originals:
        raise MetricsError("original_records: expected a non-empty list of locator/record objects")
    treatments = document.get("field_treatments", {})
    if not isinstance(treatments, dict):
        raise MetricsError("field_treatments: expected an object keyed by source field")
    fields = {}
    locators = set()

    def escape(value):
        return str(value).replace("~", "~0").replace("/", "~1")

    def walk(value, field, locator):
        if isinstance(value, dict):
            if not value:
                fields.setdefault(field or "/", []).append(locator)
            for key, child in value.items():
                walk(child, field + "/" + escape(key), locator + "/" + escape(key))
        elif isinstance(value, list):
            if not value:
                fields.setdefault(field or "/", []).append(locator)
            for index, child in enumerate(value):
                token = "*"
                if isinstance(child, dict):
                    discriminator = next((k for k in ("action_type", "type") if k in child), None)
                    if discriminator:
                        token = "@" + discriminator + "=" + json.dumps(child[discriminator], ensure_ascii=False)
                walk(child, field + "/" + escape(token), locator + "/" + str(index))
        else:
            fields.setdefault(field or "/", []).append(locator)

    for index, original in enumerate(originals):
        if not isinstance(original, dict) or not isinstance(original.get("locator"), str) or "record" not in original:
            raise MetricsError(f"original_records[{index}]: locator and record required")
        locator = original["locator"].strip()
        if not locator or locator in locators:
            raise MetricsError(f"original_records[{index}]: locator must be non-empty and unique")
        locators.add(locator)
        walk(original["record"], "", locator)
    allowed = {"used", "checked but not material", "duplicate of a named measure", "unusable", "dimension"}
    normalized_fields = {field for row in rows for field in row}
    missing = []
    entries = []
    for field, locations in sorted(fields.items()):
        treatment = treatments.get(field)
        valid = (isinstance(treatment, dict) and treatment.get("disposition") in allowed
                 and isinstance(treatment.get("reason"), str) and bool(treatment["reason"].strip()))
        targets = treatment.get("normalized_fields", []) if isinstance(treatment, dict) else []
        valid = valid and isinstance(targets, list) and all(isinstance(t, str) and t in normalized_fields for t in targets)
        if valid and treatment["disposition"] == "used" and not targets:
            valid = isinstance(treatment.get("analysis_ref"), str) and bool(treatment["analysis_ref"].strip())
        if valid and treatment["disposition"] == "duplicate of a named measure":
            valid = treatment.get("duplicate_of") in fields and treatment["duplicate_of"] != field
        if not valid:
            missing.append(field)
        entries.append({"source_field": field, "locations": locations, "treatment": treatment, "valid": bool(valid)})
    linked = {row.get("source_row_locator") for row in rows} & locators
    row_treatments = document.get("source_row_treatments", {})
    if not isinstance(row_treatments, dict):
        raise MetricsError("source_row_treatments: expected an object keyed by original locator")
    invalid_rows = []
    for locator, treatment in row_treatments.items():
        valid = (locator in locators and locator not in linked and isinstance(treatment, dict)
                 and treatment.get("disposition") in {"excluded", "analyzed at original grain"}
                 and isinstance(treatment.get("reason"), str) and bool(treatment["reason"].strip()))
        if valid and treatment["disposition"] == "analyzed at original grain":
            valid = isinstance(treatment.get("analysis_ref"), str) and bool(treatment["analysis_ref"].strip())
        if not valid:
            invalid_rows.append(locator)
    unmatched = sorted(locators - linked - (set(row_treatments) - set(invalid_rows)))
    unlinked = [row.get("source_row_id") for row in rows if row.get("source_row_locator") not in locators]
    return {"status": "complete" if not missing and not unlinked and not unmatched and not invalid_rows else "incomplete",
            "fields": entries, "missing_treatments": missing, "unlinked_normalized_rows": unlinked,
            "unrepresented_original_rows": unmatched, "source_row_treatments": row_treatments,
            "invalid_row_treatments": sorted(invalid_rows),
            "stale_treatments": sorted(set(treatments) - set(fields))}


def _build_group(definition: dict, buckets: dict[tuple[str, str, str], list[dict]]) -> dict:
    rows = [row for key in definition["keys"] for row in buckets[key]]
    totals = {metric: _sum(rows, metric) for metric in ADDITIVE_METRICS}
    missing = {
        metric: sorted(row["where"] for row in rows if row["metrics"][metric] is None)
        for metric in ADDITIVE_METRICS
    }
    missing = {metric: names for metric, names in missing.items() if names}
    availability = {
        metric: ("missing" if all(row["metrics"][metric] is None for row in rows)
                 else "partial" if metric in missing else "complete")
        for metric in ADDITIVE_METRICS
    }
    identity = {
        field: sorted({row["evidence"][field] for row in rows if row["evidence"][field]})
        for field in EVIDENCE_FIELDS
    }
    identity_status = (
        "changed" if any(len(values) > 1 for values in identity.values())
        else "references_match" if all(row["evidence"][field] for row in rows for field in EVIDENCE_FIELDS)
        else "unconfirmed"
    )
    acquisition = {
        name: _compatible_basis(rows, numerator, denominator)
        for name, numerator, denominator in (
            ("ncac", "spend", "new_orders"),
            ("nc_roas", "new_revenue", "spend"),
            ("new_aov", "new_revenue", "new_orders"),
        )
    }
    video_rows = [row for row in rows if row["media_type"] == "video"]
    video_views = _sum(video_rows, "video_3_sec_watched_actions") if video_rows else None
    video_impressions = _sum(video_rows, "impressions") if video_rows else None
    hook_checks = []
    for row in video_rows:
        calculated = _rate(row["metrics"]["video_3_sec_watched_actions"], row["metrics"]["impressions"])
        api = row["video_view_per_impression"]
        hook_checks.append({
            "source_row": row["where"], "api_percent": None if api is None else _plain(api),
            "calculated_percent": None if calculated is None else _plain(Decimal(calculated) * 100),
            "matches": None if api is None or calculated is None else abs(api - Decimal(calculated) * 100) <= Decimal("0.01"),
        })

    return {
        "group_id": definition["group_id"],
        "account_id": rows[0]["account_id"],
        "currency": rows[0]["currency"],
        "ad_ids": sorted({row["ad_id"] for row in rows}),
        "label_only_names": sorted({row["name"] for row in rows if row["name"]}),
        "sources": sorted({row["source"] for row in rows}),
        "source_rows": sorted(row["where"] for row in rows),
        "source_locations": {row["where"]: row["source_row_locator"] for row in rows},
        "measurement_bases": {row["where"]: row["measurement_basis"] for row in rows},
        "date_range": [min(row["period_start"] for row in rows), max(row["period_end"] for row in rows)],
        "input_grains": sorted({"daily" if row["date"] else "period" for row in rows}),
        "grouping_evidence": definition["evidence"],
        "creative_identity": identity_status,
        "identity_evidence": identity,
        "metrics": {
            metric: (None if value is None else _plain(value))
            for metric, value in totals.items()
        },
        "derived": {
            "ctr": _rate(totals["link_clicks"], totals["impressions"]),
            "cpc": _rate(totals["spend"], totals["link_clicks"]),
            "ncac": _rate(totals["spend"], totals["new_orders"]) if acquisition["ncac"]["status"] == "compatible" else None,
            "nc_roas": _rate(totals["new_revenue"], totals["spend"]) if acquisition["nc_roas"]["status"] == "compatible" else None,
            "new_aov": _rate(totals["new_revenue"], totals["new_orders"]) if acquisition["new_aov"]["status"] == "compatible" else None,
            "hook_rate": _rate(video_views, video_impressions),
            "early_hold_rate": _rate(
                _sum(video_rows, "video_6_sec_watched_actions") if video_rows else None,
                video_views,
            ),
            "deep_hold_rate": _rate(
                _sum(video_rows, "video_thruplay_watched_actions") if video_rows else None,
                video_views,
            ),
        },
        "incomplete": any(metric in missing for metric in RECONCILED_METRICS)
            or "partial" in availability.values(),
        "metric_availability": availability,
        "acquisition_basis": acquisition,
        "hook_coverage": {
            "scope": "confirmed video rows only",
            "rate_unit": "fraction", "confirmed_video_rows": len(video_rows),
            "unknown_media_rows": [row["where"] for row in rows if row["media_type"] not in ("video", "image")],
            "video_impressions": None if video_impressions is None else _plain(video_impressions),
            "missing_view_rows": [row["where"] for row in video_rows if row["metrics"]["video_3_sec_watched_actions"] is None],
            "api_checks": hook_checks,
        },
        "missing_inputs": missing,
    }


def _emitted_sum(groups: list[dict], account_id: str, currency: str, metric: str) -> Decimal | None:
    """Sum a metric from the emitted groups, exactly as they were reported."""
    values: list[Decimal] = []
    for group in groups:
        if group["account_id"] != account_id or group["currency"] != currency:
            continue
        value = group["metrics"][metric]
        if value is None:
            return None
        values.append(Decimal(value))
    return sum(values, Decimal(0))


def _reconciliation(
    prepared: list[dict], results: list[dict], unresolved: list[dict]
) -> list[dict]:
    """Compare the emitted rows against the input, per account+currency.

    The grouped figure is read back from the emitted groups and the unresolved
    figure from the emitted unmapped rows, so a bug in aggregation shows up as
    an imbalance instead of being averaged away by recomputing from the input.
    """
    pairs = sorted({(row["account_id"], row["currency"]) for row in prepared})
    report: list[dict] = []
    for account_id, currency in pairs:
        input_rows = [
            row
            for row in prepared
            if row["account_id"] == account_id and row["currency"] == currency
        ]
        unresolved_rows = [
            row
            for row in unresolved
            if row["account_id"] == account_id and row["currency"] == currency
        ]
        entry = {
            "account_id": account_id,
            "currency": currency,
            "input_rows": len(input_rows),
            "grouped_rows": sum(
                len(group["source_rows"])
                for group in results
                if group["account_id"] == account_id and group["currency"] == currency
            ),
            "unresolved_rows": len(unresolved_rows),
            "metrics": {},
        }
        for metric in RECONCILED_METRICS:
            total = _sum(input_rows, metric)
            grouped = _emitted_sum(results, account_id, currency, metric)
            unresolved_total = _emitted_sum(unresolved, account_id, currency, metric)
            if total is None or grouped is None or unresolved_total is None:
                balanced = None
            else:
                balanced = total == grouped + unresolved_total
            entry["metrics"][metric] = {
                "input": None if total is None else _plain(total),
                "grouped": None if grouped is None else _plain(grouped),
                "unresolved": None if unresolved_total is None else _plain(unresolved_total),
                "balanced": balanced,
            }
        report.append(entry)
    return report


def aggregate(document: dict) -> dict:
    """Validate one source's normalized rows and aggregate them into creative groups."""
    # Sums are exact inside the supported range at this precision; the default
    # context precision of 28 would silently round large amounts.
    with localcontext() as context:
        context.prec = WORKING_PRECISION
        return _aggregate(document)


def _aggregate(document: dict) -> dict:
    if not isinstance(document, dict):
        raise MetricsError("input: expected a JSON object with 'rows'")
    rows = document.get("rows")
    if isinstance(rows, list) and len(rows) > MAX_INPUT_ROWS:
        raise MetricsError(
            f"rows: {len(rows)} rows exceeds the supported {MAX_INPUT_ROWS}; "
            "split the export"
        )
    prepared = _prepare_rows(rows)
    groups = document.get("groups")
    if groups is not None and not isinstance(groups, list):
        raise MetricsError("groups: expected a list")

    definitions, unresolved, buckets = _resolve_groups(prepared, groups)
    results = sorted(
        (_build_group(definition, buckets) for definition in definitions),
        key=lambda group: group["group_id"],
    )

    labels: dict[tuple[str, str], list[str]] = {}
    for group in results:
        for name in group["label_only_names"]:
            labels.setdefault((group["account_id"], name), []).append(group["group_id"])
    warnings = [
        f"name {name!r} labels {len(group_ids)} separate ads in {account_id} "
        f"({', '.join(sorted(group_ids))}): kept separate, not merged"
        for (account_id, name), group_ids in sorted(labels.items())
        if len(group_ids) > 1
    ]
    warnings.extend(
        f"{group['group_id']}: creative evidence changed within the ad total; "
        "do not report this as one unchanged creative"
        for group in results if group.get("creative_identity") == "changed"
    )

    unmapped = sorted(
        (_unmapped_row(row) for row in unresolved), key=lambda row: row["source_row_id"]
    )
    supported = set(REQUIRED_FIELDS + ADDITIVE_METRICS + EVIDENCE_FIELDS) | {
        "ad_id", "name", "date", "period_start", "period_end",
        "source_row_locator", "measurement_basis", "media_type"
    }
    unprocessed = sorted({field for row in rows for field in row} - supported)
    if unprocessed:
        warnings.append("Unprocessed fields require source review: " + ", ".join(unprocessed))
    source_coverage = _source_coverage(document, rows)
    if source_coverage["status"] == "incomplete":
        warnings.append("Original-source coverage is incomplete; inspect missing treatments and row links.")
    row_treatments = source_coverage.get("source_row_treatments", {})
    treated = sorted(set(row_treatments) - set(source_coverage.get("invalid_row_treatments", [])))
    if treated:
        warnings.append("Original-source rows outside normalized totals: " + ", ".join(
            f"{locator} ({row_treatments[locator]['disposition']})" for locator in treated))
    return {
        "source": prepared[0]["source"],
        "input_rows": len(prepared),
        "unprocessed_fields": unprocessed,
        "source_measure_coverage": source_coverage,
        "groups": results,
        "unmapped": unmapped,
        "warnings": warnings,
        "reconciliation": _reconciliation(prepared, results, unmapped),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="JSON document with normalized rows")
    parser.add_argument("--output", type=Path, help="write JSON here instead of stdout")
    args = parser.parse_args(argv)

    try:
        if args.output and (args.input.resolve() == args.output.resolve() or (
                args.output.exists() and args.input.samefile(args.output))):
            raise MetricsError("Keep the output separate from the input, including file aliases")
        document = json.loads(args.input.read_text(encoding="utf-8"), parse_float=Decimal)
        report = aggregate(document)
    except MetricsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: unreadable input: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, indent=2, default=_plain) + "\n"
    if args.output:
        replacement = None
        try:
            with tempfile.NamedTemporaryFile(dir=args.output.parent, prefix=".metrics-", delete=False) as temporary:
                replacement = Path(temporary.name)
            replacement.write_text(rendered, encoding="utf-8")
            os.replace(replacement, args.output)
        except OSError as exc:
            print(f"error: could not save output: {exc}", file=sys.stderr)
            return 2
        finally:
            if replacement is not None:
                replacement.unlink(missing_ok=True)
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

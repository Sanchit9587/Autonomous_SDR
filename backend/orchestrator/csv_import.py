"""CSV -> ProspectProfile parsing with forgiving header matching.

Real-world lead CSVs have wildly varying headers, so we map a set of common
aliases per field rather than demanding exact column names. Name is the only
required field; rows without one are reported as invalid.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from core.models import Prospect, ProspectProfile

# field -> accepted header aliases (lowercased, spaces/underscores normalised)
_ALIASES: dict[str, list[str]] = {
    "name": ["name", "full name", "fullname", "full_name", "contact name", "prospect"],
    "company_name": ["company", "company name", "company_name", "organization", "organisation", "employer", "account"],
    "position": ["position", "title", "job title", "role", "job_title", "headline title"],
    "headline": ["headline", "bio", "summary", "about"],
    "location": ["location", "city", "region", "country", "geo"],
    "work_email": ["email", "work email", "work_email", "email address", "e-mail"],
    "linkedin_url": ["linkedin", "linkedin url", "linkedin_url", "profile", "profile url", "linkedin profile"],
    "company_size": ["company size", "company_size", "employees", "headcount", "size"],
}


@dataclass
class ParseResult:
    prospects: list[Prospect] = field(default_factory=list)
    invalid_rows: int = 0          # rows with no usable name
    total_rows: int = 0


def _normalise(header: str) -> str:
    return header.strip().lower().replace("_", " ")


def _build_column_map(headers: list[str]) -> dict[str, int]:
    """Map each model field to the CSV column index that matches one of its aliases."""
    norm = [_normalise(h) for h in headers]
    col_map: dict[str, int] = {}
    for model_field, aliases in _ALIASES.items():
        for i, h in enumerate(norm):
            if h in aliases:
                col_map[model_field] = i
                break
    return col_map


def _cell(row: list[str], idx: int | None) -> str | None:
    if idx is None or idx >= len(row):
        return None
    val = row[idx].strip()
    return val or None


def parse_prospects_csv(raw: bytes) -> ParseResult:
    """Parse CSV bytes into Prospect objects. Never raises on a bad row — bad
    rows are counted, not fatal."""
    result = ParseResult()
    try:
        text = raw.decode("utf-8-sig")  # utf-8-sig strips a BOM if present (Excel exports)
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")

    reader = csv.reader(io.StringIO(text))
    try:
        headers = next(reader)
    except StopIteration:
        return result  # empty file

    col_map = _build_column_map(headers)
    name_idx = col_map.get("name")

    for row in reader:
        if not row or all(not c.strip() for c in row):
            continue
        result.total_rows += 1
        name = _cell(row, name_idx)
        if not name:
            result.invalid_rows += 1
            continue

        size_raw = _cell(row, col_map.get("company_size"))
        company_size = None
        if size_raw:
            digits = "".join(ch for ch in size_raw if ch.isdigit())
            company_size = int(digits) if digits else None

        profile = ProspectProfile(
            name=name,
            company_name=_cell(row, col_map.get("company_name")),
            position=_cell(row, col_map.get("position")),
            headline=_cell(row, col_map.get("headline")),
            location=_cell(row, col_map.get("location")),
            work_email=_cell(row, col_map.get("work_email")),
            linkedin_url=_cell(row, col_map.get("linkedin_url")),
            company_size=company_size,
        )
        result.prospects.append(Prospect(profile=profile))

    return result
"""Layer 3: DwC semantic row-level checks."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from ..report import Issue, Report, Severity

BASIS_OF_RECORD_VALUES = {
    "PreservedSpecimen",
    "FossilSpecimen",
    "LivingSpecimen",
    "MaterialSample",
    "MaterialCitation",
    "HumanObservation",
    "MachineObservation",
    "Taxon",
    "Occurrence",
    "Event",
    "MaterialEntity",
}

OCCURRENCE_STATUS_VALUES = {"present", "absent"}

TAXON_RANK_VALUES = {
    "domain",
    "kingdom",
    "phylum",
    "class",
    "order",
    "family",
    "superfamily",
    "tribe",
    "genus",
    "subgenus",
    "section",
    "species",
    "subspecies",
    "variety",
    "form",
    "cultivar",
    "strain",
    "nothogenus",
    "nothospecies",
    "nothosubspecies",
    "infraspecificname",
    "infragenericname",
}

# ISO 3166-1 alpha-2 codes (comprehensive set)
_ISO_ALPHA2 = {
    "AD", "AE", "AF", "AG", "AI", "AL", "AM", "AO", "AQ", "AR", "AS", "AT",
    "AU", "AW", "AX", "AZ", "BA", "BB", "BD", "BE", "BF", "BG", "BH", "BI",
    "BJ", "BL", "BM", "BN", "BO", "BQ", "BR", "BS", "BT", "BV", "BW", "BY",
    "BZ", "CA", "CC", "CD", "CF", "CG", "CH", "CI", "CK", "CL", "CM", "CN",
    "CO", "CR", "CU", "CV", "CW", "CX", "CY", "CZ", "DE", "DJ", "DK", "DM",
    "DO", "DZ", "EC", "EE", "EG", "EH", "ER", "ES", "ET", "FI", "FJ", "FK",
    "FM", "FO", "FR", "GA", "GB", "GD", "GE", "GF", "GG", "GH", "GI", "GL",
    "GM", "GN", "GP", "GQ", "GR", "GS", "GT", "GU", "GW", "GY", "HK", "HM",
    "HN", "HR", "HT", "HU", "ID", "IE", "IL", "IM", "IN", "IO", "IQ", "IR",
    "IS", "IT", "JE", "JM", "JO", "JP", "KE", "KG", "KH", "KI", "KM", "KN",
    "KP", "KR", "KW", "KY", "KZ", "LA", "LB", "LC", "LI", "LK", "LR", "LS",
    "LT", "LU", "LV", "LY", "MA", "MC", "MD", "ME", "MF", "MG", "MH", "MK",
    "ML", "MM", "MN", "MO", "MP", "MQ", "MR", "MS", "MT", "MU", "MV", "MW",
    "MX", "MY", "MZ", "NA", "NC", "NE", "NF", "NG", "NI", "NL", "NO", "NP",
    "NR", "NU", "NZ", "OM", "PA", "PE", "PF", "PG", "PH", "PK", "PL", "PM",
    "PN", "PR", "PS", "PT", "PW", "PY", "QA", "RE", "RO", "RS", "RU", "RW",
    "SA", "SB", "SC", "SD", "SE", "SG", "SH", "SI", "SJ", "SK", "SL", "SM",
    "SN", "SO", "SR", "SS", "ST", "SV", "SX", "SY", "SZ", "TC", "TD", "TF",
    "TG", "TH", "TJ", "TK", "TL", "TM", "TN", "TO", "TR", "TT", "TV", "TW",
    "TZ", "UA", "UG", "UM", "US", "UY", "UZ", "VA", "VC", "VE", "VG", "VI",
    "VN", "VU", "WF", "WS", "YE", "YT", "ZA", "ZM", "ZW",
}


def _parse_iso8601(value: str) -> bool:
    """Return True if value is a parseable ISO 8601 date/datetime/interval."""
    if not value:
        return False
    # Handle intervals: two dates separated by /
    parts = value.split("/")
    if len(parts) == 2:
        start, end = parts
        if not start and not end:
            return False
        # Truncated end like "2007-11-13/15" — end is just a day component
        if start and end and end.isdigit():
            return _parse_single_date(start)
        return all(_parse_single_date(p) for p in parts if p)
    return _parse_single_date(value)


def _parse_single_date(value: str) -> bool:
    from datetime import datetime, date

    value = value.strip()
    # Year only
    if len(value) == 4 and value.isdigit():
        return True
    # Year-month
    if len(value) == 7 and value[4] == "-":
        try:
            datetime.strptime(value, "%Y-%m")
            return True
        except ValueError:
            return False
    # Try standard isoformat (handles dates, datetimes, with or without tz)
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%MZ",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M%z",
    ):
        try:
            datetime.strptime(value.rstrip("Z"), fmt.rstrip("Z"))
            return True
        except ValueError:
            continue
    # Python 3.11 handles more ISO 8601 variants natively
    try:
        datetime.fromisoformat(value)
        return True
    except ValueError:
        pass
    return False


def _open_csv(path: Path, delimiter: str = ","):
    return open(path, newline="", encoding="utf-8-sig")


def _get_delimiter(resource: dict) -> str:
    fmt = resource.get("format", "csv").lower()
    dialect = resource.get("dialect", {})
    if isinstance(dialect, dict):
        return dialect.get("delimiter", "\t" if fmt in ("tsv", "tab") else ",")
    return "\t" if fmt in ("tsv", "tab") else ","


def check(dp: dict, base_dir: Path, report: Report) -> None:
    """Run semantic checks on all resource CSV/TSV files."""
    for resource in dp.get("resources", []):
        name = resource.get("name", "<unnamed>")
        path_str = resource.get("path", "")
        if not path_str:
            continue
        csv_path = base_dir / path_str
        if not csv_path.exists():
            continue

        delimiter = _get_delimiter(resource)
        try:
            with _open_csv(csv_path) as fh:
                reader = csv.DictReader(fh, delimiter=delimiter)
                for row_num, row in enumerate(reader, start=2):
                    _check_row(row, row_num, name, report)
        except Exception as exc:
            report.add(Issue(
                severity=Severity.ERROR,
                resource=name,
                message=f"Could not read file: {exc}",
            ))


def _check_row(row: dict, row_num: int, resource: str, report: Report) -> None:
    def add(severity: Severity, field: str, msg: str) -> None:
        report.add(Issue(
            severity=severity,
            message=msg,
            resource=resource,
            row=row_num,
            field_name=field,
        ))

    bor = row.get("basisOfRecord", "").strip()
    if bor and bor not in BASIS_OF_RECORD_VALUES:
        add(Severity.ERROR, "basisOfRecord",
            f"basisOfRecord {bor!r} is not in the allowed vocabulary.")

    status = row.get("occurrenceStatus", "").strip()
    if status and status not in OCCURRENCE_STATUS_VALUES:
        add(Severity.ERROR, "occurrenceStatus",
            f"occurrenceStatus {status!r} must be 'present' or 'absent'.")

    lat_str = row.get("decimalLatitude", "").strip()
    lon_str = row.get("decimalLongitude", "").strip()

    lat: Optional[float] = None
    lon: Optional[float] = None

    if lat_str:
        try:
            lat = float(lat_str)
            if not (-90 <= lat <= 90):
                add(Severity.ERROR, "decimalLatitude",
                    f"decimalLatitude {lat} is outside [-90, 90].")
                lat = None
        except ValueError:
            add(Severity.ERROR, "decimalLatitude",
                f"decimalLatitude {lat_str!r} is not a number.")

    if lon_str:
        try:
            lon = float(lon_str)
            if not (-180 <= lon <= 180):
                add(Severity.ERROR, "decimalLongitude",
                    f"decimalLongitude {lon} is outside [-180, 180].")
                lon = None
        except ValueError:
            add(Severity.ERROR, "decimalLongitude",
                f"decimalLongitude {lon_str!r} is not a number.")

    if (lat is not None or lon is not None) and not row.get("geodeticDatum", "").strip():
        add(Severity.WARNING, "geodeticDatum",
            "geodeticDatum should be present when lat/lon are provided.")

    unc_str = row.get("coordinateUncertaintyInMeters", "").strip()
    if unc_str:
        try:
            unc = float(unc_str)
            if unc <= 0:
                add(Severity.ERROR, "coordinateUncertaintyInMeters",
                    f"coordinateUncertaintyInMeters must be > 0, got {unc}.")
        except ValueError:
            add(Severity.ERROR, "coordinateUncertaintyInMeters",
                f"coordinateUncertaintyInMeters {unc_str!r} is not a number.")

    cc = row.get("countryCode", "").strip()
    if cc and cc not in _ISO_ALPHA2:
        add(Severity.WARNING, "countryCode",
            f"countryCode {cc!r} is not a valid ISO 3166-1 alpha-2 code.")

    rank = row.get("taxonRank", "").strip()
    if rank and rank.lower() not in TAXON_RANK_VALUES:
        add(Severity.WARNING, "taxonRank",
            f"taxonRank {rank!r} is not in the DwC controlled vocabulary.")

    event_date = row.get("eventDate", "").strip()
    if event_date and not _parse_iso8601(event_date):
        add(Severity.ERROR, "eventDate",
            f"eventDate {event_date!r} is not a valid ISO 8601 date or interval.")

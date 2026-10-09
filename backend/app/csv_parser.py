"""Tolerant bank-statement CSV parser (HDFC/ICICI/SBI/Axis style layouts + generic Date/Description/Amount)."""
import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from . import config


class CSVParseError(Exception):
    """File-level problem: nothing can be imported."""


ALIASES = {
    "date": ["date", "txn date", "transaction date", "tran date", "posting date", "value date", "value dt"],
    "description": ["narration", "description", "particulars", "details", "remarks", "transaction remarks",
                    "transaction details", "txn description"],
    "debit": ["withdrawal", "withdrawal amt", "withdrawal amount", "withdrawals", "debit", "debit amount", "dr"],
    "credit": ["deposit", "deposit amt", "deposit amount", "deposits", "credit", "credit amount", "cr"],
    "amount": ["amount", "transaction amount", "txn amount", "amt"],
    "type": ["dr/cr", "cr/dr", "type", "transaction type", "txn type"],
    "balance": ["balance", "closing balance", "running balance", "available balance"],
}
DATE_FORMATS = ["%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%Y-%m-%d", "%d %b %Y", "%d-%b-%Y",
                "%d-%b-%y", "%d %b %y", "%d/%b/%Y", "%d.%m.%Y", "%d %B %Y"]


@dataclass
class ParseResult:
    rows: list = field(default_factory=list)
    errors: list = field(default_factory=list)  # [{row, reason}] (capped)
    total_rows: int = 0
    skipped: int = 0


def _norm_header(h: str) -> str:
    h = re.sub(r"\(.*?\)", "", h.lower()).replace(".", "").replace("_", " ").replace("*", "")
    return re.sub(r"\s+", " ", h).strip()


def _map_headers(row):
    mapping = {}
    for idx, cell in enumerate(row):
        n = _norm_header(cell)
        for key, names in ALIASES.items():
            if n in names and key not in mapping:
                mapping[key] = idx
                break
    ok = "date" in mapping and "description" in mapping and (
        "amount" in mapping or "debit" in mapping or "credit" in mapping)
    return mapping if ok else None


def parse_date(s: str):
    s = s.strip()
    candidates = [s] + ([s.split()[0]] if " " in s else [])
    for c in candidates:
        for fmt in DATE_FORMATS:
            try:
                d = datetime.strptime(c, fmt).date()
            except ValueError:
                continue
            if d.year < 1990 or d > date.today() + timedelta(days=1):
                raise ValueError("date out of range")
            return d
    raise ValueError(f"unrecognised date '{s[:20]}'")


def parse_amount(s):
    """Return (Decimal|None, suffix) where suffix is 'cr'/'dr'/None. Empty -> (None, None)."""
    if s is None:
        return None, None
    t = re.sub(r"(?i)(₹|rs\.?|inr|,|\s)", "", s)
    if t in ("", "-"):
        return None, None
    suffix = None
    m = re.search(r"(?i)(cr|dr)$", t)
    if m:
        suffix, t = m.group(1).lower(), t[: m.start()]
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    try:
        v = Decimal(t)
    except InvalidOperation:
        raise ValueError(f"invalid amount '{s[:20]}'")
    if not v.is_finite() or abs(v) > Decimal("999999999999"):
        raise ValueError("amount out of range")
    return (-v if neg else v), suffix


def _decode(raw: bytes) -> str:
    if b"\x00" in raw[:4096]:
        raise CSVParseError("This looks like a binary file, not a CSV. Export your statement as CSV and retry.")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def parse_csv(raw: bytes) -> ParseResult:
    text = _decode(raw)
    if not text.strip():
        raise CSVParseError("The file is empty.")
    sample = "\n".join(text.splitlines()[:40])
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delim = ","
    try:
        rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    except csv.Error as e:
        raise CSVParseError(f"Could not read CSV structure: {e}")
    if len(rows) > config.MAX_ROWS + 60:
        raise CSVParseError(f"Too many rows (limit {config.MAX_ROWS}). Split the statement by period.")

    header_idx, mapping = None, None
    for i, r in enumerate(rows[:40]):  # banks often put account info above the header
        mapping = _map_headers(r)
        if mapping:
            header_idx = i
            break
    if mapping is None:
        raise CSVParseError("Could not find a header row. Expected columns like Date, Narration/Description and "
                            "Debit/Credit or Amount.")

    res = ParseResult()

    def fail(rownum, reason):
        res.skipped += 1
        if len(res.errors) < 100:
            res.errors.append({"row": rownum, "reason": reason})

    for i, r in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        if not any(c.strip() for c in r):
            continue
        res.total_rows += 1
        get = lambda k: r[mapping[k]] if k in mapping and mapping[k] < len(r) else ""
        try:
            d = parse_date(get("date"))
            desc = re.sub(r"\s+", " ", get("description")).strip()[:500] or "(no description)"
            bal = None
            try:
                bal, _ = parse_amount(get("balance"))
            except ValueError:
                pass
            dv = cv = av = None
            suffix = None
            if "debit" in mapping or "credit" in mapping:
                dv, _ = parse_amount(get("debit"))
                cv, _ = parse_amount(get("credit"))
            if dv is None and cv is None and "amount" in mapping:
                av, suffix = parse_amount(get("amount"))
            if dv and dv != 0:
                typ, amt = "debit", abs(dv)
            elif cv and cv != 0:
                typ, amt = "credit", abs(cv)
            elif av is not None and av != 0:
                t = get("type").strip().lower()
                if suffix == "dr" or t in ("dr", "debit", "d", "withdrawal"):
                    typ = "debit"
                elif suffix == "cr" or t in ("cr", "credit", "c", "deposit"):
                    typ = "credit"
                else:
                    typ = "debit" if av < 0 else "credit"
                amt = abs(av)
            else:
                raise ValueError("no non-zero amount")
            res.rows.append({"date": d, "description": desc, "amount": amt.quantize(Decimal("0.01")),
                             "txn_type": typ, "balance": bal.quantize(Decimal("0.01")) if bal is not None else None})
        except ValueError as e:
            fail(i, str(e))
    if not res.rows and res.total_rows:
        raise CSVParseError("No valid transactions found. First problem: " + (res.errors[0]["reason"] if res.errors else "unknown"))
    if not res.rows:
        raise CSVParseError("Header found but the file contains no transaction rows.")
    return res

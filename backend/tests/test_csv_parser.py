from datetime import date
from decimal import Decimal

import pytest

from app.csv_parser import CSVParseError, parse_amount, parse_csv, parse_date
from tests.conftest import HDFC_CSV


def test_parses_bank_layout_with_preamble_and_indian_number_format():
    res = parse_csv(HDFC_CSV.encode())
    assert len(res.rows) == 5
    first = res.rows[0]
    assert first["date"] == date(2024, 9, 1)
    assert first["amount"] == Decimal("1250.50") and first["txn_type"] == "debit"
    assert res.rows[2]["txn_type"] == "credit" and res.rows[2]["amount"] == Decimal("60000.00")


def test_single_amount_column_with_dr_cr_and_semicolon_delimiter():
    csv_text = "Date;Description;Amount;Dr/Cr\n2024-01-05;Netflix;499.00;DR\n2024-01-06;Refund;100;CR\n"
    rows = parse_csv(csv_text.encode()).rows
    assert [r["txn_type"] for r in rows] == ["debit", "credit"]


def test_signed_amounts():
    rows = parse_csv(b"Date,Description,Amount\n05-01-2024,Shop,-250\n06-01-2024,Pay,1000\n").rows
    assert [r["txn_type"] for r in rows] == ["debit", "credit"]


def test_bad_rows_are_skipped_and_reported_not_fatal():
    text = "Date,Description,Debit,Credit\n01/01/2024,Good,10,\nnot-a-date,Bad,5,\n02/01/2024,NoAmount,,\n"
    res = parse_csv(text.encode())
    assert len(res.rows) == 1 and res.skipped == 2
    assert {e["row"] for e in res.errors} == {3, 4}


@pytest.mark.parametrize("raw", [b"", b"   \n", b"foo,bar\n1,2\n", b"\x00\x01\x02binary", b"Date,Description,Amount\n"])
def test_corrupt_or_irrelevant_files_raise_clear_error(raw):
    with pytest.raises(CSVParseError):
        parse_csv(raw)


def test_all_rows_invalid_raises():
    with pytest.raises(CSVParseError):
        parse_csv(b"Date,Description,Amount\nxx,yy,zz\n")


def test_cp1252_encoding_and_rupee_symbol():
    raw = "Date,Description,Amount\n01/01/2024,Caf\xe9,\u20b91,200.00 Dr\n".encode("cp1252", errors="ignore")
    assert parse_csv(raw).rows[0]["description"].startswith("Caf")


def test_helpers():
    assert parse_amount("(1,000.50)")[0] == Decimal("-1000.50")
    assert parse_amount("")[0] is None
    assert parse_date("5 Jan 2024") == date(2024, 1, 5)
    with pytest.raises(ValueError):
        parse_date("01/01/1850")
    with pytest.raises(ValueError):
        parse_amount("12abc")

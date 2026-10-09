import hashlib
import json
import re
from collections import Counter

from sqlalchemy.orm import Session

from .categorizer import Categorizer
from .csv_parser import ParseResult
from .models import Transaction, Upload


def _norm(desc: str) -> str:
    return re.sub(r"[^a-z0-9]", "", desc.lower())


def with_hashes(user_id: int, rows: list) -> list:
    """Hash identifies a transaction. An occurrence counter keeps genuinely identical rows
    (two Rs.50 chai payments on the same day) while still catching a re-uploaded statement."""
    seen = Counter()
    for r in rows:
        key = f"{r['date']}|{_norm(r['description'])}|{r['amount']}|{r['txn_type']}|{r['balance']}"
        occ = seen[key]
        seen[key] += 1
        r["hash"] = hashlib.sha256(f"{user_id}|{key}|{occ}".encode()).hexdigest()
    return rows


def existing_hashes(db: Session, user_id: int, hashes: list) -> set:
    found = set()
    for i in range(0, len(hashes), 500):  # stay under SQLite's bound-variable limit
        chunk = hashes[i:i + 500]
        q = db.query(Transaction.dedupe_hash).filter(Transaction.user_id == user_id, Transaction.dedupe_hash.in_(chunk))
        found.update(h for (h,) in q)
    return found


def ingest(db: Session, user_id: int, filename: str, parsed: ParseResult) -> Upload:
    rows = with_hashes(user_id, parsed.rows)
    dup = existing_hashes(db, user_id, [r["hash"] for r in rows])
    fresh = [r for r in rows if r["hash"] not in dup]
    cat = Categorizer(db, user_id)

    upload = Upload(user_id=user_id, filename=filename[:255], status="completed", total_rows=parsed.total_rows,
                    inserted=len(fresh), duplicates=len(rows) - len(fresh), skipped=parsed.skipped,
                    error_report=json.dumps(parsed.errors))
    db.add(upload)
    db.flush()
    db.bulk_insert_mappings(Transaction, [{
        "user_id": user_id, "upload_id": upload.id, "txn_date": r["date"], "description": r["description"],
        "amount": r["amount"], "txn_type": r["txn_type"], "balance": r["balance"], "dedupe_hash": r["hash"],
        "category_id": cat.categorize(r["description"], r["txn_type"]),
    } for r in fresh])
    db.commit()
    return upload

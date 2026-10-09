import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import config
from ..csv_parser import CSVParseError, parse_csv
from ..database import get_db
from ..ingest import ingest
from ..models import Upload, User
from ..schemas import IdIn
from ..security import current_user

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


def _out(u: Upload):
    return {"id": u.id, "filename": u.filename, "status": u.status, "total_rows": u.total_rows,
            "inserted": u.inserted, "duplicates": u.duplicates, "skipped": u.skipped,
            "errors": json.loads(u.error_report or "[]"), "message": u.message,
            "created_at": u.created_at.isoformat()}


@router.post("/create", status_code=201)
async def create_upload(file: UploadFile = File(...), db: Session = Depends(get_db),
                        user: User = Depends(current_user)):
    name = file.filename or "statement.csv"
    if not name.lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files are supported.")
    raw = await file.read(config.MAX_UPLOAD_BYTES + 1)  # never buffer more than limit+1 bytes
    if len(raw) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File is larger than {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    try:
        parsed = parse_csv(raw)
    except CSVParseError as e:
        db.add(Upload(user_id=user.id, filename=name[:255], status="failed", message=str(e)[:500]))
        db.commit()
        raise HTTPException(422, str(e))
    try:
        upload = ingest(db, user.id, name, parsed)
    except IntegrityError:  # two identical uploads racing; unique(user_id, hash) is the final guard
        db.rollback()
        raise HTTPException(409, "These transactions are already being imported. Refresh and check history.")
    return _out(upload)


@router.post("/list")
def list_uploads(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(Upload).filter(Upload.user_id == user.id).order_by(Upload.id.desc()).limit(100).all()
    return [_out(u) for u in rows]


@router.post("/delete")
def delete_upload(body: IdIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    u = db.query(Upload).filter(Upload.id == body.id, Upload.user_id == user.id).first()
    if not u:
        raise HTTPException(404, "Upload not found.")
    db.delete(u)  # cascades to its transactions
    db.commit()
    return {"ok": True}

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Transaction, User
from ..schemas import Filters
from ..security import current_user
from .dashboard import summary as dashboard_summary
from .transactions import apply_filters
from ..schemas import SummaryIn

router = APIRouter(prefix="/api/export", tags=["export"])
PDF_ROW_LIMIT = 1000


def safe_cell(v: str) -> str:
    """Neutralise CSV/Excel formula injection from untrusted bank narrations."""
    return "'" + v if v and v[0] in "=+-@\t\r" else v


def _query(db, user, f):
    return (apply_filters(db.query(Transaction), user.id, f).options(joinedload(Transaction.category))
            .order_by(Transaction.txn_date, Transaction.id))


@router.post("/csv")
def export_csv(body: Filters, db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = _query(db, user, body)

    def gen():
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Date", "Description", "Category", "Type", "Amount", "Balance"])
        yield buf.getvalue()
        for t in q.yield_per(1000):
            buf.seek(0); buf.truncate()
            w.writerow([t.txn_date.isoformat(), safe_cell(t.description), t.category.name, t.txn_type,
                        f"{t.amount:.2f}", "" if t.balance is None else f"{t.balance:.2f}"])
            yield buf.getvalue()

    return StreamingResponse(gen(), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="transactions.csv"'})


@router.post("/pdf")
def export_pdf(body: Filters, db: Session = Depends(get_db), user: User = Depends(current_user)):
    s = dashboard_summary(SummaryIn(start_date=body.start_date, end_date=body.end_date), db, user)
    rows = _query(db, user, body).limit(PDF_ROW_LIMIT + 1).all()
    st = getSampleStyleSheet()
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    period = f"{body.start_date or 'start'} to {body.end_date or 'latest'}"
    inr = lambda v: f"Rs. {v:,.2f}"
    grid = TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e1b4b")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                       ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                       ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f9")])])
    el = [Paragraph("Spending report", st["Title"]), Paragraph(f"{user.name} | {period} | generated {datetime.now():%d %b %Y}", st["Normal"]),
          Spacer(1, 8 * mm)]
    t1 = Table([["Total spent", "Total income", "Net", "Transactions"],
                [inr(s["total_spent"]), inr(s["total_income"]), inr(s["net"]), str(s["transaction_count"])]])
    t1.setStyle(grid)
    el += [t1, Spacer(1, 6 * mm), Paragraph("Spending by category", st["Heading2"])]
    t2 = Table([["Category", "Spent", "Share", "Count"]] + [[c["category"], inr(c["spent"]), f'{c["percent"]}%', c["count"]] for c in s["categories"]], repeatRows=1)
    t2.setStyle(grid)
    el += [t2, Spacer(1, 6 * mm), Paragraph("Transactions", st["Heading2"])]
    data = [["Date", "Description", "Category", "Type", "Amount"]] + [
        [t.txn_date.isoformat(), t.description[:48], t.category.name, t.txn_type, f"{t.amount:,.2f}"] for t in rows[:PDF_ROW_LIMIT]]
    t3 = Table(data, repeatRows=1, colWidths=[22 * mm, 68 * mm, 32 * mm, 16 * mm, 26 * mm])
    t3.setStyle(grid)
    el.append(t3)
    if len(rows) > PDF_ROW_LIMIT:
        el.append(Paragraph(f"Showing the first {PDF_ROW_LIMIT} transactions. Use the CSV export for the full list.", st["Italic"]))
    doc.build(el)
    return Response(out.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="spending-report.pdf"'})

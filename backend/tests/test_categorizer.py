from app.categorizer import Categorizer, seed_categories
from app.database import Base, SessionLocal, engine
from app.models import Category, User


def test_system_user_priority_and_fallbacks():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_categories(db)
        u = User(email="a@b.com", name="A", password_hash="x")
        db.add(u)
        db.commit()
        mine = Category(user_id=u.id, name="Coffee", keywords="starbucks")
        db.add(mine)
        db.commit()
        c = Categorizer(db, u.id)
        name = lambda cid: db.get(Category, cid).name
        assert name(c.categorize("UPI-SWIGGY ORDER", "debit")) == "Food & Dining"
        assert name(c.categorize("STARBUCKS MG ROAD", "debit")) == "Coffee"  # user rule beats system rule
        assert name(c.categorize("random merchant", "debit")) == "Uncategorized"
        assert name(c.categorize("random deposit", "credit")) == "Income"

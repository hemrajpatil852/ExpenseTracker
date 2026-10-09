"""Rule-based categorisation. User keywords are checked before system keywords."""
from sqlalchemy.orm import Session

from .models import Category

DEFAULT_CATEGORIES = {
    "Groceries": "bigbasket,blinkit,zepto,dmart,d-mart,grofers,jiomart,instamart,reliance fresh,more retail,supermarket,kirana,vegetable",
    "Food & Dining": "swiggy,zomato,restaurant,cafe,dominos,domino,mcdonald,kfc,pizza,starbucks,burger,bakery,eatsure,dining",
    "Transport": "uber,ola,rapido,irctc,redbus,metro,fastag,petrol,diesel,fuel,indian oil,hpcl,bpcl,shell,makemytrip,indigo,air india,cab",
    "Utilities": "electricity,bescom,mseb,msedcl,tata power,adani electricity,water bill,gas,mahanagar,airtel,jio,vodafone,vi prepaid,bsnl,recharge,broadband,act fibernet,dth,tatasky,bill payment,billdesk",
    "Shopping": "amazon,flipkart,myntra,ajio,meesho,nykaa,croma,decathlon,lifestyle,pantaloons,shoppers stop,ikea",
    "Entertainment": "bookmyshow,netflix,hotstar,spotify,prime video,youtube,pvr,inox,gaming,sonyliv,zee5",
    "Health": "pharmacy,apollo,medplus,netmeds,1mg,pharmeasy,hospital,clinic,diagnostic,lab,doctor,practo",
    "Rent & Housing": "rent,maintenance,society,nobroker,housing",
    "EMI & Loans": "emi,loan,credit card,hdfc card,sbi card,lic,insurance premium,mutual fund,sip,zerodha,groww",
    "Education": "school,college,tuition,udemy,coursera,byju,unacademy,fees,exam",
    "Cash Withdrawal": "atm,cash wdl,cash withdrawal,nwd",
    "Transfers": "neft,imps,rtgs,self transfer",
    "Income": "salary,interest credit,int.pd,dividend,refund,cashback,reversal,payroll",
    "Uncategorized": "",
}
FALLBACK_DEBIT = "Uncategorized"
FALLBACK_CREDIT = "Income"


def seed_categories(db: Session):
    existing = {c.name for c in db.query(Category).filter(Category.user_id.is_(None))}
    for name, kw in DEFAULT_CATEGORIES.items():
        if name not in existing:
            db.add(Category(user_id=None, name=name, keywords=kw))
    db.commit()


class Categorizer:
    def __init__(self, db: Session, user_id: int):
        cats = db.query(Category).filter((Category.user_id.is_(None)) | (Category.user_id == user_id)).all()
        ordered = sorted(cats, key=lambda c: c.user_id is None)  # user categories first
        self.rules = [(c.id, [k.strip() for k in c.keywords.split(",") if k.strip()]) for c in ordered]
        sysmap = {c.name: c.id for c in cats if c.user_id is None}
        self.debit_default, self.credit_default = sysmap[FALLBACK_DEBIT], sysmap[FALLBACK_CREDIT]

    def categorize(self, description: str, txn_type: str) -> int:
        text = description.lower()
        for cid, kws in self.rules:
            if any(k in text for k in kws):
                return cid
        return self.credit_default if txn_type == "credit" else self.debit_default

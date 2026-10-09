from datetime import datetime

from sqlalchemy import (BigInteger, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    password_hash = Column(String(128), nullable=False)
    token_version = Column(Integer, default=0, nullable=False)  # bump to revoke all tokens (logout)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Category(Base):
    """user_id NULL = system category shared by everyone; otherwise a user's custom category."""
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(60), nullable=False)
    keywords = Column(Text, default="", nullable=False)  # comma separated, lowercase
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_category_user_name"),)


class Upload(Base):
    __tablename__ = "uploads"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="completed")  # completed | failed
    total_rows = Column(Integer, default=0)
    inserted = Column(Integer, default=0)
    duplicates = Column(Integer, default=0)
    skipped = Column(Integer, default=0)
    error_report = Column(Text, default="[]")  # JSON list of {row, reason}
    message = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    transactions = relationship("Transaction", cascade="all, delete-orphan", passive_deletes=True)


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    upload_id = Column(Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    txn_date = Column(Date, nullable=False)
    description = Column(String(500), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)  # always positive; direction lives in txn_type
    txn_type = Column(String(6), nullable=False)  # debit | credit
    balance = Column(Numeric(14, 2), nullable=True)
    dedupe_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    category = relationship("Category")
    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_hash", name="uq_txn_user_hash"),
        Index("ix_txn_user_date", "user_id", "txn_date"),
    )

class Budget(Base):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    monthly_limit = Column(Numeric(14, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    category = relationship("Category")
    __table_args__ = (UniqueConstraint("user_id", "category_id", name="uq_budget_user_cat"),)
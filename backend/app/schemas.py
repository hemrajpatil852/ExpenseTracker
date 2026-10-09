import re
from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class SignupIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def strong(cls, v):
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must contain at least one letter and one number.")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=72)


class RefreshIn(BaseModel):
    refresh_token: str


class Filters(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    category_id: Optional[int] = None
    txn_type: Optional[str] = Field(default=None, pattern="^(debit|credit)$")
    search: Optional[str] = Field(default=None, max_length=100)


class TxnListIn(Filters):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)


class SummaryIn(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    group_by: str = Field(default="month", pattern="^(day|week|month)$")


class UpdateCategoryIn(BaseModel):
    transaction_id: int
    category_id: int


class CategoryCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    keywords: list[str] = []
    reapply: bool = True


class IdIn(BaseModel):
    id: int

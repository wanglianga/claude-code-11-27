from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str
    password: str


class CompareIn(BaseModel):
    product_id: int
    need_type: str = Field(pattern="^(gross|net)$")
    need_quantity: float = Field(gt=0)
    grade: Optional[str] = None
    origin: Optional[str] = None
    deliverable_by: Optional[date] = None


class DecisionIn(BaseModel):
    quote_id: int
    need_type: str = Field(pattern="^(gross|net)$")
    need_quantity: float = Field(gt=0)


class CorrectIn(BaseModel):
    new_quote_id: int


class AcceptanceIn(BaseModel):
    trip_no: str
    received_weight_kg: float = Field(ge=0)
    actual_unit_price: Optional[float] = None
    actual_grade: Optional[str] = None
    returned_weight_kg: float = 0
    grade_rejected_weight_kg: float = 0
    actual_yield: Optional[float] = Field(default=None, ge=0, le=1)
    note: Optional[str] = None


class MappingApproveIn(BaseModel):
    product_id: int
    note: Optional[str] = None


class MappingRejectIn(BaseModel):
    note: Optional[str] = None


class ReparseIn(BaseModel):
    column_mapping: Optional[dict[str, str]] = None
    unit_table: Optional[dict[str, str]] = None


class YieldRateIn(BaseModel):
    product_id: int
    from_state: str
    to_state: str = "净菜"
    lower: float = Field(gt=0, le=1)
    upper: float = Field(gt=0, le=1)
    evidence: Optional[str] = None


class ImportOut(BaseModel):
    id: int
    filename: Optional[str]
    kind: str
    status: str
    total_rows: int
    ok_rows: int
    bad_rows: int
    revision: int
    parent_batch_id: Optional[int]

    class Config:
        from_attributes = True

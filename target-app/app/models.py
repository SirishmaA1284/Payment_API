from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    amount: float = Field(..., ge=0)
    tax: float = Field(..., ge=0)
    discount: float = Field(..., ge=0)


class PaymentResponse(BaseModel):
    id: int
    amount: float
    tax: float
    discount: float
    total: float

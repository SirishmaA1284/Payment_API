from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileResponse(BaseModel):
    username: str
    display_name: str


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

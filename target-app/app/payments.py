from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user
from app.database import create_payment, get_payment
from app.models import PaymentCreate, PaymentResponse

router = APIRouter()


@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment_endpoint(
    payment: PaymentCreate, username: str = Depends(get_current_user)
) -> PaymentResponse:
    total = payment.amount + payment.tax - payment.discount
    payment_id = create_payment(payment.amount, payment.tax, payment.discount, total)
    return PaymentResponse(
        id=payment_id,
        amount=payment.amount,
        tax=payment.tax,
        discount=payment.discount,
        total=total,
    )


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
def get_payment_endpoint(payment_id: int, username: str = Depends(get_current_user)) -> PaymentResponse:
    row = get_payment(payment_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return PaymentResponse(**dict(row))

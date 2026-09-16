"""Recipients router — full CRUD operations (Phase 1)."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_models import Recipient
from app.schemas import RecipientCreate, RecipientRead, RecipientUpdate

router = APIRouter()


@router.get("", response_model=List[RecipientRead])
def list_recipients(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Return all recipients."""
    recipients = db.query(Recipient).offset(skip).limit(limit).all()
    return recipients


@router.post("", response_model=RecipientRead, status_code=201)
def create_recipient(payload: RecipientCreate, db: Session = Depends(get_db)):
    """Create a new recipient."""
    recipient = Recipient(**payload.model_dump())
    db.add(recipient)
    db.commit()
    db.refresh(recipient)
    return recipient


@router.put("/{recipient_id}", response_model=RecipientRead)
def update_recipient(
    recipient_id: int, payload: RecipientUpdate, db: Session = Depends(get_db)
):
    """Update an existing recipient by ID."""
    recipient = db.query(Recipient).filter(Recipient.id == recipient_id).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(recipient, field, value)

    db.commit()
    db.refresh(recipient)
    return recipient

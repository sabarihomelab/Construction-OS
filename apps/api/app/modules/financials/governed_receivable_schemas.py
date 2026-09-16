from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class GovernedClientInvoiceFromRABillCreate(BaseModel):
    source_ra_bill_id: UUID
    invoice_date: date
    due_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)

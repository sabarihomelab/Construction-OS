from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class BOQMeasurementControlLine(BaseModel):
    boq_item_id: UUID
    boq_id: UUID
    wbs_code_id: UUID | None
    line_number: int
    item_code: str
    description: str
    unit_code: str
    boq_quantity: Decimal
    boq_rate: Decimal
    boq_amount: Decimal
    measured_quantity: Decimal
    submitted_quantity: Decimal
    certified_quantity: Decimal
    billed_quantity: Decimal
    paid_quantity: Decimal
    certified_value: Decimal
    billed_value: Decimal
    paid_value: Decimal
    remaining_to_certify: Decimal
    remaining_to_bill: Decimal


class BOQMeasurementControlSummary(BaseModel):
    project_id: UUID
    currency_code: str
    total_boq_value: Decimal
    total_certified_value: Decimal
    total_billed_value: Decimal
    total_paid_value: Decimal
    lines: list[BOQMeasurementControlLine]

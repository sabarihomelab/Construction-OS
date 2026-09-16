from datetime import UTC, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commercial.models import RABill
from app.modules.configuration.schemas import ResolvedConfigurationSetting
from app.modules.configuration.service import resolve_effective_configuration
from app.modules.financials.models import ClientInvoice
from app.modules.financials.receivable_service import create_client_invoice_from_ra_bill
from app.modules.financials.rule_models import FinancialRuleSnapshot
from app.modules.financials.service import FinancialValidationError


GST_RULE_KEY = "financials.client_invoice.gst_rule"
WITHHOLDING_RULE_KEY = "financials.client_invoice.withholding_rule"
MONEY = Decimal("0.01")
HUNDRED = Decimal("100")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _rule_payload(setting: ResolvedConfigurationSetting, *, key: str) -> dict[str, object]:
    if not isinstance(setting.value, dict):
        raise FinancialValidationError(f"Configured rule {key} must be a JSON object")
    payload = dict(setting.value)
    jurisdiction = str(payload.get("jurisdiction") or "").strip().upper()
    if not jurisdiction:
        raise FinancialValidationError(f"Configured rule {key} requires jurisdiction evidence")
    rate = Decimal(str(payload.get("rate_percent") or 0))
    if rate < 0 or rate > HUNDRED:
        raise FinancialValidationError(f"Configured rule {key} rate_percent must be between 0 and 100")
    payload["jurisdiction"] = jurisdiction
    payload["code"] = str(payload.get("code") or "").strip().upper()
    payload["rate_percent"] = str(rate)
    payload["source_reference"] = str(payload.get("source_reference") or "").strip()
    return payload


def _setting_by_key(settings: list[ResolvedConfigurationSetting], key: str) -> ResolvedConfigurationSetting:
    for setting in settings:
        if setting.key == key:
            return setting
    raise FinancialValidationError(f"Effective configuration did not resolve required rule {key}")


async def create_governed_client_invoice_from_ra_bill(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: dict[str, object],
    membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> ClientInvoice:
    invoice_date = values.get("invoice_date")
    if invoice_date is None:
        raise FinancialValidationError("Invoice date is required")
    as_of = datetime.combine(invoice_date, time.min, tzinfo=UTC)
    effective = await resolve_effective_configuration(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        module_key="financials",
        project_id=project_id,
        as_of=as_of,
    )
    gst_setting = _setting_by_key(effective.settings, GST_RULE_KEY)
    withholding_setting = _setting_by_key(effective.settings, WITHHOLDING_RULE_KEY)
    gst_rule = _rule_payload(gst_setting, key=GST_RULE_KEY)
    withholding_rule = _rule_payload(withholding_setting, key=WITHHOLDING_RULE_KEY)

    ra_bill_id = values.get("source_ra_bill_id")
    if not isinstance(ra_bill_id, UUID):
        raise FinancialValidationError("Certified RA bill is required")
    ra_bill = await db.scalar(
        select(RABill).where(
            RABill.id == ra_bill_id,
            RABill.organization_id == organization_id,
            RABill.project_id == project_id,
        )
    )
    if ra_bill is None:
        raise FinancialValidationError("RA bill was not found")

    gst_rate = Decimal(str(gst_rule["rate_percent"]))
    withholding_rate = Decimal(str(withholding_rule["rate_percent"]))
    subtotal = _money(Decimal(ra_bill.gross_amount))
    tax_amount = _money(subtotal * gst_rate / HUNDRED)
    withholding_basis = str(withholding_rule.get("basis") or "subtotal").strip().lower()
    if withholding_basis == "subtotal":
        withholding_base = subtotal
    elif withholding_basis == "total_including_tax":
        withholding_base = _money(subtotal + tax_amount)
    else:
        raise FinancialValidationError(
            "Configured client withholding basis must be subtotal or total_including_tax"
        )
    withholding_amount = _money(withholding_base * withholding_rate / HUNDRED)

    service_values = dict(values)
    service_values["tax_code"] = gst_rule.get("code") or None
    service_values["tax_rate"] = gst_rate
    service_values["withholding_amount"] = withholding_amount
    invoice = await create_client_invoice_from_ra_bill(
        db,
        organization_id=organization_id,
        project_id=project_id,
        values=service_values,
        membership_id=membership_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )

    applied_at = datetime.now(UTC)
    for setting, payload in (
        (gst_setting, gst_rule),
        (withholding_setting, withholding_rule),
    ):
        db.add(
            FinancialRuleSnapshot(
                organization_id=organization_id,
                project_id=project_id,
                entity_type="client_invoice",
                entity_id=invoice.id,
                rule_key=setting.key,
                source=setting.source,
                version=setting.version,
                effective_from=setting.effective_from,
                applied_at=applied_at,
                snapshot_json={
                    "rule": payload,
                    "configuration_source": setting.source,
                    "configuration_version": setting.version,
                    "effective_from": (
                        setting.effective_from.isoformat() if setting.effective_from else None
                    ),
                    "resolved_as_of": as_of.isoformat(),
                },
            )
        )
    await db.flush()
    return invoice

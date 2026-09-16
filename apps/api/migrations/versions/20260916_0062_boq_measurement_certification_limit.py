"""Enforce cumulative certified measurement against BOQ quantity.

Revision ID: 20260916_0062
Revises: 20260916_0061
Create Date: 2026-09-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260916_0062"
down_revision: str | None = "20260916_0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION enforce_boq_certified_measurement_limit()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            boq_quantity numeric;
            already_certified numeric;
        BEGIN
            IF NEW.status = 'certified' AND OLD.status IS DISTINCT FROM 'certified' THEN
                SELECT quantity
                  INTO boq_quantity
                  FROM project_boq_items
                 WHERE id = NEW.boq_item_id
                   AND project_id = NEW.project_id
                   AND organization_id = NEW.organization_id
                 FOR SHARE;

                IF boq_quantity IS NULL THEN
                    RAISE EXCEPTION 'BOQ item was not found for measurement certification';
                END IF;

                SELECT COALESCE(SUM(quantity), 0)
                  INTO already_certified
                  FROM measurement_entries
                 WHERE boq_item_id = NEW.boq_item_id
                   AND project_id = NEW.project_id
                   AND organization_id = NEW.organization_id
                   AND id <> NEW.id
                   AND status = 'certified';

                IF already_certified + NEW.quantity > boq_quantity THEN
                    RAISE EXCEPTION
                        'Cumulative certified measurement quantity (%) exceeds approved BOQ quantity (%)',
                        already_certified + NEW.quantity,
                        boq_quantity;
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_boq_certified_measurement_limit
        BEFORE UPDATE OF status ON measurement_entries
        FOR EACH ROW
        EXECUTE FUNCTION enforce_boq_certified_measurement_limit();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_boq_certified_measurement_limit ON measurement_entries")
    op.execute("DROP FUNCTION IF EXISTS enforce_boq_certified_measurement_limit()")

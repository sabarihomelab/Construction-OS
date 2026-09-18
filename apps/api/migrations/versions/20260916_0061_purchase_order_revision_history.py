"""Add immutable purchase order issue revision history.

Revision ID: 20260916_0061
Revises: 20260916_0060
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260916_0061"
down_revision: str | None = "20260916_0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "purchase_order_revisions",
        sa.Column("purchase_order_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("superseded_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["purchase_order_id", "project_id", "organization_id"],
            ["purchase_orders.id", "purchase_orders.project_id", "purchase_orders.organization_id"],
            name="fk_purchase_order_revisions_po_scope",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("purchase_order_id", "version_number"),
        sa.UniqueConstraint(
            "purchase_order_id",
            "version_number",
            name="uq_purchase_order_revisions_version",
        ),
        sa.CheckConstraint("version_number >= 1", name="ck_purchase_order_revisions_version"),
    )
    op.create_index(
        "ix_purchase_order_revisions_project_id",
        "purchase_order_revisions",
        ["project_id"],
    )
    op.create_index(
        "ix_purchase_order_revisions_organization_id",
        "purchase_order_revisions",
        ["organization_id"],
    )

    op.execute(
        """
        CREATE FUNCTION capture_purchase_order_issue_revision()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            next_version integer;
            line_snapshot jsonb;
        BEGIN
            IF NEW.status = 'issued' AND OLD.status IS DISTINCT FROM 'issued' THEN
                SELECT COALESCE(MAX(version_number), 0) + 1
                  INTO next_version
                  FROM purchase_order_revisions
                 WHERE purchase_order_id = NEW.id;

                SELECT COALESCE(
                    jsonb_agg(
                        jsonb_build_object(
                            'id', line.id,
                            'line_number', line.line_number,
                            'requisition_line_id', line.requisition_line_id,
                            'material_id', line.material_id,
                            'wbs_code_id', line.wbs_code_id,
                            'boq_item_id', line.boq_item_id,
                            'description', line.description,
                            'unit_code', line.unit_code,
                            'quantity', line.quantity,
                            'unit_price', line.unit_price,
                            'taxable_value', line.taxable_value,
                            'hsn_sac', line.hsn_sac,
                            'tax_code', line.tax_code,
                            'tax_rate', line.tax_rate,
                            'tax_amount', line.tax_amount,
                            'line_total', line.line_total,
                            'notes', line.notes
                        )
                        ORDER BY line.line_number
                    ),
                    '[]'::jsonb
                )
                  INTO line_snapshot
                  FROM purchase_order_lines AS line
                 WHERE line.purchase_order_id = NEW.id;

                INSERT INTO purchase_order_revisions (
                    purchase_order_id,
                    version_number,
                    organization_id,
                    project_id,
                    issued_at,
                    approved_by_membership_id,
                    snapshot_json
                )
                VALUES (
                    NEW.id,
                    next_version,
                    NEW.organization_id,
                    NEW.project_id,
                    NEW.issued_at,
                    NEW.approved_by_membership_id,
                    jsonb_build_object(
                        'purchase_order', jsonb_build_object(
                            'id', NEW.id,
                            'number', NEW.number,
                            'supplier_party_id', NEW.supplier_party_id,
                            'requisition_id', NEW.requisition_id,
                            'status', NEW.status,
                            'order_date', NEW.order_date,
                            'expected_delivery_date', NEW.expected_delivery_date,
                            'currency_code', NEW.currency_code,
                            'subtotal', NEW.subtotal,
                            'tax_total', NEW.tax_total,
                            'total', NEW.total,
                            'revision', NEW.revision,
                            'approved_by_membership_id', NEW.approved_by_membership_id,
                            'approved_at', NEW.approved_at,
                            'issued_at', NEW.issued_at,
                            'notes', NEW.notes
                        ),
                        'lines', line_snapshot
                    )
                );
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_purchase_order_issue_revision
        AFTER UPDATE OF status ON purchase_orders
        FOR EACH ROW
        EXECUTE FUNCTION capture_purchase_order_issue_revision();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_purchase_order_issue_revision ON purchase_orders")
    op.execute("DROP FUNCTION IF EXISTS capture_purchase_order_issue_revision()")
    op.drop_index("ix_purchase_order_revisions_organization_id", table_name="purchase_order_revisions")
    op.drop_index("ix_purchase_order_revisions_project_id", table_name="purchase_order_revisions")
    op.drop_table("purchase_order_revisions")

from uuid import uuid4

from app.modules.commercial.models import RecordStatus, WBSCode, WBSKind
from app.modules.commercial.wbs_service import flatten_wbs_tree


def _row(code: str, *, parent_id=None, status=RecordStatus.ACTIVE) -> WBSCode:
    return WBSCode(
        id=uuid4(),
        organization_id=uuid4(),
        project_id=uuid4(),
        parent_id=parent_id,
        code=code,
        name=code,
        kind=WBSKind.COST_CODE,
        status=status,
        revision=1,
    )


def test_wbs_tree_has_no_delete_semantics_and_retains_inactive_rows() -> None:
    root = _row("CIV", status=RecordStatus.INACTIVE)
    child = _row("CIV.CONC", parent_id=root.id)
    child.organization_id = root.organization_id
    child.project_id = root.project_id

    flattened = flatten_wbs_tree([child, root])

    assert [row.id for row, *_ in flattened] == [root.id, child.id]
    assert flattened[0][0].status == RecordStatus.INACTIVE
    assert flattened[1][1] == 1

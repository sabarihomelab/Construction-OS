def register_builtin_search_providers() -> None:
    # Imports intentionally register each provider with the shared registry.
    from app.modules.commercial import search as _commercial  # noqa: F401
    from app.modules.documents import search_provider as _documents  # noqa: F401
    from app.modules.drawings import search as _drawings  # noqa: F401
    from app.modules.equipment import search as _equipment  # noqa: F401
    from app.modules.estimating import search as _estimating  # noqa: F401
    from app.modules.field import search as _field  # noqa: F401
    from app.modules.financials import search as _financials  # noqa: F401
    from app.modules.meetings import search as _meetings  # noqa: F401
    from app.modules.procurement import search as _procurement  # noqa: F401
    from app.modules.projects import search as _projects  # noqa: F401
    from app.modules.rfis import search as _rfis  # noqa: F401
    from app.modules.safety import search as _safety  # noqa: F401
    from app.modules.scheduling import search as _scheduling  # noqa: F401
    from app.modules.subcontracts import search as _subcontracts  # noqa: F401
    from app.modules.submittals import search as _submittals  # noqa: F401
    from app.modules.workforce import search as _workforce  # noqa: F401

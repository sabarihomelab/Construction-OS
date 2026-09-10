def register_builtin_search_providers() -> None:
    # Imports intentionally register each provider with the shared registry.
    from app.modules.documents import search_provider as _documents  # noqa: F401
    from app.modules.drawings import search as _drawings  # noqa: F401
    from app.modules.field import search as _field  # noqa: F401
    from app.modules.projects import search as _projects  # noqa: F401
    from app.modules.rfis import search as _rfis  # noqa: F401
    from app.modules.submittals import search as _submittals  # noqa: F401

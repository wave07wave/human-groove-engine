GLOBAL_PREFERENCE_SCOPE = "__global__"


def normalize_preference_scope(value: str | None) -> str:
    """Return a stable storage key while keeping user-visible preset names intact."""
    normalized = (value or "").strip()
    return normalized or GLOBAL_PREFERENCE_SCOPE

from __future__ import annotations


def is_ynab_system_category(
    group_name: str | None,
    category_name: str | None,
) -> bool:
    """Return true for YNAB-maintained categories Finclaide should not manage."""
    normalized_group = (group_name or "").strip().lower()
    normalized_category = (category_name or "").strip().lower()
    return (
        normalized_group == "internal master category"
        or normalized_category == "uncategorized"
        or normalized_category.startswith("inflow:")
    )

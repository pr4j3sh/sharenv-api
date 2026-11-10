"""Pagination helpers for list endpoints."""

from __future__ import annotations

from fastapi import Response


def set_pagination_headers(
    response: Response,
    *,
    total: int,
    limit: int,
    offset: int,
    item_count: int,
) -> None:
    """Expose pagination metadata without changing list response bodies."""
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Offset"] = str(offset)

    next_offset = offset + item_count
    if next_offset < total:
        response.headers["X-Next-Offset"] = str(next_offset)

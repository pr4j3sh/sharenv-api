from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query, Response

from app.core.config import settings


class PaginationParams:
    def __init__(
        self,
        limit: Annotated[
            int, Query(ge=1, le=settings.PAGINATION_MAX_LIMIT)
        ] = settings.PAGINATION_DEFAULT_LIMIT,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


def set_pagination_headers(
    response: Response,
    *,
    total: int,
    limit: int,
    offset: int,
    item_count: int,
) -> None:
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Offset"] = str(offset)

    next_offset = offset + item_count
    if next_offset < total:
        response.headers["X-Next-Offset"] = str(next_offset)


PaginationDep = Annotated[PaginationParams, Depends(PaginationParams)]

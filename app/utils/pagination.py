"""
utils/pagination.py
Reusable pagination helpers for all list API endpoints.
"""

from dataclasses import dataclass
from typing import TypeVar, Generic, List
from fastapi import Query

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE     = 100

T = TypeVar("T")


@dataclass
class PaginationParams:
    """Holds validated page and page_size values from a request."""
    page:      int
    page_size: int

    @property
    def offset(self) -> int:
        """SQL OFFSET value — rows to skip before returning results."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """SQL LIMIT value — max rows to return."""
        return self.page_size


@dataclass
class PaginatedResponse(Generic[T]):
    """Standard paginated response envelope returned by list endpoints."""
    items:       List[T]
    total:       int
    page:        int
    page_size:   int
    total_pages: int
    has_next:    bool
    has_prev:    bool


def get_pagination_params(
    page: int = Query(
        default=1,
        ge=1,
        description="Page number, 1-indexed.",
    ),
    page_size: int = Query(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=f"Items per page. Max {MAX_PAGE_SIZE}.",
    ),
) -> PaginationParams:
    """
    FastAPI dependency that extracts and validates pagination query params.

    Usage in a route:
        @router.get("/items")
        async def list_items(
            params: PaginationParams = Depends(get_pagination_params)
        ):
            ...
    """
    return PaginationParams(page=page, page_size=page_size)


def make_paginated_response(
    items: list,
    total: int,
    params: PaginationParams,
) -> PaginatedResponse:
    """
    Wraps a list of ORM objects or dicts in a PaginatedResponse.

    Args:
        items:  The slice of items for the current page (already fetched).
        total:  The total count of ALL matching items across all pages.
        params: The PaginationParams for the current request.

    Returns a PaginatedResponse with total_pages, has_next,
    and has_prev computed automatically.
    total_pages is always at least 1 even when total == 0.
    """
    total_pages = max(1, -(-total // params.page_size))  # ceiling division
    return PaginatedResponse(
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages,
        has_next=params.page < total_pages,
        has_prev=params.page > 1,
    )

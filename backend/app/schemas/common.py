"""Common Pydantic schema utilities, pagination, and response envelopes."""

from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standardized API response envelope."""
    success: bool = Field(True, description="Indicates successful execution")
    message: Optional[str] = Field(None, description="Human readable message")
    data: Optional[T] = Field(None, description="Response payload")


class PaginationParams(BaseModel):
    """Pagination query parameters."""
    page: int = Field(1, ge=1, description="Page number starting from 1")
    page_size: int = Field(20, ge=1, le=100, description="Number of items per page")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response metadata and items."""
    items: List[T] = Field(..., description="List of items for current page")
    total: int = Field(..., description="Total count of items matching filter")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total pages available")

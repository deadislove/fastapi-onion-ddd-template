"""Shared pagination query-parameter constraints for list endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import Query

SkipParam = Annotated[int, Query(ge=0, description="Number of records to skip.")]
LimitParam = Annotated[int, Query(ge=1, le=100, description="Max records to return (1-100).")]

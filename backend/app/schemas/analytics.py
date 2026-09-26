"""Analytics and KPI schemas."""

from typing import Dict, List
from pydantic import BaseModel, Field


class CategoryBreakdownItem(BaseModel):
    category: str
    count: int
    percentage: float


class StatusBreakdownItem(BaseModel):
    status: str
    count: int


class SLAComplianceStats(BaseModel):
    total_resolved: int
    resolved_within_sla: int
    sla_breaches: int
    compliance_rate: float


class AnalyticsSummary(BaseModel):
    total_tickets: int
    active_tickets: int
    resolved_tickets: int
    avg_resolution_hours: float
    category_breakdown: List[CategoryBreakdownItem] = Field(default_factory=list)
    status_breakdown: List[StatusBreakdownItem] = Field(default_factory=list)
    sla_compliance: SLAComplianceStats

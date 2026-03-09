from dataclasses import dataclass
from datetime import date
from typing import Optional

from django.utils import timezone


@dataclass(frozen=True)
class DashboardFilters:
    month: Optional[date]
    start_date: Optional[date]
    end_date: Optional[date]
    category: Optional[str]
    payment_mode: Optional[str]
    sort: str


SORT_MAP = {
    "amount_desc": "-amount",
    "amount_asc": "amount",
    "date_desc": "-date",
    "date_asc": "date",
}


def _parse_month(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        year, month = value.split("-")
        return date(int(year), int(month), 1)
    except Exception:
        return None


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except Exception:
        return None


def parse_filters(request) -> DashboardFilters:
    month = _parse_month(request.GET.get("month"))
    start_date = _parse_date(request.GET.get("start"))
    end_date = _parse_date(request.GET.get("end"))
    category = request.GET.get("category") or None
    payment_mode = request.GET.get("payment") or None
    sort = request.GET.get("sort") or "date_desc"

    if sort not in SORT_MAP:
        sort = "date_desc"

    return DashboardFilters(
        month=month,
        start_date=start_date,
        end_date=end_date,
        category=category if category not in ("all", "") else None,
        payment_mode=payment_mode if payment_mode not in ("all", "") else None,
        sort=sort,
    )


def apply_filters(queryset, filters: DashboardFilters):
    if filters.month:
        queryset = queryset.filter(date__year=filters.month.year, date__month=filters.month.month)
    if filters.start_date:
        queryset = queryset.filter(date__gte=filters.start_date)
    if filters.end_date:
        queryset = queryset.filter(date__lte=filters.end_date)
    if filters.category:
        queryset = queryset.filter(category=filters.category)
    if filters.payment_mode:
        queryset = queryset.filter(payment_mode=filters.payment_mode)
    return queryset


def apply_sort(queryset, filters: DashboardFilters):
    return queryset.order_by(SORT_MAP.get(filters.sort, "-date"))


def resolve_budget_month(filters: DashboardFilters) -> date:
    if filters.month:
        return filters.month
    if filters.end_date:
        return date(filters.end_date.year, filters.end_date.month, 1)
    if filters.start_date:
        return date(filters.start_date.year, filters.start_date.month, 1)
    today = timezone.localdate()
    return date(today.year, today.month, 1)

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, List, Tuple

from django.db.models import Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from tracker.models import CategoryBudget, MonthlyBudget, Transaction


CATEGORY_LABELS = dict(Transaction.CATEGORY_CHOICES)


@dataclass
class Totals:
    total_income: float
    total_expense: float
    balance: float
    online_balance: float
    cash_balance: float


@dataclass
class BudgetSummary:
    total_budget: float
    spent: float
    remaining: float
    used_percent: float
    display_percent: float
    status: str  # ok | warning | over | unset


def aggregate_totals(queryset) -> Totals:
    agg = queryset.aggregate(
        total_income=Sum("amount", filter=Q(type="income")),
        total_expense=Sum("amount", filter=Q(type="expense")),
        online_income=Sum("amount", filter=Q(type="income", payment_mode="online")),
        online_expense=Sum("amount", filter=Q(type="expense", payment_mode="online")),
        cash_income=Sum("amount", filter=Q(type="income", payment_mode="cash")),
        cash_expense=Sum("amount", filter=Q(type="expense", payment_mode="cash")),
    )

    total_income = agg["total_income"] or 0
    total_expense = agg["total_expense"] or 0
    online_balance = (agg["online_income"] or 0) - (agg["online_expense"] or 0)
    cash_balance = (agg["cash_income"] or 0) - (agg["cash_expense"] or 0)
    balance = total_income - total_expense

    return Totals(
        total_income=total_income,
        total_expense=total_expense,
        balance=balance,
        online_balance=online_balance,
        cash_balance=cash_balance,
    )


def category_expense_breakdown(queryset) -> List[Dict[str, float]]:
    expenses = (
        queryset.filter(type="expense")
        .values("category")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    total_expense = sum(item["total"] or 0 for item in expenses)
    breakdown = []
    for item in expenses:
        category = item["category"]
        amount = item["total"] or 0
        percent = (amount / total_expense * 100) if total_expense else 0
        breakdown.append({
            "category": category,
            "label": CATEGORY_LABELS.get(category, category.title()),
            "amount": amount,
            "percent": percent,
        })
    return breakdown


def build_category_chart_data(breakdown: Iterable[Dict[str, float]]):
    labels = [item["label"] for item in breakdown]
    values = [float(item["amount"]) for item in breakdown]
    return {"labels": labels, "values": values}


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _month_end(value: date) -> date:
    return date(value.year, value.month, monthrange(value.year, value.month)[1])


def last_n_months(anchor: date, count: int = 6) -> List[date]:
    months = []
    year = anchor.year
    month = anchor.month
    for _ in range(count):
        months.append(date(year, month, 1))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(months))


def build_monthly_trend(queryset, anchor: date, count: int = 6) -> Dict[str, List]:
    months = last_n_months(anchor, count=count)
    start = _month_start(months[0])
    end = _month_end(months[-1])

    data = (
        queryset.filter(type="expense", date__gte=start, date__lte=end)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )

    totals_by_month = {}
    for item in data:
        month_value = item["month"]
        if hasattr(month_value, "date"):
            month_value = month_value.date()
        totals_by_month[month_value] = float(item["total"] or 0)
    labels = [m.strftime("%b %Y") for m in months]
    values = [totals_by_month.get(m, 0) for m in months]
    return {"labels": labels, "values": values}


def build_income_expense_chart(totals: Totals) -> Dict[str, List]:
    return {
        "labels": ["Income", "Expense"],
        "values": [float(totals.total_income), float(totals.total_expense)],
    }


def build_budget_summary(user, month: date) -> BudgetSummary:
    budget = MonthlyBudget.objects.filter(user=user, month=month).first()
    total_budget = budget.total_amount if budget else 0
    spent = (
        Transaction.objects.filter(user=user, type="expense", date__year=month.year, date__month=month.month)
        .aggregate(total=Sum("amount"))
        .get("total")
        or 0
    )
    remaining = total_budget - spent
    used_percent = (spent / total_budget * 100) if total_budget else 0

    if not total_budget:
        status = "unset"
    elif spent > total_budget:
        status = "over"
    elif used_percent >= 80:
        status = "warning"
    else:
        status = "ok"

    return BudgetSummary(
        total_budget=total_budget,
        spent=spent,
        remaining=remaining,
        used_percent=used_percent,
        display_percent=min(used_percent, 100),
        status=status,
    )


def build_category_budget_rows(user, month: date) -> List[Dict]:
    budgets = {
        item["category"]: item["amount"]
        for item in CategoryBudget.objects.filter(user=user, month=month).values("category", "amount")
    }
    expenses = (
        Transaction.objects.filter(user=user, type="expense", date__year=month.year, date__month=month.month)
        .values("category")
        .annotate(total=Sum("amount"))
    )
    spent_map = {item["category"]: item["total"] or 0 for item in expenses}

    rows = []
    for category, label in CATEGORY_LABELS.items():
        budget_amount = budgets.get(category, 0)
        spent = spent_map.get(category, 0)
        percent = (spent / budget_amount * 100) if budget_amount else 0
        rows.append({
            "category": category,
            "label": label,
            "budget": budget_amount,
            "spent": spent,
            "remaining": budget_amount - spent,
            "percent": percent,
            "display_percent": min(percent, 100),
            "over": budget_amount > 0 and spent > budget_amount,
        })
    return rows


def compute_month_totals(user, month: date) -> Tuple[float, float]:
    totals = (
        Transaction.objects.filter(user=user, date__year=month.year, date__month=month.month)
        .aggregate(
            income=Sum("amount", filter=Q(type="income")),
            expense=Sum("amount", filter=Q(type="expense")),
        )
    )
    return (totals["income"] or 0, totals["expense"] or 0)


def compute_savings_rate(income: float, expense: float) -> float:
    if income <= 0:
        return 0
    return (income - expense) / income * 100


def _format_currency(amount: float) -> str:
    return f"₹{amount:,.2f}"


def month_delta(month: date, delta: int = -1) -> date:
    year = month.year
    month_num = month.month + delta
    while month_num <= 0:
        month_num += 12
        year -= 1
    while month_num > 12:
        month_num -= 12
        year += 1
    return date(year, month_num, 1)


def build_insights(user, month: date) -> List[Dict[str, str]]:
    current_income, current_expense = compute_month_totals(user, month)
    previous_month = month_delta(month, -1)
    prev_income, prev_expense = compute_month_totals(user, previous_month)

    def pct_change(current: float, previous: float):
        if previous == 0:
            return None
        return (current - previous) / previous * 100

    expense_change = pct_change(current_expense, prev_expense)
    income_change = pct_change(current_income, prev_income)
    savings_rate = compute_savings_rate(current_income, current_expense)

    top_category = (
        Transaction.objects.filter(
            user=user,
            type="expense",
            date__year=month.year,
            date__month=month.month,
        )
        .values("category")
        .annotate(total=Sum("amount"))
        .order_by("-total")
        .first()
    )

    top_label = CATEGORY_LABELS.get(top_category["category"], top_category["category"].title()) if top_category else None

    insights = []
    if prev_expense == 0 and current_expense == 0:
        insights.append({"tone": "neutral", "text": "No expenses recorded this or last month."})
    elif prev_expense == 0 and current_expense > 0:
        insights.append({
            "tone": "negative",
            "text": f"You spent {_format_currency(current_expense)} this month; no expenses last month.",
        })
    else:
        direction = "more" if expense_change > 0 else "less"
        insights.append({
            "tone": "negative" if expense_change > 0 else "positive",
            "text": f"You spent {abs(expense_change):.1f}% {direction} compared to last month.",
        })

    if prev_income == 0 and current_income == 0:
        insights.append({"tone": "neutral", "text": "No income recorded this or last month."})
    elif prev_income == 0 and current_income > 0:
        insights.append({
            "tone": "positive",
            "text": f"You earned {_format_currency(current_income)} this month; no income last month.",
        })
    else:
        direction = "more" if income_change > 0 else "less"
        insights.append({
            "tone": "positive" if income_change > 0 else "negative",
            "text": f"Your income was {abs(income_change):.1f}% {direction} than last month.",
        })

    insights.append({
        "tone": "neutral",
        "text": f"Savings rate is {savings_rate:.1f}% for {month.strftime('%B %Y')}.",
    })

    if top_label:
        insights.append({
            "tone": "neutral",
            "text": f"Highest spending category: {top_label}.",
        })
    else:
        insights.append({"tone": "neutral", "text": "No expense categories recorded yet."})

    return insights


def current_month() -> date:
    today = timezone.localdate()
    return date(today.year, today.month, 1)

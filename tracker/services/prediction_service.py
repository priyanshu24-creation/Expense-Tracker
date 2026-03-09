from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.db.models import Sum
from django.db.models.functions import TruncMonth

from tracker.models import SpendingPrediction, Transaction


@dataclass
class PredictionResult:
    month: date
    predicted_expense: float
    risk_level: str
    explanation: str


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _month_delta(month: date, delta: int) -> date:
    year = month.year
    month_num = month.month + delta
    while month_num <= 0:
        month_num += 12
        year -= 1
    while month_num > 12:
        month_num -= 12
        year += 1
    return date(year, month_num, 1)


def _get_threshold(name: str, default: float) -> float:
    return float(getattr(settings, name, default))


def get_monthly_expenses(user, months_back: int, end_month: date) -> Dict[date, float]:
    start_month = _month_delta(end_month, -(months_back - 1))
    qs = (
        Transaction.objects.filter(
            user=user,
            type="expense",
            date__gte=start_month,
            date__lte=_month_delta(end_month, 1),
        )
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )
    totals = {}
    for item in qs:
        month_value = item["month"]
        if hasattr(month_value, "date"):
            month_value = month_value.date()
        totals[_month_start(month_value)] = float(item["total"] or 0)
    return totals


def compute_growth_rates(months: List[date], totals: Dict[date, float]) -> List[float]:
    rates = []
    for idx in range(1, len(months)):
        prev_total = totals.get(months[idx - 1], 0)
        current_total = totals.get(months[idx], 0)
        if prev_total == 0:
            continue
        rates.append((current_total - prev_total) / prev_total)
    return rates


def predict_next_month(user, today: date, months_back: int = 6) -> Optional[PredictionResult]:
    months_back = max(3, min(months_back, 6))
    current_month = _month_start(today)
    history_months = [_month_delta(current_month, -i) for i in range(months_back - 1, -1, -1)]
    totals = get_monthly_expenses(user, months_back, current_month)
    available_totals = [totals.get(month, 0) for month in history_months]

    if sum(1 for value in available_totals if value > 0) < 2:
        return PredictionResult(
            month=_month_delta(current_month, 1),
            predicted_expense=0,
            risk_level="insufficient",
            explanation="Not enough history yet to predict next month.",
        )

    avg_expense = sum(available_totals) / len(available_totals)
    growth_rates = compute_growth_rates(history_months, totals)
    last_month_total = available_totals[-1]

    if growth_rates:
        avg_growth = sum(growth_rates) / len(growth_rates)
        predicted = max(0, last_month_total * (1 + avg_growth))
    else:
        predicted = max(0, avg_expense)

    return PredictionResult(
        month=_month_delta(current_month, 1),
        predicted_expense=predicted,
        risk_level="insufficient",
        explanation="Prediction based on your recent expense trend.",
    )


def classify_risk(user, today: date, average: float, prediction: float) -> Tuple[str, str]:
    overspend_projection_threshold = _get_threshold("PREDICTION_OVR_PROJ_THRESHOLD", 0.15)
    overspend_pace_threshold = _get_threshold("PREDICTION_OVR_PACE_THRESHOLD", 0.20)
    underspend_threshold = _get_threshold("PREDICTION_UNDER_THRESHOLD", 0.60)
    stable_threshold = _get_threshold("PREDICTION_STABLE_THRESHOLD", 0.10)

    current_month = _month_start(today)
    month_total = (
        Transaction.objects.filter(
            user=user,
            type="expense",
            date__year=current_month.year,
            date__month=current_month.month,
        )
        .aggregate(total=Sum("amount"))
        .get("total")
        or 0
    )
    last_month = _month_delta(current_month, -1)
    last_month_total = (
        Transaction.objects.filter(
            user=user,
            type="expense",
            date__year=last_month.year,
            date__month=last_month.month,
        )
        .aggregate(total=Sum("amount"))
        .get("total")
        or 0
    )

    # spending pace estimate
    days_elapsed = max(1, today.day)
    total_days = (_month_delta(current_month, 1) - current_month).days
    pace_projection = (month_total / days_elapsed) * total_days

    if last_month_total and prediction > last_month_total * (1 + overspend_projection_threshold):
        return "high", "Projected spending is rising faster than last month."
    if average and pace_projection > average * (1 + overspend_pace_threshold):
        return "high", "Current spending pace suggests overspending."
    if average and month_total < average * underspend_threshold:
        return "under", "Spending is well below your historical average."

    if average:
        deviation = abs(month_total - average) / average
        if deviation <= stable_threshold:
            return "healthy", "Spending is stable compared to your average."

    return "healthy", "Spending is within a healthy range."


def save_prediction(user, result: PredictionResult) -> SpendingPrediction:
    prediction, _ = SpendingPrediction.objects.update_or_create(
        user=user,
        month=result.month,
        defaults={
            "predicted_expense": result.predicted_expense,
            "risk_level": result.risk_level,
        },
    )
    return prediction


def build_prediction_summary(user, today: date) -> PredictionResult:
    current_month = _month_start(today)
    history = get_monthly_expenses(user, 6, current_month)
    avg_expense = sum(history.values()) / len(history) if history else 0
    prediction = predict_next_month(user, today)
    if not prediction:
        return PredictionResult(
            month=_month_delta(current_month, 1),
            predicted_expense=0,
            risk_level="insufficient",
            explanation="Not enough data to forecast next month.",
        )
    risk_level, explanation = classify_risk(user, today, avg_expense, prediction.predicted_expense)
    prediction.risk_level = risk_level
    prediction.explanation = explanation
    save_prediction(user, prediction)
    return prediction

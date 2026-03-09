from calendar import monthrange
from datetime import date, timedelta

from django.db import transaction as db_transaction

from tracker.models import RecurringTransaction, Transaction


def _add_months(value: date, months: int) -> date:
    year = value.year
    month = value.month + months
    while month > 12:
        month -= 12
        year += 1
    while month <= 0:
        month += 12
        year -= 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def _parse_weekdays(series: RecurringTransaction):
    if not series.weekdays:
        return set()
    parsed = set()
    for item in series.weekdays.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            value = int(item)
        except ValueError:
            continue
        if 0 <= value <= 6:
            parsed.add(value)
    return parsed


def _allowed_weekdays(series: RecurringTransaction):
    weekdays = _parse_weekdays(series)
    if weekdays:
        return weekdays
    if series.repeat == "weekly":
        return {series.start_date.weekday()}
    return set(range(7))


def iter_occurrence_dates(series: RecurringTransaction, start: date, end: date):
    if end < start:
        return []

    if series.repeat == "monthly":
        current = series.start_date
        while current <= end:
            if current >= start:
                yield current
            current = _add_months(current, 1)
        return

    allowed = _allowed_weekdays(series)
    cursor = max(series.start_date, start)
    while cursor <= end:
        if cursor.weekday() in allowed:
            yield cursor
        cursor += timedelta(days=1)


def generate_recurring_transactions(user, up_to_date: date) -> int:
    created = 0
    series_list = RecurringTransaction.objects.filter(user=user, active=True)

    with db_transaction.atomic():
        for series in series_list:
            last_date = series.last_generated_on
            start = series.start_date
            if last_date:
                start = last_date + timedelta(days=1)

            end = up_to_date
            if series.end_date and series.end_date < end:
                end = series.end_date

            if end < start:
                continue

            latest_created = None
            for occurrence in iter_occurrence_dates(series, start, end):
                if Transaction.objects.filter(
                    user=user,
                    recurring_source=series,
                    date=occurrence,
                ).exists():
                    latest_created = occurrence
                    continue
                Transaction.objects.create(
                    user=user,
                    type=series.type,
                    amount=series.amount,
                    category=series.category,
                    payment_mode=series.payment_mode,
                    date=occurrence,
                    description=series.description,
                    recurring_source=series,
                )
                created += 1
                latest_created = occurrence

            if latest_created and latest_created != series.last_generated_on:
                series.last_generated_on = latest_created
                series.save(update_fields=["last_generated_on"])

    return created

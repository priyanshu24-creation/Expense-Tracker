from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.db.models import Sum

from datetime import date, timedelta
import csv
import json
import random

from .models import (
    CategoryBudget,
    MonthlyBudget,
    RecurringTransaction,
    SavingsGoal,
    Transaction,
    Profile,
    EmailOTP,
)
from .services.email_sender import send_app_email
from .services.analytics import (
    aggregate_totals,
    build_budget_summary,
    build_category_budget_rows,
    build_category_chart_data,
    build_income_expense_chart,
    build_insights,
    build_monthly_trend,
    category_expense_breakdown,
)
from .services.categorization import KEYWORD_CATEGORY_MAP, suggest_category
from .services.filters import apply_filters, apply_sort, parse_filters, resolve_budget_month
from .services.recurring import generate_recurring_transactions, iter_occurrence_dates
from .services.prediction_service import build_prediction_summary

import logging

logger = logging.getLogger(__name__)


# =========================
# HOME
# =========================

def _guest_context(selected_month=None, auth_mode="none", login_error=None, signup_error=None):
    return {
        "transactions": Transaction.objects.none(),
        "total_income": 0,
        "total_expense": 0,
        "balance": 0,
        "online_balance": 0,
        "cash_balance": 0,
        "selected_month": selected_month,
        "chart_labels": json.dumps([]),
        "chart_values": json.dumps([]),
        "auth_mode": auth_mode,
        "login_error": login_error,
        "signup_error": signup_error,
    }


def _redirect_to_next(request, fallback="home"):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url:
        return redirect(next_url)
    return redirect(fallback)


def _build_dashboard_context(request):
    user = request.user
    filters = parse_filters(request)
    budget_month = resolve_budget_month(filters)
    selected_month = filters.month.strftime("%Y-%m") if filters.month else ""
    trend_anchor = filters.month or filters.end_date or timezone.localdate()

    generate_recurring_transactions(user, timezone.localdate())

    base_qs = Transaction.objects.filter(user=user)
    filtered_qs = apply_filters(base_qs, filters)
    transactions = apply_sort(filtered_qs, filters)

    totals = aggregate_totals(filtered_qs)
    category_breakdown = category_expense_breakdown(filtered_qs)
    category_chart = build_category_chart_data(category_breakdown)

    trend_qs = base_qs
    if filters.category:
        trend_qs = trend_qs.filter(category=filters.category)
    if filters.payment_mode:
        trend_qs = trend_qs.filter(payment_mode=filters.payment_mode)
    trend_chart = build_monthly_trend(trend_qs, trend_anchor)

    income_expense_chart = build_income_expense_chart(totals)
    budget_summary = build_budget_summary(user, budget_month)
    category_budget_rows = build_category_budget_rows(user, budget_month)
    insights = build_insights(user, budget_month)

    overall_totals = aggregate_totals(base_qs)
    current_savings = overall_totals.balance
    goals = SavingsGoal.objects.filter(user=user).order_by("created_at")
    goal_rows = []
    for goal in goals:
        target = goal.target_amount or 0
        progress = (current_savings / target * 100) if target else 0
        progress = max(0, min(progress, 100))
        remaining = max(target - current_savings, 0)
        goal_rows.append({
            "id": goal.id,
            "name": goal.name,
            "target": target,
            "progress": progress,
            "remaining": remaining,
        })

    recurring_items = RecurringTransaction.objects.filter(user=user).order_by("-created_at")
    prediction_summary = build_prediction_summary(user, timezone.localdate())

    return {
        "transactions": transactions,
        "total_income": totals.total_income,
        "total_expense": totals.total_expense,
        "balance": totals.balance,
        "online_balance": totals.online_balance,
        "cash_balance": totals.cash_balance,
        "selected_month": selected_month,
        "filters": filters,
        "filter_query": request.GET.urlencode(),
        "has_filters": any([
            filters.month,
            filters.start_date,
            filters.end_date,
            filters.category,
            filters.payment_mode,
            filters.sort != "date_desc",
        ]),
        "category_chart": category_chart,
        "trend_chart": trend_chart,
        "income_expense_chart": income_expense_chart,
        "category_breakdown": category_breakdown,
        "budget_month": budget_month,
        "budget_summary": budget_summary,
        "category_budget_rows": category_budget_rows,
        "insights": insights,
        "goals": goal_rows,
        "current_savings": current_savings,
        "recurring_items": recurring_items,
        "category_options": Transaction.CATEGORY_CHOICES,
        "payment_options": Transaction.PAYMENT_CHOICES,
        "type_options": Transaction.TYPE_CHOICES,
        "keyword_map": KEYWORD_CATEGORY_MAP,
        "prediction": prediction_summary,
        "prediction_risk_label": {
            "high": "High Risk",
            "under": "Under-utilizing",
            "healthy": "Healthy",
            "insufficient": "Insufficient Data",
        }.get(prediction_summary.risk_level, "Healthy"),
        "weekday_options": [
            (0, "Mon"),
            (1, "Tue"),
            (2, "Wed"),
            (3, "Thu"),
            (4, "Fri"),
            (5, "Sat"),
            (6, "Sun"),
        ],
    }


def _send_email(to_email, subject, body):
    return send_app_email(to_email, subject, body)


def _temporary_data_error_message(exc):
    logger.exception("Database operation failed during auth flow")
    if settings.DEBUG:
        return f"Database error: {exc}"
    return "We are having trouble reaching the server right now. Please try again in a minute."


def _render_login_error(request, error):
    if request.POST.get("source") == "index":
        return render(request, "index.html", _guest_context(
            auth_mode="login",
            login_error=error,
        ))
    if request.POST.get("source") == "get_started":
        return render(request, "tracker/get_started.html", {
            "auth_mode": "login",
            "login_error": error,
        })
    return render(request, "tracker/login_email.html", {
        "error": error,
    })


def _render_signup_error(request, error):
    if request.POST.get("source") == "index":
        return render(request, "index.html", _guest_context(
            auth_mode="signup",
            signup_error=error,
        ))
    if request.POST.get("source") == "get_started":
        return render(request, "tracker/get_started.html", {
            "auth_mode": "signup",
            "signup_error": error,
            "full_name": request.POST.get("full_name", ""),
            "username": request.POST.get("username", ""),
            "email": request.POST.get("email", ""),
        })
    return render(request, "tracker/signup.html", {
        "error": error,
        "full_name": request.POST.get("full_name", ""),
        "username": request.POST.get("username", ""),
        "email": request.POST.get("email", ""),
    })


def _send_otp_email(user, subject):
    EmailOTP.objects.filter(user=user).delete()

    otp = str(random.randint(100000, 999999))
    EmailOTP.objects.create(user=user, otp=otp, created_at=timezone.now())
    return _send_email(user.email, subject, f"Your OTP is {otp}")


def _start_login_otp(request):
    email = (request.POST.get("email") or "").strip().lower()
    if not email:
        return None, "Please enter your email"

    user = User.objects.filter(email=email).first()
    if not user:
        return None, "No account found. Please create an account."

    error = _send_otp_email(user, "Your Login OTP")
    if error:
        return None, error

    request.session["otp_user_id"] = user.id
    request.session["otp_flow"] = "login"
    return user, None


def _start_signup_otp(request):
    full_name = (request.POST.get("full_name") or "").strip()
    username = (request.POST.get("username") or "").strip()
    email = (request.POST.get("email") or "").strip().lower()
    password = request.POST.get("password") or ""
    confirm_password = request.POST.get("confirm_password") or ""

    if not full_name or not username or not email or not password or not confirm_password:
        return None, "All fields are required"

    if password != confirm_password:
        return None, "Passwords do not match"

    try:
        validate_password(password)
    except ValidationError as exc:
        return None, exc.messages[0]

    user_by_email = User.objects.filter(email=email).first()
    user_by_username = User.objects.filter(username=username).first()

    if user_by_email and user_by_email.is_active:
        return None, "Account already exists. Please login."

    if user_by_username and (not user_by_email or user_by_username.id != user_by_email.id):
        return None, "Username already taken"

    created_user = False

    if user_by_email and not user_by_email.is_active:
        user = user_by_email
        user.username = username
        user.email = email
        user.set_password(password)
        user.is_active = False
        user.save()
    else:
        user = User.objects.create_user(username=username, email=email, password=password)
        user.is_active = False
        user.save()
        created_user = True

    Profile.objects.update_or_create(user=user, defaults={"full_name": full_name})

    error = _send_otp_email(user, "Verify Your Account")
    if error:
        if created_user:
            user.delete()
        return None, error

    request.session["otp_user_id"] = user.id
    request.session["otp_flow"] = "signup"
    return user, None

def index(request):
    selected_month = request.GET.get("month")

    if not request.user.is_authenticated:
        return render(request, "index.html", _guest_context(selected_month))

    return render(request, "index.html", _build_dashboard_context(request))


def get_started(request):
    if request.user.is_authenticated:
        return redirect("home")
    return render(request, "tracker/get_started.html", {
        "auth_mode": "login",
    })


# =========================
# TRANSACTIONS
# =========================

@login_required
@require_POST
def create_transaction(request):
    amount_raw = request.POST.get("amount") or "0"
    try:
        amount = float(amount_raw)
    except ValueError:
        amount = 0

    if amount <= 0:
        return _redirect_to_next(request)

    category = request.POST.get("category") or "other"
    description = (request.POST.get("description") or "").strip()
    if category == "auto":
        category = suggest_category(description) or "other"

    valid_categories = {choice[0] for choice in Transaction.CATEGORY_CHOICES}
    if category not in valid_categories:
        category = "other"

    payment_mode = request.POST.get("payment_mode") or "online"
    valid_payments = {choice[0] for choice in Transaction.PAYMENT_CHOICES}
    if payment_mode not in valid_payments:
        payment_mode = "online"

    trans_type = request.POST.get("type") or "expense"
    valid_types = {choice[0] for choice in Transaction.TYPE_CHOICES}
    if trans_type not in valid_types:
        trans_type = "expense"

    try:
        trans_date = date.fromisoformat(request.POST.get("date") or "")
    except ValueError:
        trans_date = timezone.localdate()

    Transaction.objects.create(
        user=request.user,
        type=trans_type,
        amount=amount,
        category=category,
        payment_mode=payment_mode,
        date=trans_date,
        description=description,
    )
    return _redirect_to_next(request)


@login_required
@require_POST
def edit_transaction(request, id):
    transaction = get_object_or_404(Transaction, id=id, user=request.user)
    amount_raw = request.POST.get("amount") or transaction.amount
    try:
        amount = float(amount_raw)
    except ValueError:
        amount = transaction.amount

    category = request.POST.get("category") or transaction.category
    description = (request.POST.get("description") or transaction.description or "").strip()
    if category == "auto":
        category = suggest_category(description) or transaction.category

    valid_categories = {choice[0] for choice in Transaction.CATEGORY_CHOICES}
    if category not in valid_categories:
        category = transaction.category

    payment_mode = request.POST.get("payment_mode") or transaction.payment_mode
    valid_payments = {choice[0] for choice in Transaction.PAYMENT_CHOICES}
    if payment_mode not in valid_payments:
        payment_mode = transaction.payment_mode

    trans_type = request.POST.get("type") or transaction.type
    valid_types = {choice[0] for choice in Transaction.TYPE_CHOICES}
    if trans_type not in valid_types:
        trans_type = transaction.type

    try:
        trans_date = date.fromisoformat(request.POST.get("date") or "")
    except ValueError:
        trans_date = transaction.date

    transaction.type = trans_type
    transaction.amount = amount
    transaction.category = category
    transaction.payment_mode = payment_mode
    transaction.date = trans_date
    transaction.description = description
    transaction.save()
    return _redirect_to_next(request)


# =========================
# DELETE
# =========================

@login_required
@require_POST
def delete_transaction(request, id):
    get_object_or_404(Transaction, id=id, user=request.user).delete()
    return _redirect_to_next(request)


# =========================
# BUDGETS
# =========================

@login_required
@require_POST
def set_monthly_budget(request):
    month_raw = request.POST.get("month")
    try:
        year, month = month_raw.split("-")
        budget_month = date(int(year), int(month), 1)
    except Exception:
        today = timezone.localdate()
        budget_month = date(today.year, today.month, 1)

    amount_raw = request.POST.get("total_budget") or "0"
    try:
        amount = float(amount_raw)
    except ValueError:
        amount = 0

    if amount <= 0:
        MonthlyBudget.objects.filter(user=request.user, month=budget_month).delete()
    else:
        MonthlyBudget.objects.update_or_create(
            user=request.user,
            month=budget_month,
            defaults={"total_amount": amount},
        )
    return _redirect_to_next(request)


@login_required
@require_POST
def set_category_budget(request):
    month_raw = request.POST.get("month")
    try:
        year, month = month_raw.split("-")
        budget_month = date(int(year), int(month), 1)
    except Exception:
        today = timezone.localdate()
        budget_month = date(today.year, today.month, 1)

    category = request.POST.get("category") or "other"
    valid_categories = {choice[0] for choice in Transaction.CATEGORY_CHOICES}
    if category not in valid_categories:
        category = "other"

    amount_raw = request.POST.get("amount") or "0"
    try:
        amount = float(amount_raw)
    except ValueError:
        amount = 0

    if amount <= 0:
        CategoryBudget.objects.filter(user=request.user, month=budget_month, category=category).delete()
    else:
        CategoryBudget.objects.update_or_create(
            user=request.user,
            month=budget_month,
            category=category,
            defaults={"amount": amount},
        )
    return _redirect_to_next(request)


# =========================
# RECURRING TRANSACTIONS
# =========================

@login_required
@require_POST
def create_recurring(request):
    amount_raw = request.POST.get("amount") or "0"
    try:
        amount = float(amount_raw)
    except ValueError:
        amount = 0
    if amount <= 0:
        return _redirect_to_next(request)

    repeat = request.POST.get("repeat") or "monthly"
    valid_repeats = {choice[0] for choice in RecurringTransaction.REPEAT_CHOICES}
    if repeat not in valid_repeats:
        repeat = "monthly"

    category = request.POST.get("category") or "other"
    valid_categories = {choice[0] for choice in Transaction.CATEGORY_CHOICES}
    if category not in valid_categories:
        category = "other"

    payment_mode = request.POST.get("payment_mode") or "online"
    valid_payments = {choice[0] for choice in Transaction.PAYMENT_CHOICES}
    if payment_mode not in valid_payments:
        payment_mode = "online"

    trans_type = request.POST.get("type") or "expense"
    valid_types = {choice[0] for choice in Transaction.TYPE_CHOICES}
    if trans_type not in valid_types:
        trans_type = "expense"

    try:
        start_date = date.fromisoformat(request.POST.get("start_date") or "")
    except ValueError:
        start_date = timezone.localdate()

    end_date_raw = request.POST.get("end_date") or ""
    try:
        end_date = date.fromisoformat(end_date_raw) if end_date_raw else None
    except ValueError:
        end_date = None

    description = (request.POST.get("description") or "").strip()
    weekdays = request.POST.getlist("weekdays")
    allowed_weekdays = [day for day in weekdays if day in {"0", "1", "2", "3", "4", "5", "6"}]
    weekdays_value = ",".join(allowed_weekdays)

    RecurringTransaction.objects.create(
        user=request.user,
        type=trans_type,
        amount=amount,
        category=category,
        payment_mode=payment_mode,
        start_date=start_date,
        end_date=end_date,
        repeat=repeat,
        description=description,
        weekdays=weekdays_value,
        active=True,
    )
    return _redirect_to_next(request)


@login_required
@require_POST
def edit_recurring(request, id):
    series = get_object_or_404(RecurringTransaction, id=id, user=request.user)
    old_values = {
        "type": series.type,
        "amount": series.amount,
        "category": series.category,
        "payment_mode": series.payment_mode,
        "description": series.description or "",
        "start_date": series.start_date,
        "end_date": series.end_date,
    }
    amount_raw = request.POST.get("amount") or series.amount
    try:
        amount = float(amount_raw)
    except ValueError:
        amount = series.amount

    repeat = request.POST.get("repeat") or series.repeat
    valid_repeats = {choice[0] for choice in RecurringTransaction.REPEAT_CHOICES}
    if repeat not in valid_repeats:
        repeat = series.repeat

    category = request.POST.get("category") or series.category
    valid_categories = {choice[0] for choice in Transaction.CATEGORY_CHOICES}
    if category not in valid_categories:
        category = series.category

    payment_mode = request.POST.get("payment_mode") or series.payment_mode
    valid_payments = {choice[0] for choice in Transaction.PAYMENT_CHOICES}
    if payment_mode not in valid_payments:
        payment_mode = series.payment_mode

    trans_type = request.POST.get("type") or series.type
    valid_types = {choice[0] for choice in Transaction.TYPE_CHOICES}
    if trans_type not in valid_types:
        trans_type = series.type

    try:
        start_date = date.fromisoformat(request.POST.get("start_date") or "")
    except ValueError:
        start_date = series.start_date

    end_date_raw = request.POST.get("end_date") or ""
    try:
        end_date = date.fromisoformat(end_date_raw) if end_date_raw else None
    except ValueError:
        end_date = series.end_date

    description = (request.POST.get("description") or series.description or "").strip()
    weekdays = request.POST.getlist("weekdays")
    allowed_weekdays = [day for day in weekdays if day in {"0", "1", "2", "3", "4", "5", "6"}]
    weekdays_value = ",".join(allowed_weekdays)

    series.type = trans_type
    series.amount = amount
    series.category = category
    series.payment_mode = payment_mode
    series.start_date = start_date
    series.end_date = end_date
    series.repeat = repeat
    series.description = description
    series.weekdays = weekdays_value
    series.save()

    generated = Transaction.objects.filter(user=request.user, recurring_source=series)

    sync_end = series.end_date or timezone.localdate()
    occurrence_dates = list(iter_occurrence_dates(series, series.start_date, sync_end))
    if occurrence_dates:
        legacy = Transaction.objects.filter(
            user=request.user,
            recurring_source__isnull=True,
            date__in=occurrence_dates,
            type=old_values["type"],
            amount=old_values["amount"],
            category=old_values["category"],
            payment_mode=old_values["payment_mode"],
        )
        legacy.update(recurring_source=series)

    generated = Transaction.objects.filter(user=request.user, recurring_source=series)
    if series.start_date:
        generated = generated.exclude(date__lt=series.start_date)
    if series.end_date:
        generated = generated.exclude(date__gt=series.end_date)

    generated.update(
        type=series.type,
        amount=series.amount,
        category=series.category,
        payment_mode=series.payment_mode,
        description=series.description,
    )

    if series.repeat in ("daily", "weekly"):
        allowed = set(allowed_weekdays)
        if not allowed:
            allowed = {str(series.start_date.weekday())} if series.repeat == "weekly" else {"0", "1", "2", "3", "4", "5", "6"}
        disallowed = {str(day) for day in range(7)} - allowed
        if disallowed:
            django_days = [((int(day) + 1) % 7) + 1 for day in disallowed]
            Transaction.objects.filter(
                user=request.user,
                recurring_source=series,
                date__week_day__in=django_days,
            ).delete()

    if series.start_date:
        Transaction.objects.filter(
            user=request.user,
            recurring_source=series,
            date__lt=series.start_date,
        ).delete()
    if series.end_date:
        Transaction.objects.filter(
            user=request.user,
            recurring_source=series,
            date__gt=series.end_date,
        ).delete()

    generate_recurring_transactions(request.user, timezone.localdate())

    return _redirect_to_next(request)


@login_required
@require_POST
def delete_recurring(request, id):
    series = get_object_or_404(RecurringTransaction, id=id, user=request.user)
    delete_future = request.POST.get("delete_future") == "on"
    if delete_future:
        Transaction.objects.filter(
            user=request.user,
            recurring_source=series,
            date__gte=timezone.localdate(),
        ).delete()
    series.delete()
    return _redirect_to_next(request)


# =========================
# SAVINGS GOALS
# =========================

@login_required
@require_POST
def create_goal(request):
    name = (request.POST.get("name") or "").strip()
    amount_raw = request.POST.get("target_amount") or "0"
    try:
        amount = float(amount_raw)
    except ValueError:
        amount = 0
    if not name or amount <= 0:
        return _redirect_to_next(request)

    SavingsGoal.objects.create(user=request.user, name=name, target_amount=amount)
    return _redirect_to_next(request)


@login_required
@require_POST
def delete_goal(request, id):
    get_object_or_404(SavingsGoal, id=id, user=request.user).delete()
    return _redirect_to_next(request)


# =========================
# EXPORTS
# =========================

@login_required
def export_transactions(request):
    filters = parse_filters(request)
    queryset = apply_filters(Transaction.objects.filter(user=request.user), filters).order_by("date")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="transactions.csv"'
    writer = csv.writer(response)
    writer.writerow(["Date", "Type", "Category", "Payment", "Description", "Amount"])

    for item in queryset:
        writer.writerow([
            item.date.isoformat(),
            item.get_type_display(),
            item.get_category_display(),
            item.get_payment_mode_display(),
            item.description,
            f"{item.amount:.2f}",
        ])

    return response


@login_required
def export_summary(request):
    filters = parse_filters(request)
    queryset = apply_filters(Transaction.objects.filter(user=request.user), filters)
    totals = aggregate_totals(queryset)
    savings_rate = 0
    if totals.total_income > 0:
        savings_rate = (totals.balance / totals.total_income) * 100

    top_category = (
        queryset.filter(type="expense")
        .values("category")
        .annotate(total=Sum("amount"))
        .order_by("-total")
        .first()
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="monthly_summary.csv"'
    writer = csv.writer(response)

    writer.writerow(["Summary Type", "Value"])
    writer.writerow(["Total Income", f"{totals.total_income:.2f}"])
    writer.writerow(["Total Expense", f"{totals.total_expense:.2f}"])
    writer.writerow(["Balance", f"{totals.balance:.2f}"])
    writer.writerow(["Savings Rate (%)", f"{savings_rate:.2f}"])
    if top_category:
        label_map = dict(Transaction.CATEGORY_CHOICES)
        writer.writerow(["Top Category", label_map.get(top_category["category"], top_category["category"])])

    return response


# =========================
# RESET TRANSACTIONS
# =========================

@login_required
@require_POST
def reset_transactions(request):
    filters = parse_filters(request)
    queryset = apply_filters(Transaction.objects.filter(user=request.user), filters)
    queryset.delete()
    return _redirect_to_next(request)


# =========================
# PROFILE
# =========================

@login_required
def profile(request):
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)
    return render(request, "profile.html", {"profile": profile_obj})


@login_required
def edit_profile(request):
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        full_name = (request.POST.get("full_name") or "").strip()
        username = (request.POST.get("username") or "").strip()

        if not full_name or not username:
            next_username_change_at = (
                profile_obj.last_username_change_at + timedelta(days=30)
                if profile_obj.last_username_change_at
                else None
            )
            return render(request, "edit_profile.html", {
                "profile": profile_obj,
                "error": "Full name and username are required",
                "next_username_change_at": next_username_change_at,
            })

        if username != request.user.username:
            if profile_obj.last_username_change_at:
                next_allowed = profile_obj.last_username_change_at + timedelta(days=30)
                if timezone.now() < next_allowed:
                    return render(request, "edit_profile.html", {
                        "profile": profile_obj,
                        "error": f"You can change your username again on {next_allowed:%b %d, %Y}.",
                        "next_username_change_at": next_allowed,
                    })

            if User.objects.filter(username=username).exclude(id=request.user.id).exists():
                next_username_change_at = (
                    profile_obj.last_username_change_at + timedelta(days=30)
                    if profile_obj.last_username_change_at
                    else None
                )
                return render(request, "edit_profile.html", {
                    "profile": profile_obj,
                    "error": "Username already taken",
                    "next_username_change_at": next_username_change_at,
                })

            request.user.username = username
            request.user.save(update_fields=["username"])
            profile_obj.last_username_change_at = timezone.now()

        profile_obj.full_name = full_name
        if request.FILES.get("image"):
            profile_obj.image = request.FILES["image"]
        try:
            profile_obj.save()
        except Exception:
            logger.exception("Profile update failed for user_id=%s", request.user.id)
            next_username_change_at = (
                profile_obj.last_username_change_at + timedelta(days=30)
                if profile_obj.last_username_change_at
                else None
            )
            return render(request, "edit_profile.html", {
                "profile": profile_obj,
                "error": "Profile update failed. Please try again.",
                "next_username_change_at": next_username_change_at,
            })
        return redirect("profile")

    next_username_change_at = (
        profile_obj.last_username_change_at + timedelta(days=30)
        if profile_obj.last_username_change_at
        else None
    )
    return render(request, "edit_profile.html", {
        "profile": profile_obj,
        "next_username_change_at": next_username_change_at,
    })


# =========================
# EMAIL LOGIN + OTP SEND
# =========================

def email_login(request):
    if request.method == "POST":
        try:
            _, error = _start_login_otp(request)
        except DatabaseError as exc:
            error = _temporary_data_error_message(exc)
        if error:
            return _render_login_error(request, error)

        return redirect("verify_otp")

    return render(request, "tracker/login_email.html")


def email_signup(request):
    if request.method == "POST":
        try:
            _, error = _start_signup_otp(request)
        except DatabaseError as exc:
            error = _temporary_data_error_message(exc)
        if error:
            return _render_signup_error(request, error)

        return redirect("verify_otp")

    return render(request, "tracker/signup.html")


# =========================
# OTP VERIFY
# =========================

def verify_otp(request):
    user_id = request.session.get("otp_user_id")
    flow = request.session.get("otp_flow", "login")

    if not user_id:
        return redirect("email_login")

    user = User.objects.filter(id=user_id).first()
    if not user:
        return redirect("email_login")

    otp_obj = EmailOTP.objects.filter(user=user).first()

    if request.method == "POST":
        entered_otp = request.POST.get("otp")

        if not otp_obj:
            return render(request, "tracker/verify_otp.html", {
                "error": "OTP expired",
                "flow": flow,
            })

        if timezone.now() > otp_obj.created_at + timedelta(minutes=10):
            otp_obj.delete()
            return render(request, "tracker/verify_otp.html", {
                "error": "OTP expired",
                "flow": flow,
            })

        if entered_otp == otp_obj.otp:
            if not user.is_active:
                user.is_active = True
                user.save()
            login(request, user)
            otp_obj.delete()
            request.session.pop("otp_user_id", None)
            request.session.pop("otp_flow", None)
            return redirect("home")

        return render(request, "tracker/verify_otp.html", {
            "error": "Invalid OTP",
            "flow": flow,
        })

    return render(request, "tracker/verify_otp.html", {"flow": flow})


# =========================
# FORGOT PASSWORD (OTP)
# =========================

def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email")
        user = User.objects.filter(email=email).first()

        if not user:
            return render(request, "tracker/forgot_password.html", {
                "error": "No account found with this email"
            })

        if not settings.SENDGRID_API_KEY:
            return render(request, "tracker/forgot_password.html", {
                "error": "Email service not configured"
            })

        # clear old OTPs
        EmailOTP.objects.filter(user=user).delete()

        otp = str(random.randint(100000, 999999))
        EmailOTP.objects.create(
            user=user,
            otp=otp,
            created_at=timezone.now()
        )

        error = _send_email(email, "Your Password Reset OTP", f"Your OTP is {otp}")
        if error:
            return render(request, "tracker/forgot_password.html", {
                "error": error
            })

        request.session["reset_user_id"] = user.id
        return redirect("forgot_password_verify")

    return render(request, "tracker/forgot_password.html")


def forgot_password_verify(request):
    user_id = request.session.get("reset_user_id")
    if not user_id:
        return redirect("forgot_password")

    user = User.objects.filter(id=user_id).first()
    if not user:
        return redirect("forgot_password")

    if request.method == "POST":
        entered_otp = request.POST.get("otp")
        otp_obj = EmailOTP.objects.filter(user=user).first()

        if not otp_obj:
            return render(request, "tracker/forgot_password_verify.html", {
                "error": "OTP expired"
            })

        if timezone.now() > otp_obj.created_at + timedelta(minutes=10):
            otp_obj.delete()
            return render(request, "tracker/forgot_password_verify.html", {
                "error": "OTP expired"
            })

        if entered_otp == otp_obj.otp:
            otp_obj.delete()
            request.session["reset_verified"] = True
            return redirect("forgot_password_reset")

        return render(request, "tracker/forgot_password_verify.html", {
            "error": "Invalid OTP"
        })

    return render(request, "tracker/forgot_password_verify.html")


def forgot_password_reset(request):
    user_id = request.session.get("reset_user_id")
    verified = request.session.get("reset_verified")
    if not user_id or not verified:
        return redirect("forgot_password")

    user = User.objects.filter(id=user_id).first()
    if not user:
        return redirect("forgot_password")

    if request.method == "POST":
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        if password1 != password2:
            return render(request, "tracker/forgot_password_reset.html", {
                "error": "Passwords do not match"
            })

        try:
            validate_password(password1, user)
        except ValidationError as exc:
            return render(request, "tracker/forgot_password_reset.html", {
                "error_list": exc.messages
            })

        user.set_password(password1)
        user.save()

        # keep session if same logged-in user
        if request.user.is_authenticated and request.user.id == user.id:
            update_session_auth_hash(request, user)

        request.session.pop("reset_user_id", None)
        request.session.pop("reset_verified", None)
        return redirect("forgot_password_done")

    return render(request, "tracker/forgot_password_reset.html")

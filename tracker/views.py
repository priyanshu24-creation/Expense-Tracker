from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from datetime import timedelta
import json
import random

from .models import Transaction, Profile, EmailOTP

import logging

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

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


def _send_otp_email(user, subject):
    if not settings.SENDGRID_API_KEY:
        return "Email service not configured"

    EmailOTP.objects.filter(user=user).delete()

    otp = str(random.randint(100000, 999999))
    EmailOTP.objects.create(user=user, otp=otp, created_at=timezone.now())

    from_email = Email(settings.DEFAULT_FROM_EMAIL)
    to_email = To(user.email)
    content = Content("text/plain", f"Your OTP is {otp}")
    mail = Mail(from_email, to_email, subject, content)

    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        sg.client.mail.send.post(request_body=mail.get())
    except Exception:
        return "Failed to send OTP. Try again."

    return None


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

    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect("email_login")

        Transaction.objects.create(
            user=request.user,
            type=request.POST.get("type"),
            amount=float(request.POST.get("amount")),
            category=request.POST.get("category"),
            payment_mode=request.POST.get("payment_mode", "online"),
            date=request.POST.get("date"),
        )
        return redirect("home")

    if not request.user.is_authenticated:
        return render(request, "index.html", _guest_context(selected_month))

    transactions = Transaction.objects.filter(user=request.user)

    if selected_month:
        year, month = selected_month.split("-")
        transactions = transactions.filter(
            date__year=int(year),
            date__month=int(month)
        )

    total_income = sum(t.amount for t in transactions if t.type == "income")
    total_expense = sum(t.amount for t in transactions if t.type == "expense")
    balance = total_income - total_expense

    online_balance = sum(
        t.amount if t.type == "income" else -t.amount
        for t in transactions if t.payment_mode == "online"
    )

    cash_balance = sum(
        t.amount if t.type == "income" else -t.amount
        for t in transactions if t.payment_mode == "cash"
    )

    category_data = {}
    for t in transactions:
        if t.type == "expense":
            label = t.get_category_display()
            category_data[label] = category_data.get(label, 0) + t.amount

    return render(request, "index.html", {
        "transactions": transactions,
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": balance,
        "online_balance": online_balance,
        "cash_balance": cash_balance,
        "selected_month": selected_month,
        "chart_labels": json.dumps(list(category_data.keys())),
        "chart_values": json.dumps(list(category_data.values())),
    })


def get_started(request):
    if request.user.is_authenticated:
        return redirect("home")
    return render(request, "tracker/get_started.html", {
        "auth_mode": "login",
    })


# =========================
# DELETE
# =========================

@login_required
def delete_transaction(request, id):
    get_object_or_404(Transaction, id=id, user=request.user).delete()
    return redirect("home")


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
        _, error = _start_login_otp(request)
        if error:
            if request.POST.get("source") == "index":
                return render(request, "index.html", _guest_context(
                    auth_mode="login",
                    login_error=error
                ))
            if request.POST.get("source") == "get_started":
                return render(request, "tracker/get_started.html", {
                    "auth_mode": "login",
                    "login_error": error,
                })
            return render(request, "tracker/login_email.html", {
                "error": error
            })

        return redirect("verify_otp")

    return render(request, "tracker/login_email.html")


def email_signup(request):
    if request.method == "POST":
        _, error = _start_signup_otp(request)
        if error:
            if request.POST.get("source") == "index":
                return render(request, "index.html", _guest_context(
                    auth_mode="signup",
                    signup_error=error
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

    if request.method == "POST":
        entered_otp = request.POST.get("otp")
        otp_obj = EmailOTP.objects.filter(user=user).first()

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

        from_email = Email(settings.DEFAULT_FROM_EMAIL)
        to_email = To(email)
        subject = "Your Password Reset OTP"
        content = Content("text/plain", f"Your OTP is {otp}")
        mail = Mail(from_email, to_email, subject, content)

        try:
            sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
            sg.client.mail.send.post(request_body=mail.get())
        except Exception:
            return render(request, "tracker/forgot_password.html", {
                "error": "Failed to send OTP. Try again."
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

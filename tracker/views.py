from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings

from datetime import timedelta
import json
import random

from .models import Transaction, Profile, EmailOTP

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content


# =========================
# HOME
# =========================

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
        return render(request, "index.html", {
            "transactions": Transaction.objects.none(),
            "total_income": 0,
            "total_expense": 0,
            "balance": 0,
            "online_balance": 0,
            "cash_balance": 0,
            "selected_month": selected_month,
            "chart_labels": json.dumps([]),
            "chart_values": json.dumps([]),
        })

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
        profile_obj.full_name = request.POST.get("full_name")
        if request.FILES.get("image"):
            profile_obj.image = request.FILES["image"]
        profile_obj.save()
        return redirect("profile")

    return render(request, "edit_profile.html", {"profile": profile_obj})


# =========================
# EMAIL LOGIN + OTP SEND
# =========================

def email_login(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password != confirm_password:
            return render(request, "tracker/login_email.html", {
                "error": "Passwords do not match"
            })

        user = User.objects.filter(email=email).first()

        if not user:
            user = User.objects.create_user(
                username=email.split("@")[0],
                email=email,
                password=password,
            )
            Profile.objects.update_or_create(
                user=user,
                defaults={"full_name": full_name}
            )

        # clear old OTPs
        EmailOTP.objects.filter(user=user).delete()

        otp = str(random.randint(100000, 999999))
        EmailOTP.objects.create(
            user=user,
            otp=otp,
            created_at=timezone.now()
        )

        # ===== SENDGRID SEND =====
        from_email = Email(settings.DEFAULT_FROM_EMAIL)
        to_email = To(email)
        subject = "Your OTP Code"
        content = Content("text/plain", f"Your OTP is {otp}")

        mail = Mail(from_email, to_email, subject, content)

        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        resp = sg.client.mail.send.post(request_body=mail.get())

        print("SENDGRID STATUS:", resp.status_code)

        request.session["otp_user_id"] = user.id
        return redirect("verify_otp")

    return render(request, "tracker/login_email.html")


# =========================
# OTP VERIFY
# =========================

def verify_otp(request):
    user_id = request.session.get("otp_user_id")

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
                "error": "OTP expired"
            })

        if timezone.now() > otp_obj.created_at + timedelta(minutes=10):
            otp_obj.delete()
            return render(request, "tracker/verify_otp.html", {
                "error": "OTP expired"
            })

        if entered_otp == otp_obj.otp:
            login(request, user)
            otp_obj.delete()
            request.session.pop("otp_user_id", None)
            return redirect("home")

        return render(request, "tracker/verify_otp.html", {
            "error": "Invalid OTP"
        })

    return render(request, "tracker/verify_otp.html")

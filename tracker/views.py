from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from datetime import timedelta
import json
import random

from .models import Transaction, Profile, EmailOTP


# =========================
# HOME
# =========================

def index(request):
    selected_month = request.GET.get('month')

    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect("email_login")

        Transaction.objects.create(
            user=request.user,
            type=request.POST.get('type'),
            amount=request.POST.get('amount'),
            category=request.POST.get('category'),
            payment_mode=request.POST.get('payment_mode', 'online'),
            date=request.POST.get('date')
        )
        return redirect('/')

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

    total_income = sum(t.amount for t in transactions if t.type == "income")
    total_expense = sum(t.amount for t in transactions if t.type == "expense")
    balance = total_income - total_expense

    return render(request, "index.html", {
        "transactions": transactions,
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": balance,
        "online_balance": 0,
        "cash_balance": 0,
        "selected_month": selected_month,
        "chart_labels": json.dumps([]),
        "chart_values": json.dumps([]),
    })


# =========================
# EMAIL LOGIN + OTP
# =========================

def email_login(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password != confirm_password:
            return render(request, "tracker/login_email.html",
                          {"error": "Passwords do not match"})

        user = User.objects.filter(email=email).first()

        if not user:
            user = User.objects.create_user(
                username=email.split("@")[0],
                email=email,
                password=password
            )
            Profile.objects.update_or_create(
                user=user,
                defaults={"full_name": full_name}
            )

        EmailOTP.objects.filter(user=user).delete()

        otp = str(random.randint(100000, 999999))
        EmailOTP.objects.create(user=user, otp=otp)

        print("SENDING OTP:", otp, "TO:", email)

        send_mail(
            subject="Your OTP Code",
            message=f"Your OTP is {otp}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        request.session["otp_user_id"] = user.id
        return redirect("verify_otp")

    return render(request, "tracker/login_email.html")


# =========================
# VERIFY OTP
# =========================

def verify_otp(request):
    user_id = request.session.get("otp_user_id")
    if not user_id:
        return redirect("email_login")

    user = User.objects.get(id=user_id)

    if request.method == "POST":
        code = request.POST.get("otp")

        otp_obj = EmailOTP.objects.filter(user=user).order_by("-created_at").first()

        if not otp_obj:
            return render(request, "tracker/verify_otp.html",
                          {"error": "OTP expired"})

        if timezone.now() > otp_obj.created_at + timedelta(minutes=10):
            otp_obj.delete()
            return render(request, "tracker/verify_otp.html",
                          {"error": "OTP expired"})

        if otp_obj.otp == code:
            otp_obj.delete()
            request.session.pop("otp_user_id", None)
            login(request, user)
            return redirect("home")

        return render(request, "tracker/verify_otp.html",
                      {"error": "Invalid code"})

    return render(request, "tracker/verify_otp.html")

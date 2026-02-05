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
import traceback

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
            date=request.POST.get('date')
        )
        return redirect('/')

    if not request.user.is_authenticated:
        return render(request, "index.html", {
            "transactions": Transaction.objects.none(),
            "total_income": 0,
            "total_expense": 0,
            "balance": 0,
            "selected_month": selected_month,
            "chart_labels": json.dumps([]),
            "chart_values": json.dumps([]),
        })

    transactions = Transaction.objects.filter(user=request.user)

    if selected_month:
        year, month = selected_month.split('-')
        transactions = transactions.filter(date__year=year, date__month=month)

    total_income = sum(t.amount for t in transactions if t.type.lower() == "income")
    total_expense = sum(t.amount for t in transactions if t.type.lower() == "expense")
    balance = total_income - total_expense

    # ===== LOW BALANCE EMAIL =====

    sent_flag = request.session.get("low_balance_email_sent", False)

    if balance <= 100 and not sent_flag and request.user.email:
        subject = "⚠ Low Balance Alert - Expense Tracker"
        message = (
            f"Hello {request.user.username},\n\n"
            f"⚠ Your balance is ₹{balance}.\n\n"
            f"Please control your expenses.\n\n"
            f"Expense Tracker Team"
        )

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,   # ✅ fixed
                [request.user.email],
                fail_silently=False,
            )
            print("LOW BALANCE EMAIL SENT")
            request.session["low_balance_email_sent"] = True

        except Exception as e:
            print("LOW BALANCE EMAIL FAILED:", e)
            traceback.print_exc()

    if balance > 100:
        request.session["low_balance_email_sent"] = False

    # ===== CHART DATA =====

    category_data = {}
    for t in transactions:
        if t.type.lower() == "expense":
            label = t.get_category_display()
            category_data[label] = category_data.get(label, 0) + t.amount

    return render(request, "index.html", {
        "transactions": transactions,
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": balance,
        "selected_month": selected_month,
        "chart_labels": json.dumps(list(category_data.keys())),
        "chart_values": json.dumps(list(category_data.values())),
    })


# =========================
# DELETE
# =========================

@login_required
def delete_transaction(request, id):
    transaction = get_object_or_404(Transaction, id=id, user=request.user)
    transaction.delete()
    return redirect("/")


# =========================
# PROFILE
# =========================

@login_required
def profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    return render(request, "profile.html", {"profile": profile})


@login_required
def edit_profile(request):
    profile = request.user.profile

    if request.method == "POST":
        profile.full_name = request.POST.get("full_name")
        if request.FILES.get("image"):
            profile.image = request.FILES.get("image")
        profile.save()
        return redirect("home")

    return render(request, "edit_profile.html", {"profile": profile})


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
            return render(
                request,
                "tracker/login_email.html",
                {"error": "Passwords do not match"}
            )

        user = User.objects.filter(email=email).first()

        if not user:
            username = email.split("@")[0]
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            Profile.objects.create(user=user, full_name=full_name)

        otp = str(random.randint(100000, 999999))
        EmailOTP.objects.create(user=user, otp=otp)

        subject = "🔐 Your Expense Tracker Login Code"
        message = f"Your OTP is: {otp}"

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,   # ✅ fixed
                [email],
                fail_silently=False,
            )
            print("OTP EMAIL SENT")

        except Exception as e:
            print("OTP EMAIL FAILED:", e)
            traceback.print_exc()
            return render(
                request,
                "tracker/login_email.html",
                {"error": "Email send failed"}
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
        otp_obj = EmailOTP.objects.filter(user=user).first()

        if not otp_obj:
            return render(
                request,
                "tracker/verify_otp.html",
                {"error": "OTP expired"}
            )

        if timezone.now() > otp_obj.created_at + timedelta(minutes=5):
            otp_obj.delete()
            return render(
                request,
                "tracker/verify_otp.html",
                {"error": "OTP expired"}
            )

        if otp_obj.otp == code:
            otp_obj.delete()
            del request.session["otp_user_id"]
            login(request, user)
            return redirect("home")

        return render(
            request,
            "tracker/verify_otp.html",
            {"error": "Invalid code"}
        )

    return render(request, "tracker/verify_otp.html")

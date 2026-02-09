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
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail



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

    if selected_month:
        year, month = selected_month.split('-')
        transactions = transactions.filter(date__year=year, date__month=month)

    total_income = sum(t.amount for t in transactions if t.type == "income")
    total_expense = sum(t.amount for t in transactions if t.type == "expense")
    balance = total_income - total_expense

    online_income = sum(t.amount for t in transactions if t.type == "income" and t.payment_mode == "online")
    online_expense = sum(t.amount for t in transactions if t.type == "expense" and t.payment_mode == "online")
    cash_income = sum(t.amount for t in transactions if t.type == "income" and t.payment_mode == "cash")
    cash_expense = sum(t.amount for t in transactions if t.type == "expense" and t.payment_mode == "cash")

    online_balance = online_income - online_expense
    cash_balance = cash_income - cash_expense

    # ===== LOW BALANCE EMAIL =====
    sent_flag = request.session.get("low_balance_email_sent", False)

    if balance <= 100 and not sent_flag and request.user.email:
        print("LOW BALANCE MAIL → sending")
        send_mail(
            "Low Balance Alert",
            f"Your balance is ₹{balance}",
            settings.DEFAULT_FROM_EMAIL,
            [request.user.email],
            fail_silently=False,
        )
        request.session["low_balance_email_sent"] = True

    if balance > 100:
        request.session["low_balance_email_sent"] = False

    # chart data
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
            profile.image = request.FILES["image"]
        profile.save()
        return redirect("home")

    return render(request, "edit_profile.html", {"profile": profile})


# =========================
# EMAIL LOGIN + OTP
# =========================

def send_otp_email(to_email, otp):
    message = Mail(
        from_email=settings.DEFAULT_FROM_EMAIL,
        to_emails=to_email,
        subject="Your OTP Code",
        html_content=f"<strong>Your OTP is {otp}</strong>",
    )

    sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
    sg.send(message)


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

        # remove old OTPs
        EmailOTP.objects.filter(user=user).delete()

        otp = str(random.randint(100000, 999999))
        EmailOTP.objects.create(user=user, otp=otp)

        # ===== OTP MAIL SEND =====
        print("=== OTP MAIL DEBUG ===")
        print("BACKEND:", settings.EMAIL_BACKEND)
        print("FROM:", settings.DEFAULT_FROM_EMAIL)
        print("TO:", email)

        send_otp_email(email, otp)


        print("=== OTP MAIL SEND CALLED ===")

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

from django.shortcuts import render, redirect
from .models import Transaction
from django.contrib.auth.decorators import login_required
import json
from .models import Profile
import random
from django.core.mail import send_mail
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from .models import EmailOTP
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

@login_required
def index(request):
    selected_month = request.GET.get('month')

    if request.method == "POST":
        Transaction.objects.create(
            user=request.user,   # 🔴 THIS IS THE KEY LINE
            type=request.POST['type'],
            amount=request.POST['amount'],
            category=request.POST['category'],
            date=request.POST['date']
        )
        return redirect('/')

    # 🔴 Only fetch logged-in user's data
    transactions = Transaction.objects.filter(user=request.user)

    if selected_month:
        year, month = selected_month.split('-')
        transactions = transactions.filter(date__year=year, date__month=month)

    total_income = sum(t.amount for t in transactions if t.type.lower() == "income")
    total_expense = sum(t.amount for t in transactions if t.type.lower() == "expense")
    balance = total_income - total_expense

    sent_flag = request.session.get("low_balance_email_sent", False)

    if balance <= 100 and not sent_flag:
     send_mail(
        subject="⚠ Low Balance Alert - Expense Tracker",
        message=(
            f"Hello {request.user.username},\n\n"
            f"⚠ Your balance has dropped to ₹{balance}.\n\n"
            f"This is a friendly reminder to control your expenses "
            f"and try saving some money.\n\n"
            f"Tip: Track daily expenses and set a monthly budget.\n\n"
            f"Stay financially strong 💪\n"
            f"Expense Tracker Team"
        ),
        from_email="yourgmail@gmail.com",
        recipient_list=[request.user.email],
        fail_silently=True,
    )
    request.session["low_balance_email_sent"] = True

    if balance > 100:
     request.session["low_balance_email_sent"] = False


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


@login_required
def delete_transaction(request, id):
    Transaction.objects.get(id=id, user=request.user).delete()
    return redirect('/')

@login_required
def profile(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
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

def email_login(request):
    if request.method == "POST":
        email = request.POST.get("email")

        user = User.objects.filter(email=email).first()
        if not user:
            return render(
                request,
                "tracker/login_email.html",
                {"error": "Email not registered"}
            )

        # 🔥 Delete old OTPs for this user
        EmailOTP.objects.filter(user=user).delete()

        otp = str(random.randint(100000, 999999))
        EmailOTP.objects.create(user=user, otp=otp)

        send_mail(
            subject="🔐 Your Expense Tracker Login Code",
            message=(
                f"Hello {user.username},\n\n"
                f"Your One-Time Password (OTP) for login is:\n\n"
                f"👉 {otp}\n\n"
                f"This code is valid for only a few minutes.\n\n"
                f"If this was NOT you, please ignore this email. "
                f"Someone may have tried to access your account.\n\n"
                f"Stay safe,\n"
                f"Expense Tracker Team"
            ),
            from_email="trackexpenseteam@gmail.com",
            recipient_list=[email],
        )

        request.session["otp_user_id"] = user.id
        return redirect("verify_otp")

    return render(request, "tracker/login_email.html")


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
                {"error": "OTP expired. Please request again."}
            )

        # ⏰ Expiry check (5 minutes)
        if timezone.now() > otp_obj.created_at + timedelta(minutes=5):
            otp_obj.delete()
            return render(
                request,
                "tracker/verify_otp.html",
                {"error": "OTP expired. Please request again."}
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
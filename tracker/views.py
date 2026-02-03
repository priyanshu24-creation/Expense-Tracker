from django.shortcuts import render, redirect, get_object_or_404
from .models import Transaction, Profile, EmailOTP
from django.contrib.auth.decorators import login_required
import json
import random
from django.core.mail import send_mail
from django.contrib.auth import login
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

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

    # 🔴 Only fetch logged-in user's data
    transactions = Transaction.objects.filter(user=request.user)

    if selected_month:
        year, month = selected_month.split('-')
        transactions = transactions.filter(date__year=year, date__month=month)

    total_income = sum(t.amount for t in transactions if t.type.lower() == "income")
    total_expense = sum(t.amount for t in transactions if t.type.lower() == "expense")
    balance = total_income - total_expense

    last_notified = request.session.get("low_balance_last_notified")

    should_notify = False
    if balance <= 0:
        should_notify = True
    elif last_notified is None:
        should_notify = balance <= 50
    else:
        should_notify = balance <= (last_notified - 50)

    if should_notify:
        send_mail(
            subject="Low Balance Alert - Expense Tracker",
            message=(
                f"Hello {request.user.username},\n\n"
                f"Your balance has dropped to INR {balance}.\n\n"
                f"This is a friendly reminder to control your expenses "
                f"and try saving some money.\n\n"
                f"Tip: Track daily expenses and set a monthly budget.\n\n"
                f"Stay financially strong\n"
                f"Expense Tracker Team"
            ),
            from_email="yourgmail@gmail.com",
            recipient_list=[request.user.email],
            fail_silently=True,
        )
        request.session["low_balance_last_notified"] = balance

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
    transaction = get_object_or_404(Transaction, id=id, user=request.user)
    transaction.delete()
    return redirect("/")

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
        mode = request.POST.get("mode", "signup")
        email = request.POST.get("email")
        if mode == "login":
            user = User.objects.filter(email=email).first()
            if not user:
                return render(request, "tracker/login_email.html", {
                    "error": "Account not found. Please create an account first."
                })

            otp = str(random.randint(100000, 999999))
            EmailOTP.objects.create(user=user, otp=otp)

            if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
                return render(request, "tracker/login_email.html", {
                    "error": "Email service is not configured. Please contact support."
                })

            try:
                send_mail(
                    subject="Your Expense Tracker Login Code",
                    message=(
                        f"Hello {user.username},\n\n"
                        f"Your One-Time Password (OTP) for login is:\n\n"
                        f"{otp}\n\n"
                        f"This code is valid for only a few minutes.\n\n"
                        f"If this was NOT you, please ignore this email.\n\n"
                        f"Stay safe,\nExpense Tracker Team"
                    ),
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[email],
                    fail_silently=False,
                )
            except Exception:
                return render(request, "tracker/login_email.html", {
                    "error": "Unable to send OTP email right now. Please try again later."
                })


            request.session["otp_user_id"] = user.id
            return redirect("verify_otp")

        full_name = request.POST.get("full_name")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password != confirm_password:
            return render(request, "tracker/login_email.html", {
                "error": "Passwords do not match"
            })

        user = User.objects.filter(email=email).first()

        if user:
            return render(request, "tracker/login_email.html", {
                "error": "Account already exists. Please log in."
            })

        # create user
        username = email.split("@")[0]
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        Profile.objects.filter(user=user).update(full_name=full_name)

        otp = str(random.randint(100000,999999))
        EmailOTP.objects.create(user=user, otp=otp)

        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            return render(request, "tracker/login_email.html", {
                "error": "Email service is not configured. Please contact support."
            })

        try:
            send_mail(
                subject="Your Expense Tracker Login Code",
                message=(
                    f"Hello {user.username},\n\n"
                    f"Your One-Time Password (OTP) for login is:\n\n"
                    f"{otp}\n\n"
                    f"This code is valid for only a few minutes.\n\n"
                    f"If this was NOT you, please ignore this email.\n\n"
                    f"Stay safe,\nExpense Tracker Team"
                ),
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception:
            return render(request, "tracker/login_email.html", {
                "error": "Unable to send OTP email right now. Please try again later."
            })


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

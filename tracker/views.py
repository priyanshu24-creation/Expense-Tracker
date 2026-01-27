from django.shortcuts import render, redirect
from .models import Transaction
from django.contrib.auth.decorators import login_required
import json
from .models import Profile
 

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

    total_income = sum(t.amount for t in transactions if t.type == "income")
    total_expense = sum(t.amount for t in transactions if t.type == "expense")
    balance = total_income - total_expense

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
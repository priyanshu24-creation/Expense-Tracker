from django.contrib import admin

from .models import (
    CategoryBudget,
    EmailLog,
    MonthlyBudget,
    RecurringTransaction,
    SavingsGoal,
    SpendingPrediction,
    Transaction,
)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "category", "amount", "payment_mode", "date", "recurring_source")
    list_filter = ("type", "category", "payment_mode")
    search_fields = ("user__username", "description")


@admin.register(MonthlyBudget)
class MonthlyBudgetAdmin(admin.ModelAdmin):
    list_display = ("user", "month", "total_amount", "updated_at")
    list_filter = ("month",)


@admin.register(CategoryBudget)
class CategoryBudgetAdmin(admin.ModelAdmin):
    list_display = ("user", "month", "category", "amount", "updated_at")
    list_filter = ("month", "category")


@admin.register(RecurringTransaction)
class RecurringTransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "category", "amount", "repeat", "start_date", "active")
    list_filter = ("repeat", "active", "category")
    search_fields = ("user__username", "description")


@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "target_amount", "updated_at")
    search_fields = ("user__username", "name")


@admin.register(SpendingPrediction)
class SpendingPredictionAdmin(admin.ModelAdmin):
    list_display = ("user", "month", "predicted_expense", "risk_level", "created_at")
    list_filter = ("risk_level", "month")


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("user", "email_type", "related_month", "sent_at")
    list_filter = ("email_type", "related_month")

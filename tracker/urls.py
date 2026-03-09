from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.index, name='home'),
    path('get-started/', views.get_started, name='get_started'),
    path("transactions/create/", views.create_transaction, name="create_transaction"),
    path("transactions/<int:id>/edit/", views.edit_transaction, name="edit_transaction"),
    path("transactions/<int:id>/delete/", views.delete_transaction, name="delete_transaction"),
    path("budgets/monthly/", views.set_monthly_budget, name="set_monthly_budget"),
    path("budgets/category/", views.set_category_budget, name="set_category_budget"),
    path("recurring/create/", views.create_recurring, name="create_recurring"),
    path("recurring/<int:id>/edit/", views.edit_recurring, name="edit_recurring"),
    path("recurring/<int:id>/delete/", views.delete_recurring, name="delete_recurring"),
    path("goals/create/", views.create_goal, name="create_goal"),
    path("goals/<int:id>/delete/", views.delete_goal, name="delete_goal"),
    path("export/transactions/", views.export_transactions, name="export_transactions"),
    path("export/summary/", views.export_summary, name="export_summary"),
    path("transactions/reset/", views.reset_transactions, name="reset_transactions"),
    path('profile/', views.profile, name='profile'),
    path("edit-profile/", views.edit_profile, name="edit_profile"),
    path(
        "password-change/",
        auth_views.PasswordChangeView.as_view(
            template_name="password_change.html",
            success_url="/password-change/done/"
        ),
        name="password_change"
    ),
    path(
        "password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="password_change_done.html"
        ),
        name="password_change_done"
    ),
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("forgot-password/verify/", views.forgot_password_verify, name="forgot_password_verify"),
    path("forgot-password/reset/", views.forgot_password_reset, name="forgot_password_reset"),
    path("forgot-password/done/", auth_views.PasswordChangeDoneView.as_view(
        template_name="forgot_password_done.html"
    ), name="forgot_password_done"),
    # aliases (underscore)
    path("forgot_password/", views.forgot_password),
    path("forgot_password/verify/", views.forgot_password_verify),
    path("forgot_password/reset/", views.forgot_password_reset),
    path("forgot_password/done/", auth_views.PasswordChangeDoneView.as_view(
        template_name="forgot_password_done.html"
    )),
   


]

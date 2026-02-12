from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.index, name='home'),
    path('get-started/', views.get_started, name='get_started'),
    path("delete/<int:id>/", views.delete_transaction, name="delete"),
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

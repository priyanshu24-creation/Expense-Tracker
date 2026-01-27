from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='home'),
    path('delete/<int:id>/', views.delete_transaction, name='delete'),
    path('profile/', views.profile, name='profile'),
    path("edit-profile/", views.edit_profile, name="edit_profile"),


]

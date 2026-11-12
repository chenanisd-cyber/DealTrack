from django.urls import path

from . import views

app_name = "merchant"

urlpatterns = [
    path("", views.space, name="space"),
    path("<uuid:merchant_id>/modifier/", views.edit, name="edit"),
]

from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("", views.plans, name="plans"),
    path("<slug:code>/", views.subscribe, name="subscribe"),
]

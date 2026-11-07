from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("", views.plans, name="plans"),
    path("paiement/retour/", views.checkout_return, name="checkout_return"),
    path("paiement/annule/", views.checkout_cancel, name="checkout_cancel"),
    path("paiement-test/<str:session_id>/", views.sandbox_checkout, name="sandbox_checkout"),
    path("webhook/stripe/", views.stripe_webhook, name="stripe_webhook"),
    path("<slug:code>/", views.subscribe, name="subscribe"),
]

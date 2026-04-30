from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.DealTrackLoginView.as_view(), name="login"),
    path("deconnexion/", views.DealTrackLogoutView.as_view(), name="logout"),
    path("inscription/", views.register, name="register"),
    path("profil/", views.profile, name="profile"),
    path("profil/export/", views.export_data, name="export"),
    path("profil/fermeture/", views.close_account, name="close"),
]

from django.urls import path

from . import views

app_name = "deals"

urlpatterns = [
    path("", views.deal_list, name="list"),
    path("publier/", views.deal_submit, name="submit"),
    path("deal/<slug:slug>/", views.deal_detail, name="detail"),
    path("deal/<slug:slug>/vote/", views.deal_vote, name="vote"),
    path("deal/<slug:slug>/commentaire/", views.comment_create, name="comment"),
]

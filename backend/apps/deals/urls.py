from django.urls import path

from . import views

app_name = "deals"

urlpatterns = [
    path("", views.deal_list, name="list"),
    path("publier/", views.deal_submit, name="submit"),
    path("commercants-locaux/", views.local_merchants, name="local"),
    path("deal/<slug:slug>/", views.deal_detail, name="detail"),
    path("deal/<slug:slug>/vote/", views.deal_vote, name="vote"),
    path("deal/<slug:slug>/comparer/", views.deal_compare, name="compare"),
    path("deal/<slug:slug>/commentaire/", views.comment_create, name="comment"),
    path("api/scrape/", views.scrape_link_view, name="scrape-link"),
]

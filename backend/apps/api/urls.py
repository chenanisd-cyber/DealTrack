from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .views import (
    CommentViewSet,
    DealViewSet,
    MeExportView,
    MeView,
    ModerationQueueViewSet,
    ThrottledTokenObtainView,
)

app_name = "api"

router = DefaultRouter()
router.register("deals", DealViewSet, basename="deal")
router.register("comments", CommentViewSet, basename="comment")
router.register("moderation/queue", ModerationQueueViewSet, basename="moderation-queue")

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
    path("me/export/", MeExportView.as_view(), name="me-export"),
    path("auth/token/", ThrottledTokenObtainView.as_view(), name="token-obtain"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token-verify"),
    path("", include(router.urls)),
]

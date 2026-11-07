"""
Points d'entrée de l'API v1.

Sécurisation, en résumé :
  - Authentification : JWT (clients tiers) ou session (navigateur). La session
    reste soumise au CSRF, DRF l'impose sur SessionAuthentication.
  - Autorisation : permission de classe pour l'accès à la vue, permission
    d'objet pour l'accès à la ressource, plus un queryset filtré par
    `for_user()`. Trois couches, parce qu'oublier l'une des trois arrive.
  - Débit : throttles globaux plus des throttles nommés sur les points chauds.
  - Écriture : le statut, l'auteur et la température sont fixés par le serveur.
"""

import logging

from django_filters import rest_framework as filters
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.deals.models import Comment, Deal, DealStatus, Vote
from apps.moderation.models import AuditLog

from .permissions import IsAuthorOrModerator, IsModerator, ReadOnlyOrAuthenticated
from .serializers import (
    CommentSerializer,
    DealDetailSerializer,
    DealListSerializer,
    DealWriteSerializer,
    VoteSerializer,
)
from .throttles import DealWriteThrottle, TokenObtainThrottle, VoteThrottle

logger = logging.getLogger("dealtrack.audit")


class DealFilter(filters.FilterSet):
    """
    Filtres déclaratifs. Les valeurs passent par les champs de formulaire de
    django-filter, donc une chaîne dans `min_price` renvoie un 400 propre au
    lieu d'atteindre la couche SQL.
    """

    min_price = filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = filters.NumberFilter(field_name="price", lookup_expr="lte")
    region = filters.CharFilter(field_name="regions__code", lookup_expr="iexact")
    category = filters.CharFilter(field_name="category__slug", lookup_expr="iexact")
    merchant = filters.CharFilter(field_name="merchant__slug", lookup_expr="iexact")
    local_only = filters.BooleanFilter(field_name="merchant__is_local_independent")
    min_temperature = filters.NumberFilter(field_name="temperature", lookup_expr="gte")

    class Meta:
        model = Deal
        fields = ["status", "is_cross_border", "language"]


class DealViewSet(viewsets.ModelViewSet):
    """
    GET    /api/v1/deals/            liste publique, filtrable et paginée
    GET    /api/v1/deals/{id}/       détail
    POST   /api/v1/deals/            soumission (authentifié)
    PATCH  /api/v1/deals/{id}/       modification (auteur si non publié, ou modérateur)
    DELETE /api/v1/deals/{id}/       retrait logique (jamais de DELETE SQL)
    POST   /api/v1/deals/{id}/vote/  vote chaud/froid
    POST   /api/v1/deals/{id}/publish/ validation (modérateur)
    """

    permission_classes = [ReadOnlyOrAuthenticated, IsAuthorOrModerator]
    filterset_class = DealFilter
    search_fields = ["title", "description", "merchant__name"]
    ordering_fields = ["temperature", "published_at", "price", "created_at"]
    ordering = ["-temperature"]
    lookup_field = "pk"

    def get_queryset(self):
        # Le filtre d'accès est appliqué ici, une fois, pour toutes les actions.
        return (
            Deal.objects.for_user(self.request.user)
            .select_related("merchant", "category", "submitted_by")
            .prefetch_related("regions", "translations")
        )

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return DealWriteSerializer
        if self.action == "retrieve":
            return DealDetailSerializer
        return DealListSerializer

    def get_throttles(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [DealWriteThrottle()]
        if self.action == "vote":
            return [VoteThrottle()]
        return super().get_throttles()

    def perform_destroy(self, instance):
        """DELETE effectue un retrait logique : les votes et commentaires restent."""
        instance.soft_delete(actor=self.request.user)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def vote(self, request, pk=None):
        deal = self.get_object()
        if deal.status != DealStatus.PUBLISHED:
            return Response(
                {"error": {"code": "not_votable", "detail": "Cette offre n'est pas publiée."}},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = VoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        temperature = Vote.cast(
            deal=deal, user=request.user, value=serializer.validated_data["value"]
        )
        return Response({"id": str(deal.pk), "temperature": temperature})

    @action(detail=True, methods=["post"], permission_classes=[IsModerator])
    def publish(self, request, pk=None):
        deal = self.get_object()
        if deal.status == DealStatus.PUBLISHED:
            return Response(
                {"error": {"code": "already_published", "detail": "Offre déjà publiée."}},
                status=status.HTTP_409_CONFLICT,
            )
        deal.publish(moderator=request.user, reason=request.data.get("reason", ""))
        return Response(DealDetailSerializer(deal, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[IsModerator])
    def reject(self, request, pk=None):
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return Response(
                {"error": {"code": "reason_required", "detail": "Un motif est obligatoire."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        deal = self.get_object()
        deal.reject(moderator=request.user, reason=reason)
        return Response(DealDetailSerializer(deal, context={"request": request}).data)


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [ReadOnlyOrAuthenticated, IsAuthorOrModerator]
    filterset_fields = ["deal"]

    def get_queryset(self):
        visible_deals = Deal.objects.for_user(self.request.user)
        return Comment.objects.filter(
            deleted_at__isnull=True, deal__in=visible_deals
        ).select_related("author", "deal")

    def perform_destroy(self, instance):
        instance.soft_delete(actor=self.request.user)


class MeView(APIView):
    """
    Espace personnel — vue explicite plutôt que ViewSet : la ressource « moi »
    n'a pas d'identifiant, et le routeur DRF ne mappe pas DELETE sur une route
    de liste.

      GET    /api/v1/me/   profil
      DELETE /api/v1/me/   effacement (art. 17), en désinscription douce
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                "id": str(user.pk),
                "email": user.email,
                "display_name": user.display_name,
                "role": user.role,
                "language": user.preferred_language,
                "joined": user.date_joined,
                "deals_submitted": user.submitted_deals.count(),
                "payments": user.payments.count(),
            }
        )

    def delete(self, request):
        """
        Désinscription. On n'appelle jamais delete() : les paiements sont en
        PROTECT et doivent le rester sept ans.
        """
        user = request.user
        user.soft_delete(reason="demande du membre via API", actor=user)
        if not user.payments.exists():
            # Sans obligation comptable, on peut anonymiser immédiatement.
            user.anonymise(actor=user)
            outcome = "anonymised"
        else:
            outcome = "soft_deleted_pending_retention"
        return Response(
            {
                "status": outcome,
                "detail": (
                    "Compte désactivé. Les données personnelles seront purgées à "
                    "l'expiration du délai légal de conservation comptable."
                    if outcome != "anonymised"
                    else "Compte désactivé et données personnelles anonymisées."
                ),
            },
            status=status.HTTP_200_OK,
        )


class MeExportView(APIView):
    """Portabilité des données (art. 20 RGPD)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        AuditLog.record(
            action=AuditLog.Action.USER_DATA_EXPORTED,
            actor=request.user,
            target=request.user,
            request=request,
        )
        return Response(request.user.export_personal_data())


class ThrottledTokenObtainView(TokenObtainPairView):
    """Obtention de jeton, limitée par IP."""

    permission_classes = [AllowAny]
    throttle_classes = [TokenObtainThrottle]


class ModerationQueueViewSet(viewsets.ReadOnlyModelViewSet):
    """File d'attente du back-office, en lecture seule et réservée."""

    permission_classes = [IsModerator]
    serializer_class = DealListSerializer

    def get_queryset(self):
        return (
            Deal.objects.filter(status=DealStatus.PENDING, deleted_at__isnull=True)
            .select_related("merchant", "category", "submitted_by")
            .order_by("created_at")
        )

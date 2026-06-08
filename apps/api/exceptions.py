"""
Gestionnaire d'exceptions unique de l'API.

Objectif : une réponse d'erreur au format constant, et surtout aucune fuite
d'information. Une trace Python ou un message de base de données renvoyé au
client renseigne un attaquant sur le schéma et les versions employées.
"""

import logging
import uuid

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_handler

logger = logging.getLogger("django.request")


def api_exception_handler(exc, context):
    request = context.get("request")
    trace_id = uuid.uuid4().hex[:12]  # rapproche la réponse et la ligne de log

    if isinstance(exc, DjangoValidationError):
        return _envelope(
            "validation_error",
            getattr(exc, "message_dict", {"detail": exc.messages}),
            status.HTTP_400_BAD_REQUEST,
            trace_id,
        )

    if isinstance(exc, IntegrityError):
        # Le message brut cite les noms de table et de contrainte : on le
        # journalise, on ne le renvoie pas.
        logger.warning("[%s] Violation d'intégrité : %s", trace_id, exc)
        return _envelope(
            "conflict",
            {"detail": "Cette opération entre en conflit avec une donnée existante."},
            status.HTTP_409_CONFLICT,
            trace_id,
        )

    if isinstance(exc, PermissionDenied):
        return _envelope(
            "permission_denied",
            {"detail": "Vous n'avez pas les droits pour cette action."},
            status.HTTP_403_FORBIDDEN,
            trace_id,
        )

    if isinstance(exc, Http404):
        # 404 volontaire là où un 403 serait plus exact : confirmer l'existence
        # d'une ressource interdite renseigne déjà l'attaquant.
        return _envelope(
            "not_found",
            {"detail": "Ressource introuvable."},
            status.HTTP_404_NOT_FOUND,
            trace_id,
        )

    response = drf_handler(exc, context)
    if response is not None:
        detail = response.data if isinstance(response.data, dict) else {"detail": response.data}
        return _envelope(
            _code_for(response.status_code), detail, response.status_code, trace_id
        )

    # Tout le reste est une anomalie serveur : trace complète côté journal,
    # message neutre côté client.
    logger.error(
        "[%s] Exception non gérée sur %s %s",
        trace_id,
        getattr(request, "method", "?"),
        getattr(request, "path", "?"),
        exc_info=True,
    )
    return _envelope(
        "server_error",
        {"detail": "Une erreur interne est survenue. Citez l'identifiant de trace au support."},
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        trace_id,
    )


def _envelope(code, detail, http_status, trace_id):
    return Response(
        {"error": {"code": code, "trace_id": trace_id, "detail": detail}},
        status=http_status,
    )


def _code_for(http_status):
    return {
        400: "bad_request",
        401: "authentication_required",
        403: "permission_denied",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        429: "throttled",
    }.get(http_status, "error")

"""Journalisation transversale des écritures authentifiées."""

import logging

audit_logger = logging.getLogger("dealtrack.audit")

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Le corps de ces requêtes contient des secrets : on trace l'accès, pas le contenu.
SENSITIVE_PATHS = ("/accounts/login", "/accounts/password", "/api/v1/auth/")


class AuditTrailMiddleware:
    """
    Trace toute requête modifiant l'état, ainsi que les 401/403/404 sur les
    espaces protégés. Complète AuditLog.record() : celui-ci consigne l'intention
    métier, celui-là consigne la requête HTTP brute.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._log(request, response)
        except Exception:  # une panne du journal ne doit jamais casser la réponse
            audit_logger.exception("Échec d'écriture dans la piste d'audit")
        return response

    def _log(self, request, response):
        user = getattr(request, "user", None)
        is_write = request.method in WRITE_METHODS
        is_denied = response.status_code in (401, 403)
        if not (is_write or is_denied):
            return

        sensitive = any(request.path.startswith(p) for p in SENSITIVE_PATHS)
        audit_logger.info(
            "%s %s -> %s user=%s ip=%s%s",
            request.method,
            request.path,
            response.status_code,
            getattr(user, "email", "anonyme") if user and user.is_authenticated else "anonyme",
            request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "-")),
            " [corps non journalisé]" if sensitive else "",
        )

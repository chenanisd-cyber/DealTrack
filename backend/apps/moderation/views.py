from django.shortcuts import render

from .models import AuditLog


def csrf_failure(request, reason=""):
    """
    Vue CSRF personnalisée : consigne l'échec puis renvoie une page lisible
    plutôt que la page technique de Django, qui en dit trop.
    """
    AuditLog.record(
        action=AuditLog.Action.CSRF_FAILURE,
        actor=getattr(request, "user", None),
        request=request,
        metadata={"reason": reason},
    )
    return render(request, "errors/csrf.html", {"reason": reason}, status=403)

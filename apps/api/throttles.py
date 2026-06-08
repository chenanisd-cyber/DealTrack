from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle


class VoteThrottle(ScopedRateThrottle):
    scope = "vote"


class DealWriteThrottle(ScopedRateThrottle):
    scope = "deal-write"


class TokenObtainThrottle(SimpleRateThrottle):
    """
    Limite la demande de jeton par IP. django-axes verrouille le compte visé ;
    ce throttle freine en amont le balayage d'une liste d'identifiants, qui ne
    déclencherait jamais le verrou d'un compte donné.
    """

    scope = "token"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}

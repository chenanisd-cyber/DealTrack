"""
Validateurs réutilisés côté formulaire HTML et côté API : une seule règle,
deux points d'entrée. Le navigateur peut être contourné, ces contrôles non.
"""

import re
import unicodedata

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

SEQUENCES = ("abcdefghijklmnopqrstuvwxyz", "azertyuiopqsdfghjklmwxcvbn", "0123456789")


class ComplexityValidator:
    """
    Exige au moins trois des quatre classes de caractères et rejette les
    suites de clavier. Complète les validateurs Django : longueur minimale,
    mot de passe courant, similarité avec l'identifiant.
    """

    def __init__(self, min_classes=3, max_sequence=4):
        self.min_classes = min_classes
        self.max_sequence = max_sequence

    def validate(self, password, user=None):
        classes = {
            "minuscule": bool(re.search(r"[a-z]", password)),
            "majuscule": bool(re.search(r"[A-Z]", password)),
            "chiffre": bool(re.search(r"\d", password)),
            "symbole": bool(re.search(r"[^\w\s]", password)),
        }
        found = sum(classes.values())
        if found < self.min_classes:
            raise ValidationError(
                ngettext(
                    "Le mot de passe doit combiner au moins %(n)d type de caractère "
                    "parmi minuscules, majuscules, chiffres et symboles.",
                    "Le mot de passe doit combiner au moins %(n)d types de caractères "
                    "parmi minuscules, majuscules, chiffres et symboles.",
                    self.min_classes,
                )
                % {"n": self.min_classes},
                code="password_not_complex",
            )

        lowered = password.lower()
        for seq in SEQUENCES:
            for i in range(len(seq) - self.max_sequence + 1):
                chunk = seq[i : i + self.max_sequence]
                if chunk in lowered or chunk[::-1] in lowered:
                    raise ValidationError(
                        _(
                            "Le mot de passe contient une suite de touches "
                            "trop évidente (« %(s)s »)."
                        )
                        % {"s": chunk},
                        code="password_sequential",
                    )

    def get_help_text(self):
        return _(
            "Au moins 12 caractères, combinant minuscules, majuscules, chiffres "
            "ou symboles, sans suite de touches."
        )


# --------------------------------------------------------------------------
# Numéro de TVA belge
# --------------------------------------------------------------------------
def validate_be_vat(value):
    """
    Vérifie un numéro de TVA belge : BE + 10 chiffres, le premier valant 0 ou 1,
    et une clé de contrôle telle que 97 - (base mod 97) == clé.

    C'est l'exemple type de validation qui ne peut pas rester côté client :
    un attaquant poste directement sur l'API.
    """
    if not value:
        return
    cleaned = re.sub(r"[\s.\-]", "", str(value)).upper()
    if not re.fullmatch(r"BE[01]\d{9}", cleaned):
        raise ValidationError(
            _("Format attendu : BE suivi de 10 chiffres, par exemple BE0123456749."),
            code="vat_format",
        )
    digits = cleaned[2:]
    base, check = int(digits[:8]), int(digits[8:])
    if 97 - (base % 97) != check:
        raise ValidationError(
            _("La clé de contrôle du numéro de TVA est incorrecte."), code="vat_checksum"
        )


def validate_no_control_characters(value):
    """
    Refuse les caractères de contrôle et les marques de direction Unicode,
    utilisés pour masquer une charge utile ou inverser un texte affiché.
    """
    for char in str(value):
        category = unicodedata.category(char)
        if category in {"Cc", "Cf"} and char not in "\n\r\t":
            raise ValidationError(
                _("Le texte contient un caractère de contrôle interdit."),
                code="control_character",
            )

"""
Images envoyées par les utilisateurs (photo d'offre, logo de marchand).

Un fichier envoyé est une entrée non fiable comme une autre (OWASP A04 /
« Unrestricted File Upload »). Quatre contrôles, du moins coûteux au plus sûr :

1. extension autorisée : jpg, jpeg, png, webp. Le SVG est exclu : c'est du XML
   qui peut contenir du JavaScript (XSS stocké) ;
2. taille maximale : 2 Mo ;
3. contenu réellement décodé par Pillow : un script renommé « photo.jpg »
   est refusé, et le format détecté doit correspondre à la liste blanche ;
4. dimensions plafonnées : protège contre les « bombes de décompression »
   (une petite image PNG qui occupe des gigaoctets une fois décodée).

Le nom d'origine n'est jamais réutilisé : le fichier est renommé avec un UUID,
ce qui évite les collisions, les noms piégés (../../) et la fuite
d'informations contenues dans le nom.
"""

import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _

ALLOWED_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_BYTES = 2 * 1024 * 1024  # 2 Mo
MAX_IMAGE_SIDE = 6000  # pixels

validate_image_extension = FileExtensionValidator(allowed_extensions=ALLOWED_EXTENSIONS)


def validate_image_size(file):
    if file.size > MAX_IMAGE_BYTES:
        raise ValidationError(_("L'image dépasse 2 Mo."), code="image_too_large")


def validate_image_content(file):
    """Décode l'image avec Pillow et vérifie son format réel et ses dimensions."""
    from PIL import Image, UnidentifiedImageError

    try:
        file.seek(0)
        with Image.open(file) as image:
            image_format = image.format
            width, height = image.size
            image.verify()  # détecte un fichier tronqué ou corrompu
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ValidationError(
            _("Le fichier n'est pas une image valide."), code="invalid_image"
        ) from exc
    finally:
        file.seek(0)

    if image_format not in ALLOWED_FORMATS:
        raise ValidationError(
            _("Format refusé : JPEG, PNG ou WebP uniquement."), code="image_format"
        )
    if width > MAX_IMAGE_SIDE or height > MAX_IMAGE_SIDE:
        raise ValidationError(
            _("Image trop grande : 6000 pixels de côté au maximum."), code="image_dimensions"
        )


IMAGE_VALIDATORS = [validate_image_extension, validate_image_size, validate_image_content]


def _random_name(folder, filename):
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension == "jpeg":
        extension = "jpg"
    return f"{folder}/{uuid.uuid4().hex}.{extension}"


def deal_image_path(instance, filename):
    return _random_name("deals", filename)


def merchant_logo_path(instance, filename):
    return _random_name("merchants", filename)

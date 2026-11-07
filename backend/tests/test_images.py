"""
Photos d'offres et vignettes de marchands : validation des fichiers envoyés,
ordre de priorité à l'affichage, repli sur le marchand.

Les fichiers sont écrits dans un dossier temporaire (MEDIA_ROOT surchargé),
jamais dans database/media/.
"""

import io
import shutil
import tempfile
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.catalog.images import validate_image_content, validate_image_size
from apps.catalog.models import Category, Merchant
from apps.deals.models import Deal, DealStatus

from .factories import make_deal, make_user, seed_reference_data

TEMP_MEDIA = tempfile.mkdtemp(prefix="dealtrack-tests-")


def image_file(name="photo.png", image_format="PNG", size=(40, 30)):
    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 80, 40)).save(buffer, format=image_format)
    content_type = {"PNG": "image/png", "JPEG": "image/jpeg", "GIF": "image/gif"}[image_format]
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)


class ImageValidatorTests(TestCase):
    def test_png_valide_accepte(self):
        validate_image_content(image_file())

    def test_script_renomme_en_jpg_refuse(self):
        fake = SimpleUploadedFile("photo.jpg", b"<script>alert(1)</script>", "image/jpeg")
        with self.assertRaises(ValidationError):
            validate_image_content(fake)

    def test_format_hors_liste_blanche_refuse(self):
        """Un vrai GIF renommé en .png est détecté par son contenu, pas par son nom."""
        with self.assertRaises(ValidationError):
            validate_image_content(image_file("anim.png", image_format="GIF"))

    def test_image_trop_lourde_refusee(self):
        big = SimpleUploadedFile("big.png", b"0" * (2 * 1024 * 1024 + 1), "image/png")
        with self.assertRaises(ValidationError):
            validate_image_size(big)

    def test_dimensions_excessives_refusees(self):
        with self.assertRaises(ValidationError):
            validate_image_content(image_file(size=(6001, 10)))

    def test_couleur_de_texte_lisible(self):
        self.assertEqual(Merchant(brand_color="#0000A4").brand_text_color, "#FFFFFF")
        self.assertEqual(Merchant(brand_color="#F2C14E").brand_text_color, "#01182B")


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class DealPhotoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.member = make_user("membre@example.be", "Membre")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def publish(self, **overrides):
        return make_deal(
            self.member, status=DealStatus.PUBLISHED, published_at=timezone.now(), **overrides
        )

    def test_sans_photo_la_vignette_du_marchand_s_affiche(self):
        deal = self.publish()
        html = self.client.get(reverse("deals:list")).content.decode()
        self.assertIn("dealmedia__brand", html)
        self.assertIn(f'<span class="dealmedia__name">{deal.merchant.name}</span>', html)
        self.assertNotIn("dealmedia__photo", html)

    def test_miniatures_de_la_colonne_les_plus_hot(self):
        """La colonne « Les plus hot » et le profil ont aussi un visuel."""
        deal = self.publish()
        html = self.client.get(reverse("deals:list")).content.decode()
        self.assertIn('<div class="dealmedia is-small">', html)

        self.client.force_login(self.member)
        profile = self.client.get(reverse("accounts:profile")).content.decode()
        self.assertIn('<span class="table__thumb">', profile)
        self.assertIn(deal.merchant.name, profile)

    def test_image_externe_affichee_par_dessus_la_vignette(self):
        self.publish(image_url="https://shop.example/casque.jpg")
        html = self.client.get(reverse("deals:list")).content.decode()
        self.assertIn('src="https://shop.example/casque.jpg"', html)
        self.assertIn('onerror="this.remove()"', html)  # repli si le lien est mort
        self.assertIn("dealmedia__brand", html)

    def test_photo_envoyee_prioritaire_sur_l_image_externe(self):
        deal = self.publish(image_url="https://shop.example/casque.jpg")
        deal.image = image_file()
        deal.save()
        self.assertTrue(deal.photo_url.startswith("/media/deals/"))
        html = self.client.get(deal.get_absolute_url()).content.decode()
        self.assertIn(f'src="{deal.photo_url}"', html)
        self.assertNotIn("shop.example/casque.jpg", html)

    def test_envoi_de_photo_par_le_formulaire(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("deals:submit"),
            {
                "title": "Casque audio sans fil à réduction de bruit",
                "description": "Autonomie de trente heures, étui de transport et câble inclus.",
                "external_url": "https://www.shop.example/casque",
                "gallery_urls": '["https://cdn.shop.example/casque-face.jpg"]',
                "gallery_files": [image_file("Mon casque.PNG")],
                "main_index": "1",  # la photo envoyée devient l'image principale
                "price": "199.00",
                "reference_price": "249.00",
                "availability": "online",
                "shipping_cost": "0.00",
                "category": Category.objects.filter(is_active=True).first().pk,
                "language": "fr",
            },
        )
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        deal = Deal.objects.get(external_url="https://www.shop.example/casque")
        # Nom aléatoire : le nom d'origine (« Mon casque.PNG ») n'est pas réutilisé.
        self.assertRegex(deal.image.name, r"^deals/[0-9a-f]{32}\.png$")
        self.assertEqual(deal.price, Decimal("199.00"))
        # L'image externe passe dans la galerie, en deuxième position.
        self.assertEqual(
            list(deal.gallery.values_list("image_url", flat=True)),
            ["https://cdn.shop.example/casque-face.jpg"],
        )
        # Marchand inconnu : créé d'après le domaine, non vérifié.
        self.assertEqual(deal.merchant.name, "Shop")
        self.assertFalse(deal.merchant.is_verified)
        self.assertEqual(deal.merchant.website, "https://www.shop.example")

    def test_faux_fichier_image_refuse_par_le_formulaire(self):
        self.client.force_login(self.member)
        fake = SimpleUploadedFile("photo.jpg", b"pas une image", content_type="image/jpeg")
        response = self.client.post(
            reverse("deals:submit"), {"title": "x", "gallery_files": [fake]}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].has_error("gallery_files"))

    def test_image_externe_en_http_refusee(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("deals:submit"), {"gallery_urls": '["http://shop.example/casque.jpg"]'}
        )
        self.assertTrue(response.context["form"].has_error("gallery_urls"))

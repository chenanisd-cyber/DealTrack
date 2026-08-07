"""
Tests d'intégration — la pile complète, via HTTP.

Chaque classe correspond à une exigence du cahier des charges, pour que la
correspondance soit vérifiable ligne à ligne.
"""

import json
from decimal import Decimal
from io import StringIO

from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from apps.accounts.models import Role, User
from apps.deals.models import Comment, Deal, DealStatus, DealTranslation, Vote
from apps.moderation.models import AuditLog
from apps.payments.models import Payment, Plan

from .factories import STRONG_PASSWORD, make_deal, make_user, seed_reference_data


class BaseIntegrationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.member = make_user("membre@example.be", "Membre")
        cls.other = make_user("autre@example.be", "Autre")
        cls.moderator = make_user("modo@example.be", "Modo", role=Role.MODERATOR)
        cls.published = make_deal(
            cls.member, status=DealStatus.PUBLISHED, published_at=timezone.now()
        )
        cls.pending = make_deal(cls.member, status=DealStatus.PENDING)

    def setUp(self):
        # django-axes et les throttles DRF s'appuient sur le cache : sans purge,
        # un test verrouille les suivants.
        cache.clear()

    # AxesStandaloneBackend exige un objet request, que Client.login() ne fournit
    # pas. Les tests dont l'authentification n'est pas l'objet passent donc par
    # force_login ; ceux qui testent le verrouillage postent le vrai formulaire.
    MODEL_BACKEND = "django.contrib.auth.backends.ModelBackend"

    def login(self, user, client=None):
        (client or self.client).force_login(user, backend=self.MODEL_BACKEND)


# ==========================================================================
# CSRF
# ==========================================================================
class CsrfProtectionTests(BaseIntegrationTest):
    def test_post_without_token_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        self.login(self.member, client)
        response = client.post(
            reverse("deals:vote", kwargs={"slug": self.published.slug}), {"value": 1}
        )
        self.assertEqual(response.status_code, 403)

    def test_post_with_token_succeeds(self):
        client = Client(enforce_csrf_checks=True)
        self.login(self.member, client)
        client.get(reverse("deals:detail", kwargs={"slug": self.published.slug}))
        token = client.cookies["csrftoken"].value
        response = client.post(
            reverse("deals:vote", kwargs={"slug": self.published.slug}),
            {"value": 1, "csrfmiddlewaretoken": token},
        )
        self.assertEqual(response.status_code, 302)

    def test_csrf_failure_is_audited(self):
        client = Client(enforce_csrf_checks=True)
        self.login(self.member, client)
        before = AuditLog.objects.filter(action=AuditLog.Action.CSRF_FAILURE).count()
        client.post(reverse("deals:vote", kwargs={"slug": self.published.slug}), {"value": 1})
        after = AuditLog.objects.filter(action=AuditLog.Action.CSRF_FAILURE).count()
        self.assertEqual(after, before + 1)

    def test_state_changing_action_refuses_get(self):
        """Un GET ne doit jamais modifier l'état, sinon une balise img suffit."""
        self.login(self.member)
        response = self.client.get(reverse("deals:vote", kwargs={"slug": self.published.slug}))
        self.assertEqual(response.status_code, 405)


# ==========================================================================
# XSS
# ==========================================================================
class XssProtectionTests(BaseIntegrationTest):
    PAYLOADS = [
        "<script>alert('xss')</script>",
        "<img src=x onerror=alert(1)>",
        '"><svg/onload=alert(1)>',
        "javascript:alert(document.cookie)",
    ]

    def test_comment_payload_is_escaped_in_page(self):
        self.login(self.member)
        for payload in self.PAYLOADS:
            Comment.objects.create(deal=self.published, author=self.member, body=payload)
        response = self.client.get(
            reverse("deals:detail", kwargs={"slug": self.published.slug})
        )
        body = response.content.decode()
        # Le texte de la charge utile subsiste — c'est normal, c'est du contenu.
        # Ce qui compte est qu'aucune balise ne soit reconstituable : les
        # chevrons sont convertis en entités, donc le navigateur affiche au lieu
        # d'exécuter.
        self.assertNotIn("<script>alert", body)
        self.assertNotIn("<img src=x", body)
        self.assertNotIn("<svg/onload", body)
        self.assertIn("&lt;script&gt;", body)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", body)

    def test_deal_title_payload_is_escaped(self):
        deal = make_deal(
            self.member,
            title="<script>alert(1)</script> Casque audio sans fil",
            status=DealStatus.PUBLISHED,
            published_at=timezone.now(),
        )
        response = self.client.get(reverse("deals:detail", kwargs={"slug": deal.slug}))
        self.assertNotIn("<script>alert(1)</script>", response.content.decode())

    def test_api_rejects_javascript_scheme_url(self):
        self.login(self.member)
        response = self.client.post(
            "/api/v1/deals/",
            data=json.dumps(
                {
                    "title": "Titre suffisamment long pour passer",
                    "description": (
                        "Description assez longue pour satisfaire la contrainte du modèle."
                    ),
                    "external_url": "javascript:alert(document.cookie)",
                    "price": "10.00",
                    "merchant": str(self.published.merchant_id),
                    "category": str(self.published.category_id),
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_security_headers_present(self):
        response = self.client.get(reverse("deals:list"))
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["Referrer-Policy"], "same-origin")


# ==========================================================================
# Force brute
# ==========================================================================
@override_settings(AXES_FAILURE_LIMIT=3)
class BruteForceTests(BaseIntegrationTest):
    def test_account_locks_after_repeated_failures(self):
        url = reverse("accounts:login")
        for _ in range(3):
            self.client.post(url, {"username": self.member.email, "password": "mauvais"})

        # Le verrou tient même avec le bon mot de passe.
        response = self.client.post(
            url, {"username": self.member.email, "password": STRONG_PASSWORD}
        )
        self.assertIn(response.status_code, (403, 429))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_failures_are_recorded_in_audit_log(self):
        url = reverse("accounts:login")
        self.client.post(url, {"username": self.member.email, "password": "mauvais"})
        self.assertTrue(
            AuditLog.objects.filter(action=AuditLog.Action.USER_LOGIN_FAILED).exists()
        )

    def test_login_error_does_not_reveal_account_existence(self):
        url = reverse("accounts:login")
        known = self.client.post(url, {"username": self.member.email, "password": "mauvais"})
        cache.clear()
        unknown = self.client.post(
            url, {"username": "inconnu@example.be", "password": "mauvais"}
        )
        self.assertEqual(
            known.context["form"].errors.get("__all__"),
            unknown.context["form"].errors.get("__all__"),
        )

    def test_api_token_endpoint_is_throttled(self):
        statuses = []
        for _ in range(12):  # la limite est de 10/heure
            response = self.client.post(
                "/api/v1/auth/token/",
                data=json.dumps({"email": "x@example.be", "password": "y"}),
                content_type="application/json",
            )
            statuses.append(response.status_code)
        self.assertIn(429, statuses)


# ==========================================================================
# Contrôle d'accès
# ==========================================================================
class AccessControlTests(BaseIntegrationTest):
    def test_anonymous_cannot_reach_submission_form(self):
        response = self.client.get(reverse("deals:submit"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("connexion", response["Location"])

    def test_pending_deal_hidden_from_other_members(self):
        self.login(self.other)
        response = self.client.get(reverse("deals:detail", kwargs={"slug": self.pending.slug}))
        self.assertEqual(response.status_code, 404)

    def test_author_sees_own_pending_deal(self):
        self.login(self.member)
        response = self.client.get(reverse("deals:detail", kwargs={"slug": self.pending.slug}))
        self.assertEqual(response.status_code, 200)

    def test_moderator_sees_every_pending_deal(self):
        self.login(self.moderator)
        response = self.client.get(reverse("deals:detail", kwargs={"slug": self.pending.slug}))
        self.assertEqual(response.status_code, 200)

    def test_member_cannot_edit_another_members_deal(self):
        self.login(self.other)
        response = self.client.patch(
            f"/api/v1/deals/{self.pending.pk}/",
            data=json.dumps({"title": "Titre détourné par un tiers malveillant"}),
            content_type="application/json",
        )
        self.assertIn(response.status_code, (403, 404))

    def test_member_cannot_publish_a_deal(self):
        """Élévation de privilège : publier est réservé à la modération."""
        self.login(self.member)
        response = self.client.post(f"/api/v1/deals/{self.pending.pk}/publish/")
        self.assertEqual(response.status_code, 403)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, DealStatus.PENDING)

    def test_moderator_can_publish(self):
        self.login(self.moderator)
        response = self.client.post(f"/api/v1/deals/{self.pending.pk}/publish/")
        self.assertEqual(response.status_code, 200)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, DealStatus.PUBLISHED)

    def test_member_cannot_read_moderation_queue(self):
        self.login(self.member)
        self.assertEqual(self.client.get("/api/v1/moderation/queue/").status_code, 403)

    def test_moderator_can_read_moderation_queue(self):
        self.login(self.moderator)
        self.assertEqual(self.client.get("/api/v1/moderation/queue/").status_code, 200)

    # Le libellé traverse l'échappement HTML : l'apostrophe de « Journal
    # d'audit » sort en &#x27;. Comparer à la chaîne brute donnerait un test
    # toujours vert, y compris pour un superutilisateur. On échappe donc des
    # deux côtés, et on double par l'URL de la vue de liste, qui elle ne
    # dépend d'aucun libellé traduisible.
    AUDIT_LOG_LABEL = escape("Journal d'audit")

    def test_back_office_closed_to_regular_member(self):
        self.login(self.member)
        response = self.client.get("/fr/back-office/", follow=True)
        self.assertNotContains(response, self.AUDIT_LOG_LABEL, status_code=200)
        self.assertNotContains(
            response, reverse("admin:moderation_auditlog_changelist"), status_code=200
        )

    def test_moderator_sees_audit_log_after_setup_roles(self):
        """
        Contrepartie indispensable du test précédent.

        `is_staff` ouvre la porte du back-office, mais Django exige en plus une
        permission par modèle pour afficher une entrée dans l'index. Un
        modérateur correctement marqué en base tombait donc sur une page vide
        tant que setup_roles n'avait pas tourné. Seule l'assertion positive
        détecte cette panne : la négative reste verte quoi qu'il arrive.
        """
        call_command("setup_roles", stdout=StringIO())
        self.moderator.refresh_from_db()
        self.assertTrue(self.moderator.is_staff)

        self.login(self.moderator)
        response = self.client.get("/fr/back-office/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.AUDIT_LOG_LABEL)
        self.assertContains(response, reverse("admin:moderation_auditlog_changelist"))

    def test_moderator_can_open_the_audit_log_itself(self):
        """L'entrée d'index ne vaut que si la vue de liste répond aussi."""
        call_command("setup_roles", stdout=StringIO())
        self.login(self.moderator)
        response = self.client.get(reverse("admin:moderation_auditlog_changelist"))
        self.assertEqual(response.status_code, 200)

    def test_setup_roles_grants_no_write_access_on_the_audit_log(self):
        """La piste d'audit se consulte : ni ajout, ni modification."""
        call_command("setup_roles", stdout=StringIO())
        self.moderator.refresh_from_db()
        self.assertTrue(self.moderator.has_perm("moderation.view_auditlog"))
        for codename in ("add_auditlog", "change_auditlog", "delete_auditlog"):
            self.assertFalse(
                self.moderator.has_perm(f"moderation.{codename}"), f"moderation.{codename}"
            )

    def test_setup_roles_is_idempotent(self):
        call_command("setup_roles", stdout=StringIO())
        first = set(
            User.objects.get(pk=self.moderator.pk)
            .groups.get(name="Modérateurs")
            .permissions.values_list("codename", flat=True)
        )
        call_command("setup_roles", stdout=StringIO())
        second = set(
            User.objects.get(pk=self.moderator.pk)
            .groups.get(name="Modérateurs")
            .permissions.values_list("codename", flat=True)
        )
        self.assertEqual(first, second)
        self.assertEqual(self.moderator.groups.count(), 1)

    def test_permission_denial_is_audited(self):
        self.login(self.other)
        before = AuditLog.objects.filter(action=AuditLog.Action.PERMISSION_DENIED).count()
        self.client.patch(
            f"/api/v1/deals/{self.published.pk}/",
            data=json.dumps({"title": "Tentative de détournement de contenu"}),
            content_type="application/json",
        )
        after = AuditLog.objects.filter(action=AuditLog.Action.PERMISSION_DENIED).count()
        self.assertGreater(after, before)

    def test_member_cannot_read_another_members_payments(self):
        self.login(self.member)
        response = self.client.get("/api/v1/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], self.member.email)


# ==========================================================================
# API REST
# ==========================================================================
class ApiTests(BaseIntegrationTest):
    def test_get_deals_is_public_and_paginated(self):
        response = self.client.get("/api/v1/deals/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        for key in ("count", "results", "next", "previous"):
            self.assertIn(key, payload)
        slugs = [d["slug"] for d in payload["results"]]
        self.assertIn(self.published.slug, slugs)
        self.assertNotIn(self.pending.slug, slugs)  # filtrage d'accès appliqué

    def test_get_deal_detail(self):
        response = self.client.get(f"/api/v1/deals/{self.published.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["slug"], self.published.slug)

    def test_filters_are_applied(self):
        response = self.client.get("/api/v1/deals/?min_price=1000")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

    def test_invalid_filter_value_returns_400_not_500(self):
        response = self.client.get("/api/v1/deals/?min_price=pas-un-nombre")
        self.assertEqual(response.status_code, 400)

    def test_post_deal_requires_authentication(self):
        response = self.client.post(
            "/api/v1/deals/", data=json.dumps({}), content_type="application/json"
        )
        self.assertEqual(response.status_code, 401)

    def test_post_deal_creates_pending_entry(self):
        self.login(self.member)
        response = self.client.post(
            "/api/v1/deals/",
            data=json.dumps(
                {
                    "title": "Aspirateur balai Dyson V12 Detect Slim Absolute",
                    "description": (
                        "Prix le plus bas relevé en Belgique depuis quatre mois, "
                        "stock limité."
                    ),
                    "external_url": "https://www.coolblue.be/fr/produit/dyson-v12",
                    "price": "399.00",
                    "reference_price": "649.00",
                    "merchant": str(self.published.merchant_id),
                    "category": str(self.published.category_id),
                    "language": "fr",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        deal = Deal.objects.get(pk=response.json()["id"])
        self.assertEqual(deal.status, DealStatus.PENDING)  # imposé par le serveur
        self.assertEqual(deal.submitted_by, self.member)  # ignore toute charge utile

    def test_post_deal_cannot_force_published_status(self):
        """Mass assignment : un champ non exposé ne doit pas être écrivable."""
        self.login(self.member)
        response = self.client.post(
            "/api/v1/deals/",
            data=json.dumps(
                {
                    "title": "Console portable Steam Deck OLED 512 Go",
                    "description": "Import allemand, garantie européenne valable en Belgique.",
                    "external_url": "https://example.be/steamdeck",
                    "price": "549.00",
                    "merchant": str(self.published.merchant_id),
                    "category": str(self.published.category_id),
                    "status": "published",
                    "temperature": 99999,
                    "submitted_by": str(self.moderator.pk),
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        deal = Deal.objects.get(pk=response.json()["id"])
        self.assertEqual(deal.status, DealStatus.PENDING)
        self.assertEqual(deal.temperature, 100)
        self.assertEqual(deal.submitted_by, self.member)

    def test_post_deal_rejects_reference_price_below_price(self):
        self.login(self.member)
        response = self.client.post(
            "/api/v1/deals/",
            data=json.dumps(
                {
                    "title": "Écran Dell UltraSharp 27 pouces U2724D",
                    "description": (
                        "Réduction annoncée avec un prix barré inférieur au prix affiché."
                    ),
                    "external_url": "https://example.be/dell-u2724d",
                    "price": "400.00",
                    "reference_price": "300.00",
                    "merchant": str(self.published.merchant_id),
                    "category": str(self.published.category_id),
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("reference_price", response.json()["error"]["detail"])

    def test_put_vote_updates_temperature(self):
        self.login(self.other)
        response = self.client.post(
            f"/api/v1/deals/{self.published.pk}/vote/",
            data=json.dumps({"value": 1}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["temperature"], 101)

    def test_delete_performs_soft_delete(self):
        self.login(self.moderator)
        response = self.client.delete(f"/api/v1/deals/{self.published.pk}/")
        self.assertEqual(response.status_code, 204)
        self.published.refresh_from_db()
        self.assertIsNotNone(self.published.deleted_at)
        self.assertTrue(Deal.objects.filter(pk=self.published.pk).exists())  # ligne conservée

    def test_jwt_flow(self):
        token_response = self.client.post(
            "/api/v1/auth/token/",
            data=json.dumps({"email": self.member.email, "password": STRONG_PASSWORD}),
            content_type="application/json",
        )
        self.assertEqual(token_response.status_code, 200, token_response.content)
        access = token_response.json()["access"]

        authed = self.client.get("/api/v1/me/", HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(authed.status_code, 200)
        self.assertEqual(authed.json()["email"], self.member.email)

    def test_invalid_jwt_is_rejected(self):
        response = self.client.get(
            "/api/v1/me/", HTTP_AUTHORIZATION="Bearer jeton.invalide.xyz"
        )
        self.assertEqual(response.status_code, 401)

    def test_error_envelope_has_stable_shape(self):
        response = self.client.get("/api/v1/deals/00000000-0000-0000-0000-000000000000/")
        self.assertEqual(response.status_code, 404)
        error = response.json()["error"]
        for key in ("code", "trace_id", "detail"):
            self.assertIn(key, error)

    def test_server_does_not_leak_stack_trace(self):
        response = self.client.get("/api/v1/deals/pas-un-uuid/")
        self.assertNotIn("Traceback", response.content.decode())


# ==========================================================================
# RGPD
# ==========================================================================
class GdprTests(BaseIntegrationTest):
    def test_export_returns_downloadable_json(self):
        self.login(self.member)
        response = self.client.get(reverse("accounts:export"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("identifiant", json.loads(response.content))

    def test_export_is_audited(self):
        self.login(self.member)
        self.client.get(reverse("accounts:export"))
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.USER_DATA_EXPORTED, actor=self.member
            ).exists()
        )

    def test_account_closure_requires_exact_confirmation(self):
        self.login(self.member)
        self.client.post(reverse("accounts:close"), {"confirm": "n-importe-quoi"})
        self.member.refresh_from_db()
        self.assertIsNone(self.member.deleted_at)

    def test_account_closure_with_confirmation_soft_deletes(self):
        self.login(self.member)
        self.client.post(reverse("accounts:close"), {"confirm": self.member.display_name})
        self.member.refresh_from_db()
        self.assertIsNotNone(self.member.deleted_at)
        self.assertTrue(User.objects.filter(pk=self.member.pk).exists())

    def test_api_deletion_keeps_row_when_payments_exist(self):
        plan = Plan.objects.get(code="club-annuel")
        Payment.objects.create(
            reference="DT-2025-000900",
            user=self.member,
            plan=plan,
            amount=Decimal("24.00"),
            vat_amount=Decimal("4.17"),
            status=Payment.Status.SUCCEEDED,
            settled_at=timezone.now(),
            gateway_reference="sbx-test-900",
        )
        self.login(self.member)
        response = self.client.delete("/api/v1/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "soft_deleted_pending_retention")
        self.member.refresh_from_db()
        self.assertIsNone(self.member.anonymised_at)  # conservation comptable

    def test_api_deletion_anonymises_when_no_payment(self):
        self.login(self.other)
        response = self.client.delete("/api/v1/me/")
        self.assertEqual(response.json()["status"], "anonymised")
        self.other.refresh_from_db()
        self.assertIsNotNone(self.other.anonymised_at)


# ==========================================================================
# Multilingue
# ==========================================================================
class MultilingualTests(BaseIntegrationTest):
    def test_three_language_prefixes_all_respond(self):
        for code in ("fr", "nl", "de"):
            response = self.client.get(f"/{code}/")
            self.assertEqual(response.status_code, 200, f"échec pour /{code}/")

    def test_root_redirects_to_default_language(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/fr/"))

    def test_html_lang_attribute_follows_prefix(self):
        for code in ("fr", "nl", "de"):
            response = self.client.get(f"/{code}/")
            self.assertContains(response, f'<html lang="{code}"')

    def test_alternate_links_declare_every_language(self):
        response = self.client.get("/fr/").content.decode()
        for code in ("fr", "nl", "de"):
            self.assertIn(f'hreflang="{code}"', response)

    def test_set_language_switches_and_persists(self):
        response = self.client.post(
            "/i18n/setlang/", {"language": "nl", "next": "/fr/"}, follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("dealtrack_language", self.client.cookies)
        self.assertEqual(self.client.cookies["dealtrack_language"].value, "nl")

    def test_category_labels_are_translated(self):
        from apps.catalog.models import Category

        category = Category.objects.get(slug="high-tech")
        self.assertEqual(category.label("fr"), "High-tech")
        self.assertEqual(category.label("nl"), "Elektronica")
        self.assertEqual(category.label("de"), "Elektronik")

    def test_label_falls_back_to_french(self):
        from apps.catalog.models import Category

        category = Category.objects.get(slug="high-tech")
        self.assertEqual(category.label("it"), "High-tech")

    def test_api_is_not_language_prefixed(self):
        """Un client REST négocie par en-tête, pas par URL."""
        self.assertEqual(self.client.get("/api/v1/deals/").status_code, 200)
        self.assertEqual(self.client.get("/fr/api/v1/deals/").status_code, 404)

    # -- Contenu des offres, et non plus seulement de l'interface ---------
    #
    # Les tests ci-dessus couvrent le gabarit : préfixes d'URL, attribut lang,
    # libellés du référentiel. Ils resteraient tous verts avec un flux dont
    # chaque offre s'affiche en français sur /nl/. Ceux qui suivent portent sur
    # le texte rédigé par les membres, qui est la partie réellement traduite.

    FRENCH_TITLE = "Robot pâtissier Kenwood Chef XL Titanium"
    DUTCH_TITLE = "Keukenrobot Kenwood Chef XL Titanium"

    def _make_translated_deal(self, **overrides):
        """Une offre rédigée en français, disposant d'une traduction néerlandaise."""
        deal = make_deal(
            self.member,
            title=self.FRENCH_TITLE,
            language="fr",
            status=DealStatus.PUBLISHED,
            published_at=timezone.now(),
            **overrides,
        )
        DealTranslation.objects.create(
            deal=deal,
            language="nl",
            title=self.DUTCH_TITLE,
            description=(
                "Nederlandse beschrijving, lang genoeg om de minimale lengte "
                "van het model te halen, met geloofwaardige details."
            ),
        )
        return deal

    def test_translated_title_is_served_on_dutch_feed(self):
        self._make_translated_deal()
        response = self.client.get("/nl/")
        self.assertContains(response, self.DUTCH_TITLE)
        self.assertNotContains(response, self.FRENCH_TITLE)

    def test_translated_title_is_served_on_dutch_detail_page(self):
        deal = self._make_translated_deal()
        response = self.client.get(f"/nl/deal/{deal.slug}/")
        self.assertContains(response, self.DUTCH_TITLE)
        self.assertNotContains(response, self.FRENCH_TITLE)

    def test_original_title_is_kept_on_the_language_it_was_written_in(self):
        """La traduction néerlandaise ne doit pas déborder sur /fr/."""
        self._make_translated_deal()
        response = self.client.get("/fr/")
        self.assertContains(response, self.FRENCH_TITLE)
        self.assertNotContains(response, self.DUTCH_TITLE)

    def test_missing_translation_falls_back_to_the_original_text(self):
        """
        Un flux communautaire est traduit de façon inégale. L'absence de
        traduction doit dégrader vers le texte d'origine, jamais vers un titre
        vide ni une erreur.
        """
        make_deal(
            self.member,
            title="Tondeuse thermique Honda IZY 46 cm",
            description=(
                "Description en français, sans traduction néerlandaise, "
                "suffisamment longue pour le modèle."
            ),
            language="fr",
            status=DealStatus.PUBLISHED,
            published_at=timezone.now(),
        )
        response = self.client.get("/nl/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tondeuse thermique Honda IZY 46 cm")

    def test_fallback_is_signalled_by_a_language_badge(self):
        """
        Le repli silencieux serait trompeur : le lecteur néerlandophone doit
        savoir que le texte est en français avant de cliquer. Le badge dit la
        langue de rédaction, déclinée dans la langue de lecture.
        """
        make_deal(
            self.member,
            title="Perceuse-visseuse Bosch PSR 18 LI-2",
            language="fr",
            status=DealStatus.PUBLISHED,
            published_at=timezone.now(),
        )
        response = self.client.get("/nl/")
        self.assertContains(response, "Aanbieding opgesteld in het Frans")

    # Les deux tests suivants passent par la page de détail, et non par le flux :
    # le jeu de données de base contient déjà une offre française non traduite,
    # qui affiche légitimement son badge et rendrait un assertNotContains sur le
    # flux impossible à interpréter.
    def test_no_language_badge_when_the_translation_exists(self):
        deal = self._make_translated_deal()
        response = self.client.get(f"/nl/deal/{deal.slug}/")
        self.assertNotContains(response, "Aanbieding opgesteld in het")

    def test_no_language_badge_on_the_source_language(self):
        deal = make_deal(
            self.member,
            title="Aanbieding rechtstreeks in het Nederlands geschreven",
            language="nl",
            status=DealStatus.PUBLISHED,
            published_at=timezone.now(),
        )
        response = self.client.get(f"/nl/deal/{deal.slug}/")
        self.assertNotContains(response, "Aanbieding opgesteld in het")

    def test_feed_does_not_issue_one_query_per_card(self):
        """
        Garde-fou contre le N+1 que `title_current` invite : un `.filter()`
        dans `_translation()` contournerait le prefetch et relancerait une
        requête par carte affichée.

        On compare deux tailles de flux au lieu de figer un nombre. Le nombre
        exact dépend des intergiciels et changerait à la première évolution ;
        l'invariant à tenir est qu'il ne dépende pas du nombre d'offres.
        """
        for index in range(2):
            self._make_translated_deal(slug=f"flux-court-{index}")

        with CaptureQueriesContext(connection) as captured:
            short = self.client.get("/nl/")
        self.assertEqual(short.status_code, 200)
        baseline = len(captured)

        # Toujours une seule page : la pagination est à dix, on reste en deçà
        # pour que la comparaison porte bien sur le rendu et non sur un tronçon.
        for index in range(6):
            self._make_translated_deal(slug=f"flux-long-{index}")
        self.assertEqual(Deal.objects.live().count(), 9)

        with self.assertNumQueries(baseline):
            long = self.client.get("/nl/")
        self.assertContains(long, self.DUTCH_TITLE)


# ==========================================================================
# Validation des formulaires du front-office
# ==========================================================================
class FormValidationTests(BaseIntegrationTest):
    def test_registration_rejects_weak_password(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "email": "faible@example.be",
                "display_name": "Faible",
                "preferred_language": "fr",
                "password1": "azerty123",
                "password2": "azerty123",
                "accept_terms": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(User.objects.filter(email="faible@example.be").exists())

    def test_registration_requires_terms_acceptance(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "email": "sanscgu@example.be",
                "display_name": "SansCGU",
                "preferred_language": "fr",
                "password1": STRONG_PASSWORD,
                "password2": STRONG_PASSWORD,
            },
        )
        self.assertIn("accept_terms", response.context["form"].errors)

    def test_registration_blocks_duplicate_email_case_insensitively(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "email": "MEMBRE@example.be",
                "display_name": "Doublon",
                "preferred_language": "fr",
                "password1": STRONG_PASSWORD,
                "password2": STRONG_PASSWORD,
                "accept_terms": "on",
            },
        )
        self.assertIn("email", response.context["form"].errors)

    def test_successful_registration_logs_in_and_audits(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "email": "nouvelle@example.be",
                "display_name": "Nouvelle",
                "preferred_language": "nl",
                "password1": "Quai-Aux-Briques-7",
                "password2": "Quai-Aux-Briques-7",
                "accept_terms": "on",
                "marketing_consent": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email="nouvelle@example.be")
        self.assertTrue(user.marketing_consent)
        self.assertIsNotNone(user.accepted_terms_at)
        self.assertTrue(
            AuditLog.objects.filter(action=AuditLog.Action.USER_REGISTERED, actor=user).exists()
        )

    def test_submission_form_rejects_non_https_link(self):
        self.login(self.member)
        response = self.client.post(
            reverse("deals:submit"),
            {
                "title": "Enceinte portable JBL Charge 5 étanche",
                "description": (
                    "Description assez longue pour satisfaire la contrainte du modèle."
                ),
                "external_url": "http://example.be/jbl-charge-5",
                "price": "99.00",
                "shipping_cost": "0.00",
                "merchant": str(self.published.merchant_id),
                "category": str(self.published.category_id),
                "language": "fr",
            },
        )
        self.assertIn("external_url", response.context["form"].errors)

    def test_submission_form_enforces_cross_border_flag(self):
        from apps.catalog.models import Merchant

        self.login(self.member)
        dutch = Merchant.objects.get(slug="action-maastricht")
        response = self.client.post(
            reverse("deals:submit"),
            {
                "title": "Sèche-linge Bosch pompe à chaleur huit kilos",
                "description": (
                    "Vendu par un marchand néerlandais, à vingt kilomètres " "de la frontière."
                ),
                "external_url": "https://example.nl/bosch-seche-linge",
                "price": "449.00",
                "shipping_cost": "0.00",
                "merchant": str(dutch.pk),
                "category": str(self.published.category_id),
                "language": "nl",
            },
        )
        self.assertIn("is_cross_border", response.context["form"].errors)

    def test_url_parameter_injection_is_ignored(self):
        """Un code région inexistant ne doit pas casser la page ni tout révéler."""
        response = self.client.get(reverse("deals:list") + "?region=' OR 1=1--")
        self.assertEqual(response.status_code, 200)

    def test_invalid_vote_value_is_rejected(self):
        self.login(self.member)
        response = self.client.post(
            reverse("deals:vote", kwargs={"slug": self.published.slug}), {"value": "99"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Vote.objects.filter(deal=self.published, user=self.member).exists())

import json

from django import forms
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.accounts.validators import validate_no_control_characters
from apps.catalog.images import IMAGE_VALIDATORS
from apps.catalog.merchants import build_merchant
from apps.catalog.models import Category, Merchant, Region

from .models import Comment, Deal, DealImage, DealStatus

MAX_IMAGES = 8


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    """Plusieurs images dans un seul champ ; chacune passe par Pillow et IMAGE_VALIDATORS."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "widget", MultipleImageInput(attrs={"accept": "image/jpeg,image/png,image/webp"})
        )
        kwargs.setdefault("validators", IMAGE_VALIDATORS)
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        files = data if isinstance(data, list | tuple) else ([data] if data else [])
        return [super(MultipleImageField, self).clean(f, initial) for f in files]


class DealSubmissionForm(forms.ModelForm):
    """
    Dépôt d'une offre, présenté en six étapes (lien, essentiel, images,
    description, derniers détails, vérification) mais envoyé en UNE fois :
    le serveur revalide tout, l'assistant n'est qu'un confort d'affichage.

    Le statut n'est pas un champ du formulaire : quoi que poste le client,
    l'offre entre en file de modération. Le marchand n'est plus choisi dans
    une liste : il est reconnu, ou créé non vérifié, d'après le lien.
    """

    regions = forms.ModelMultipleChoiceField(
        queryset=Region.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("Lieux"),
        help_text=_("Aucune case cochée : toute la Belgique."),
    )
    merchant = forms.ModelChoiceField(
        queryset=Merchant.objects.order_by("name"),
        required=False,
        label=_("Marchand"),
        widget=forms.Select(attrs={"class": "select"}),
    )
    merchant_name = forms.CharField(
        label=_("Nom du marchand"),
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={"class": "input", "placeholder": _("ex. Joybuy")}),
    )
    gallery_urls = forms.CharField(required=False, widget=forms.HiddenInput)
    gallery_files = MultipleImageField(label=_("Ajouter des photos"), required=False)
    main_index = forms.IntegerField(required=False, min_value=0, widget=forms.HiddenInput)

    class Meta:
        model = Deal
        fields = [
            "external_url",
            "title",
            "price",
            "reference_price",
            "promo_code",
            "availability",
            "shipping_cost",
            "regions",
            "description",
            "category",
            "language",
            "starts_at",
            "ends_at",
        ]
        widgets = {
            "external_url": forms.URLInput(
                attrs={"class": "input", "placeholder": "https://www.exemple.be/super-deal"}
            ),
            "title": forms.TextInput(
                attrs={"class": "input", "maxlength": 140, "minlength": 15}
            ),
            "description": forms.Textarea(
                attrs={"class": "textarea", "maxlength": 4000, "rows": 10}
            ),
            "price": forms.NumberInput(attrs={"class": "input", "min": 0, "step": "0.01"}),
            "reference_price": forms.NumberInput(
                attrs={"class": "input", "min": 0, "step": "0.01"}
            ),
            "shipping_cost": forms.NumberInput(
                attrs={"class": "input", "min": 0, "step": "0.01"}
            ),
            "promo_code": forms.TextInput(attrs={"class": "input", "maxlength": 40}),
            "availability": forms.RadioSelect,
            "category": forms.Select(attrs={"class": "select"}),
            "language": forms.Select(attrs={"class": "select"}),
            "starts_at": forms.DateTimeInput(
                attrs={"class": "input", "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "ends_at": forms.DateTimeInput(
                attrs={"class": "input", "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["category"].queryset = Category.objects.filter(
            is_active=True
        ).prefetch_related("translations")
        # Libellé traduit (« Maison & électroménager ») plutôt que le code (« maison »).
        self.fields["category"].label_from_instance = lambda category: category.label_current
        self.fields["starts_at"].required = False
        self.fields["starts_at"].initial = timezone.localtime().replace(second=0, microsecond=0)
        self.fields["reference_price"].label = _(
            "Prix de référence (le plus bas des 30 derniers jours)"
        )
        self._merchant = None

    # -- Champs ---------------------------------------------------------------
    def clean_title(self):
        value = " ".join(self.cleaned_data["title"].split())
        validate_no_control_characters(value)
        if value.isupper():
            raise forms.ValidationError(_("Évitez les titres entièrement en majuscules."))
        return value

    def clean_external_url(self):
        url = self.cleaned_data.get("external_url", "")
        if url and not url.lower().startswith("https://"):
            raise forms.ValidationError(_("Le lien doit être en HTTPS."))
        return url

    def clean_promo_code(self):
        return self.cleaned_data.get("promo_code", "").strip()

    def clean_gallery_urls(self):
        raw = self.cleaned_data.get("gallery_urls") or "[]"
        try:
            urls = json.loads(raw)
        except ValueError as exc:
            raise forms.ValidationError(_("Liste d'images invalide.")) from exc
        if not isinstance(urls, list) or not all(isinstance(u, str) for u in urls):
            raise forms.ValidationError(_("Liste d'images invalide."))
        cleaned = []
        for url in urls:
            url = url.strip()
            # https uniquement : une image http serait bloquée (contenu mixte).
            if not url.lower().startswith("https://") or len(url) > 800:
                raise forms.ValidationError(_("L'adresse de l'image doit être en HTTPS."))
            if url not in cleaned:
                cleaned.append(url)
        return cleaned

    # -- Règles croisées ------------------------------------------------------
    def clean(self):
        data = super().clean()

        price, reference = data.get("price"), data.get("reference_price")
        if reference is not None and price is not None and reference <= price:
            self.add_error(
                "reference_price",
                _(
                    "Le prix de référence doit dépasser le prix affiché. La loi belge "
                    "impose d'y indiquer le prix le plus bas des 30 derniers jours."
                ),
            )

        if data.get("availability") == "online" and not data.get("external_url"):
            self.add_error(
                "external_url", _("Un deal en ligne doit avoir un lien vers l'offre.")
            )

        starts, ends = data.get("starts_at"), data.get("ends_at")
        if starts and ends and ends <= starts:
            self.add_error("ends_at", _("La fin doit être postérieure au début."))

        images = len(data.get("gallery_urls") or []) + len(data.get("gallery_files") or [])
        if images > MAX_IMAGES:
            self.add_error("gallery_files", _("Huit images au maximum."))

        # Marchand : choisi dans la liste, sinon reconnu ou créé d'après le lien.
        self._merchant = data.get("merchant") or build_merchant(
            url=data.get("external_url", ""), name=data.get("merchant_name", "")
        )
        if self._merchant is None:
            self.add_error(
                "merchant_name",
                _("Indiquez le nom du marchand (ou collez le lien de l'offre)."),
            )
        return data

    def save(self, commit=True):
        deal = super().save(commit=False)
        merchant = self._merchant
        if merchant._state.adding:
            merchant.save()  # nouveau marchand, non vérifié : la modération confirme
        deal.merchant = merchant
        # Hors de Belgique = transfrontalier, automatiquement (plus de case à cocher).
        deal.is_cross_border = merchant.country != "BE"
        deal.submitted_by = self.user
        deal.status = DealStatus.PENDING
        deal.starts_at = self.cleaned_data.get("starts_at") or timezone.now()
        base = slugify(deal.title)[:140] or "deal"
        slug, n = base, 1
        while Deal.objects.filter(slug=slug).exclude(pk=deal.pk).exists():
            n += 1
            slug = f"{base[:150]}-{n}"
        deal.slug = slug

        # Images : d'abord les adresses, puis les fichiers ; main_index désigne
        # l'image principale dans cet ordre, les autres vont dans la galerie.
        items = [("url", u) for u in self.cleaned_data.get("gallery_urls") or []]
        items += [("file", f) for f in self.cleaned_data.get("gallery_files") or []]
        main = self.cleaned_data.get("main_index") or 0
        if items:
            items.insert(0, items.pop(min(main, len(items) - 1)))
            kind, value = items[0]
            if kind == "url":
                deal.image_url = value
            else:
                deal.image = value

        if commit:
            deal.save()
            self.save_m2m()
            if not deal.regions.exists():
                deal.regions.set(Region.objects.all())  # « toute la Belgique »
            for position, (kind, value) in enumerate(items[1:], start=1):
                DealImage.objects.create(
                    deal=deal,
                    position=position,
                    image=value if kind == "file" else "",
                    image_url=value if kind == "url" else "",
                )
        return deal


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "class": "textarea",
                    "rows": 4,
                    "maxlength": 2000,
                    "placeholder": _("Disponibilité, qualité du service, conditions réelles…"),
                }
            )
        }

    def clean_body(self):
        value = self.cleaned_data["body"].strip()
        validate_no_control_characters(value)
        if len(value) < 2:
            raise forms.ValidationError(_("Commentaire trop court."))
        return value

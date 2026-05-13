from django import forms
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.accounts.validators import validate_no_control_characters
from apps.catalog.models import Category, Merchant, Region

from .models import Comment, Deal, DealStatus


class DealSubmissionForm(forms.ModelForm):
    """
    Dépôt d'une offre. Le statut n'est pas un champ du formulaire : quoi que
    poste le client, l'offre entre en file de modération.
    """

    regions = forms.ModelMultipleChoiceField(
        queryset=Region.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("Régions concernées"),
    )

    class Meta:
        model = Deal
        fields = [
            "title",
            "description",
            "external_url",
            "price",
            "reference_price",
            "shipping_cost",
            "merchant",
            "category",
            "regions",
            "language",
            "is_cross_border",
            "ends_at",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "input", "maxlength": 140, "minlength": 15}
            ),
            "description": forms.Textarea(attrs={"class": "textarea", "maxlength": 4000}),
            "external_url": forms.URLInput(attrs={"class": "input", "placeholder": "https://"}),
            "price": forms.NumberInput(attrs={"class": "input", "min": 0, "step": "0.01"}),
            "reference_price": forms.NumberInput(
                attrs={"class": "input", "min": 0, "step": "0.01"}
            ),
            "shipping_cost": forms.NumberInput(
                attrs={"class": "input", "min": 0, "step": "0.01"}
            ),
            "merchant": forms.Select(attrs={"class": "select"}),
            "category": forms.Select(attrs={"class": "select"}),
            "language": forms.Select(attrs={"class": "select"}),
            "ends_at": forms.DateTimeInput(attrs={"class": "input", "type": "datetime-local"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["category"].queryset = Category.objects.filter(is_active=True)
        self.fields["merchant"].queryset = Merchant.objects.order_by("name")

    def clean_title(self):
        value = " ".join(self.cleaned_data["title"].split())
        validate_no_control_characters(value)
        if value.isupper():
            raise forms.ValidationError(_("Évitez les titres entièrement en majuscules."))
        return value

    def clean_external_url(self):
        url = self.cleaned_data["external_url"]
        if not url.lower().startswith("https://"):
            raise forms.ValidationError(_("Le lien doit être en HTTPS."))
        return url

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
        merchant = data.get("merchant")
        if merchant and merchant.country != "BE" and not data.get("is_cross_border"):
            self.add_error(
                "is_cross_border",
                _("Un marchand hors Belgique impose de cocher « offre transfrontalière »."),
            )
        return data

    def save(self, commit=True):
        deal = super().save(commit=False)
        deal.submitted_by = self.user
        deal.status = DealStatus.PENDING
        base = slugify(deal.title)[:140] or "deal"
        slug, n = base, 1
        while Deal.objects.filter(slug=slug).exclude(pk=deal.pk).exists():
            n += 1
            slug = f"{base[:150]}-{n}"
        deal.slug = slug
        if commit:
            deal.save()
            self.save_m2m()
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

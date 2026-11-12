from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Merchant, MerchantAccount


class MerchantClaimForm(forms.ModelForm):
    """Demande de gestion d'une fiche. Le statut n'est pas un champ : il est imposé."""

    class Meta:
        model = MerchantAccount
        fields = ["merchant", "message"]
        labels = {
            "merchant": _("Votre commerce"),
            "message": _("Votre lien avec ce commerce"),
        }
        help_texts = {
            "message": _("Par exemple : « Je suis le gérant, numéro de TVA BE0… »."),
        }
        widgets = {
            "merchant": forms.Select(attrs={"class": "select"}),
            "message": forms.TextInput(attrs={"class": "input", "maxlength": 300}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["merchant"].queryset = Merchant.objects.order_by("name")
        self.fields["merchant"].empty_label = _("Choisissez un commerce")

    def clean_merchant(self):
        merchant = self.cleaned_data["merchant"]
        if MerchantAccount.objects.filter(user=self.user, merchant=merchant).exists():
            raise forms.ValidationError(_("Vous avez déjà fait une demande pour ce commerce."))
        return merchant

    def clean_message(self):
        return " ".join(self.cleaned_data["message"].split())


class MerchantProfileForm(forms.ModelForm):
    """
    Fiche du commerce, modifiable par son commerçant. Le nom, le numéro de TVA
    et les badges « vérifié » et « commerçant local » restent à la modération :
    ils ne figurent pas dans les champs.
    """

    class Meta:
        model = Merchant
        fields = ["website", "address", "city", "brand_color", "logo"]
        labels = {
            "website": _("Site web"),
            "address": _("Adresse"),
            "city": _("Ville"),
            "brand_color": _("Couleur de la vignette"),
            "logo": _("Logo"),
        }
        widgets = {
            "website": forms.URLInput(attrs={"class": "input", "placeholder": "https://…"}),
            "address": forms.TextInput(attrs={"class": "input", "maxlength": 200}),
            "city": forms.TextInput(attrs={"class": "input", "maxlength": 80}),
            "brand_color": forms.TextInput(attrs={"class": "input", "type": "color"}),
            "logo": forms.ClearableFileInput(
                attrs={"accept": "image/jpeg,image/png,image/webp"}
            ),
        }

    def clean_website(self):
        website = self.cleaned_data["website"]
        if website and not website.startswith("https://"):
            raise forms.ValidationError(_("L'adresse du site doit commencer par https://"))
        return website

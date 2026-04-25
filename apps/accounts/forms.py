"""
Formulaires du front-office.

Toute validation présente ici existe aussi côté API (sérialiseurs) : le
navigateur n'est qu'une commodité, la règle vit sur le serveur.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import gettext_lazy as _

from .models import User
from .validators import validate_no_control_characters


class RegistrationForm(UserCreationForm):
    accept_terms = forms.BooleanField(
        label=_("J'accepte les conditions d'utilisation et la politique de confidentialité"),
        required=True,
        error_messages={"required": _("L'acceptation des conditions est obligatoire.")},
    )
    marketing_consent = forms.BooleanField(
        label=_("Je souhaite recevoir la sélection hebdomadaire des meilleurs deals"),
        required=False,
        help_text=_("Facultatif, révocable à tout moment. Consentement distinct des CGU."),
    )

    class Meta:
        model = User
        fields = ["email", "display_name", "preferred_language", "home_region"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "input" if not isinstance(field.widget, forms.CheckboxInput) else ""
            if isinstance(field.widget, forms.Select):
                css = "select"
            if css:
                field.widget.attrs.setdefault("class", css)
        # Le navigateur applique la même longueur minimale que le serveur.
        self.fields["password1"].widget.attrs.update(
            {"class": "input", "minlength": 12, "autocomplete": "new-password"}
        )
        self.fields["password2"].widget.attrs.update(
            {"class": "input", "minlength": 12, "autocomplete": "new-password"}
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        # iexact : « Jean@x.be » et « jean@x.be » sont le même compte.
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("Un compte existe déjà avec cette adresse."))
        return email

    def clean_display_name(self):
        name = self.cleaned_data["display_name"].strip()
        validate_no_control_characters(name)
        if User.objects.filter(display_name__iexact=name).exists():
            raise forms.ValidationError(_("Ce pseudonyme est déjà pris."))
        return name

    def save(self, commit=True):
        user = super().save(commit=False)
        user.marketing_consent = self.cleaned_data.get("marketing_consent", False)
        if self.cleaned_data.get("accept_terms"):
            from django.utils import timezone

            user.accepted_terms_at = timezone.now()
        if commit:
            user.save()
        return user


class EmailAuthenticationForm(AuthenticationForm):
    """
    Connexion par e-mail. Le message d'échec est volontairement identique que
    l'adresse existe ou non : distinguer les deux cas transforme le formulaire
    en oracle d'existence de compte.
    """

    username = forms.EmailField(
        label=_("Adresse e-mail"),
        widget=forms.EmailInput(attrs={"class": "input", "autocomplete": "email"}),
    )
    password = forms.CharField(
        label=_("Mot de passe"),
        widget=forms.PasswordInput(
            attrs={"class": "input", "autocomplete": "current-password"}
        ),
    )
    error_messages = {
        "invalid_login": _("Adresse e-mail ou mot de passe incorrect."),
        "inactive": _("Adresse e-mail ou mot de passe incorrect."),
    }


class AlertForm(forms.Form):
    keyword = forms.CharField(
        label=_("Mot-clé"),
        max_length=80,
        widget=forms.TextInput(
            attrs={"class": "input", "placeholder": _("Ex. : machine à café")}
        ),
    )
    region = forms.ChoiceField(
        label=_("Région"), required=False, widget=forms.Select(attrs={"class": "select"})
    )
    max_price = forms.DecimalField(
        label=_("Prix maximum"),
        required=False,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "input", "min": 0, "step": "0.01"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.catalog.models import Region

        self.fields["region"].choices = [("", _("Toute la Belgique"))] + [
            (r.code, r.name_fr) for r in Region.objects.all()
        ]

    def clean_keyword(self):
        value = self.cleaned_data["keyword"].strip()
        validate_no_control_characters(value)
        if len(value) < 2:
            raise forms.ValidationError(_("Mot-clé trop court."))
        return value

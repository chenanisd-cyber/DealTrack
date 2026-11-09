"""Formulaire de la page « Aide et contact »."""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.accounts.validators import validate_no_control_characters

from .models import ContactMessage

MESSAGE_MIN_LENGTH = 20


class ContactForm(forms.ModelForm):
    # Champ piège invisible pour un humain : un robot qui remplit tout le
    # formulaire le complète, et le message est alors refusé.
    website = forms.CharField(
        required=False,
        label=_("Ne pas remplir ce champ"),
        widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}),
    )

    class Meta:
        model = ContactMessage
        fields = ("name", "email", "subject", "message")
        labels = {
            "name": _("Votre nom"),
            "email": _("Votre adresse e-mail"),
            "subject": _("Sujet"),
            "message": _("Votre message"),
        }
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "input", "maxlength": 80, "autocomplete": "name"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "input", "maxlength": 254, "autocomplete": "email"}
            ),
            "subject": forms.Select(attrs={"class": "select"}),
            "message": forms.Textarea(
                attrs={
                    "class": "textarea",
                    "rows": 6,
                    "minlength": MESSAGE_MIN_LENGTH,
                    "maxlength": 2000,
                }
            ),
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        validate_no_control_characters(name)
        return name

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        validate_no_control_characters(message)
        if len(message) < MESSAGE_MIN_LENGTH:
            raise ValidationError(
                _("Décrivez votre demande en %(n)d caractères au moins.")
                % {"n": MESSAGE_MIN_LENGTH}
            )
        return message

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise ValidationError(_("Message refusé."))
        return ""

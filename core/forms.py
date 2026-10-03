"""Forms owned by the core app (site settings + small shared forms)."""

from __future__ import annotations

from django import forms

from core.models import SiteSetting
from core.validators import validate_phone, validate_pincode


class SiteSettingForm(forms.ModelForm):
    class Meta:
        model = SiteSetting
        fields = [
            "institute_name",
            "institute_code",
            "address",
            "city",
            "state",
            "pincode",
            "phone",
            "email",
            "website",
            "logo",
            "academic_year",
            "current_semester",
            "pass_percentage",
            "attendance_shortage_percentage",
            "currency_symbol",
            "receipt_prefix",
            "id_card_validity_months",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "logo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "current_semester": forms.NumberInput(attrs={"min": 1, "max": 12}),
            "pass_percentage": forms.NumberInput(attrs={"step": "0.01", "min": 0, "max": 100}),
            "attendance_shortage_percentage": forms.NumberInput(
                attrs={"step": "0.01", "min": 0, "max": 100}
            ),
            "id_card_validity_months": forms.NumberInput(attrs={"min": 1, "max": 120}),
        }

    def clean_pincode(self):
        pincode = self.cleaned_data.get("pincode")
        validate_pincode(pincode)
        return pincode

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        validate_phone(phone)
        return phone

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if logo:
            from core.validators import validate_image

            validate_image(logo)
        return logo


class BootstrapFormMixin:
    """Adds Bootstrap 5 classes to every widget of a form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            css = widget.attrs.get("class", "")
            if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect)):
                widget.attrs["class"] = f"{css} form-check-input".strip()
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs["class"] = f"{css} form-select".strip()
            elif isinstance(widget, forms.FileInput):
                widget.attrs["class"] = f"{css} form-control".strip()
            else:
                widget.attrs["class"] = f"{css} form-control".strip()
            if field.required:
                widget.attrs.setdefault("required", "required")
            widget.attrs.setdefault("autocomplete", "off")

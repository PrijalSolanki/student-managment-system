from __future__ import annotations

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    UserCreationForm,
)

from accounts.models import User
from academics.models import Department
from core.forms import BootstrapFormMixin
from core.validators import USERNAME_RE, validate_image, validate_phone


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    remember_me = forms.BooleanField(
        required=False,
        label="Keep me signed in",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def clean_username(self):
        return self.cleaned_data.get("username", "").strip()


class RegistrationForm(BootstrapFormMixin, UserCreationForm):
    """Self-service staff registration (Admin approval required for access)."""

    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(
        choices=User.Role.choices,
        initial=User.Role.STAFF,
        help_text="New accounts are created as Staff until an administrator changes the role.",
    )
    phone = forms.CharField(max_length=20, required=False, validators=[validate_phone])

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "role", "phone", "password1", "password2"]

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")
        return email

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not USERNAME_RE.match(username):
            raise forms.ValidationError(
                "Usernames may contain letters, digits and . _ - @ (3-150 characters)."
            )
        return username


class UserForm(BootstrapFormMixin, forms.ModelForm):
    """Create / edit an internal user (administrators only)."""

    password1 = forms.CharField(
        label="Password", required=False, widget=forms.PasswordInput(render_value=False),
        help_text="Leave blank to keep the current password.",
    )
    password2 = forms.CharField(
        label="Confirm password", required=False, widget=forms.PasswordInput(render_value=False)
    )

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "phone",
            "designation",
            "department",
            "date_of_birth",
            "address",
            "avatar",
            "is_active",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "avatar": forms.ClearableFileInput(),
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        qs = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if email and qs.exists():
            raise forms.ValidationError("Another account already uses this email address.")
        return email

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar:
            validate_image(avatar)
        return avatar

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 or password2:
            if password1 != password2:
                self.add_error("password2", "The two passwords do not match.")
            else:
                from django.contrib.auth.password_validation import validate_password

                try:
                    validate_password(password1, self.instance)
                except forms.ValidationError as exc:
                    self.add_error("password1", exc)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password1")
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


class UserProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "designation",
            "address",
            "date_of_birth",
            "avatar",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "avatar": forms.ClearableFileInput(),
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        qs = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if email and qs.exists():
            raise forms.ValidationError("Another account already uses this email address.")
        return email

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar:
            validate_image(avatar)
        return avatar


class StyledPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    pass


class StaffFilterForm(forms.Form):
    """Lightweight filter helper rendered on the user list page."""

    role = forms.ChoiceField(
        required=False,
        choices=[("", "All roles"), ("ADMIN", "Administrator"), ("STAFF", "Staff")],
    )
    department = forms.ModelChoiceField(
        required=False, queryset=Department.objects.all(), empty_label="All departments"
    )

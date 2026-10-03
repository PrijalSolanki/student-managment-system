from django import forms

from academics.models import Batch, Course, Department
from core.forms import BootstrapFormMixin
from notifications.models import Notification, StudentAnnouncement
from students.models import Student


class NotificationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Notification
        fields = [
            "title",
            "body",
            "priority",
            "audience",
            "department",
            "course",
            "batch",
            "is_pinned",
            "is_active",
            "expires_at",
            "action_url",
            "attachment",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Short headline"}),
            "body": forms.Textarea(attrs={"rows": 5, "placeholder": "Write the message shown to recipients"}),
            "expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "action_url": forms.TextInput(attrs={"placeholder": "/attendance/mark/  (optional)"}),
            "attachment": forms.ClearableFileInput(attrs={"accept": ".pdf,.doc,.docx,.png,.jpg,.jpeg"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.order_by("name")
        self.fields["department"].empty_label = "Not department specific"
        self.fields["course"].queryset = Course.objects.order_by("name")
        self.fields["course"].empty_label = "Not course specific"
        self.fields["batch"].queryset = Batch.objects.order_by("name")
        self.fields["batch"].empty_label = "Not batch specific"
        self.fields["expires_at"].required = False

    def clean(self):
        cleaned = super().clean()
        audience = cleaned.get("audience")
        mapping = {
            Notification.Audience.DEPARTMENT: "department",
            Notification.Audience.COURSE: "course",
            Notification.Audience.BATCH: "batch",
        }
        required_field = mapping.get(audience)
        if required_field and not cleaned.get(required_field):
            self.add_error(required_field, f"Select a target for the '{audience.title()}' audience.")
        return cleaned


class StudentAnnouncementForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = StudentAnnouncement
        fields = ["student", "title", "message"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Notice title"}),
            "message": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = (
            Student.objects.select_related("course", "department").order_by("student_id")
        )
        self.fields["student"].empty_label = "Select student"


class NotificationFilterForm(BootstrapFormMixin, forms.Form):
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Search title or body"}))
    priority = forms.ChoiceField(required=False, choices=[("", "All priorities")] + list(Notification.Priority.choices))
    audience = forms.ChoiceField(required=False, choices=[("", "All audiences")] + list(Notification.Audience.choices))
    is_active = forms.ChoiceField(required=False, choices=[("", "All"), ("true", "Active"), ("false", "Inactive")])
    is_pinned = forms.BooleanField(required=False)
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))


__all__ = ["NotificationForm", "StudentAnnouncementForm", "NotificationFilterForm"]
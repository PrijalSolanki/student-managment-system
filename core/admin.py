from django.contrib import admin

from core.models import AuditLog, SiteSetting


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ("institute_name", "institute_code", "academic_year", "current_semester")
    search_fields = ("institute_name",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "username_snapshot", "action", "module", "record_repr", "ip_address")
    list_filter = ("action", "module")
    search_fields = ("record_repr", "description", "username_snapshot", "record_id")
    readonly_fields = [field.name for field in AuditLog._meta.fields]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

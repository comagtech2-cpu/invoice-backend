from django.contrib import admin
from django.utils.html import format_html
from .models import Business


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone_number', 'logo_preview')
    readonly_fields = ('logo_preview',)

    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="max-height: 60px;"/>', obj.logo.url)
        return '-'
    logo_preview.short_description = 'Logo Preview'

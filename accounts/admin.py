from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, StaffProfile, PatientProfile, ANCVisit, SMSLog


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'phone_number', 'is_active')
    list_filter = ('role',)
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('role', 'phone_number', 'must_change_password')}),
    )


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'pregnancy_period', 'assigned_doctor', 'email_alerts_active', 'registered_at')


@admin.register(ANCVisit)
class ANCVisitAdmin(admin.ModelAdmin):
    list_display = ('patient', 'visit_number', 'scheduled_date', 'status', 'is_completed')
    list_filter = ('status',)


admin.site.register(StaffProfile)
admin.site.register(SMSLog)
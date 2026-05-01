from django.contrib import admin
from .models import Appointment, PractitionerAssignment

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'date', 'hour', 'status')
    list_filter = ('status', 'date')

admin.site.register(PractitionerAssignment)
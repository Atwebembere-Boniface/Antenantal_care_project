from django.db import models
from accounts.models import User, PatientProfile
from datetime import date


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='doctor_appointments',
                               limit_choices_to={'role': 'DOCTOR'})
    date = models.DateField()
    hour = models.IntegerField(help_text="Hour slot (9-17 = 9am to 5pm)")
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    notes = models.TextField(blank=True, help_text="Doctor's notes on appointment")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'hour']

    def __str__(self):
        return f"{self.patient.user.get_full_name()} with Dr. {self.doctor.last_name} on {self.date} at {self.hour}:00"

    @property
    def hour_display(self):
        h = self.hour
        suffix = 'AM' if h < 12 else 'PM'
        display_h = h if h <= 12 else h - 12
        return f"{display_h}:00 {suffix}"


class PractitionerAssignment(models.Model):
    patient = models.OneToOneField(PatientProfile, on_delete=models.CASCADE, related_name='current_assignment')
    practitioner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_mothers')
    date_assigned = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient.user.get_full_name()} -> Dr. {self.practitioner.last_name}"
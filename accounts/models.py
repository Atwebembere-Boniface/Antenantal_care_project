from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import date, timedelta
from django.conf import settings

class User(AbstractUser):
    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('DOCTOR', 'Doctor'),
        ('NURSE', 'Nurse'),
        ('PATIENT', 'Patient'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    must_change_password = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"


class StaffProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    employee_id = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=100, default='Antenatal Care')

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.department}"


class PatientProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    address = models.TextField(blank=True)
    pregnancy_period = models.IntegerField(default=0, help_text="Weeks pregnant at registration")
    age = models.IntegerField(null=True, blank=True)
    assigned_doctor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='doctor_patients'
    )
    ward_number = models.CharField(max_length=20, blank=True, default='ANC-01')
    email_alerts_active = models.BooleanField(default=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    @property
    def edd(self):
        """Estimated Delivery Date: 40 weeks from LMP based on pregnancy period."""
        weeks_remaining = 40 - self.pregnancy_period
        return date.today() + timedelta(weeks=weeks_remaining)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class ANCVisit(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ATTENDED', 'Attended'),
        ('MISSED', 'Missed'),
        ('APPROVED', 'Approved'),
    ]
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='anc_visits')
    visit_number = models.IntegerField()
    scheduled_date = models.DateField()
    is_completed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    clinical_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['visit_number']

    def __str__(self):
        return f"Visit {self.visit_number} - {self.patient.user.get_full_name() or self.patient.user.username} on {self.scheduled_date}"


class SMSLog(models.Model):
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='sms_logs', null=True, blank=True)
    phone_number = models.CharField(max_length=20)
    message = models.TextField()
    status = models.CharField(max_length=20)
    response_body = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.phone_number} - {self.status} at {self.sent_at}"


def generate_anc_visits(patient_profile):
    today = date.today()
    intervals = [4, 8, 12, 16, 20, 24, 28]
    for i, weeks in enumerate(intervals, start=2):
        ANCVisit.objects.get_or_create(
            patient=patient_profile,
            visit_number=i,
            defaults={'scheduled_date': today + timedelta(weeks=weeks)}
        )


class Message(models.Model):
    # FIXED: Added app-specific prefixes to related_name to prevent clashing with 'messaging' app
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        related_name='accounts_sent_messages', 
        on_delete=models.CASCADE
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        related_name='accounts_received_messages', 
        on_delete=models.CASCADE
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"From {self.sender} to {self.recipient} at {self.timestamp}"
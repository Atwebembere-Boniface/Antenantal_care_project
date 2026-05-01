from django.db import models
from accounts.models import PatientProfile, ANCVisit


class ReminderLog(models.Model):
    CHANNEL_CHOICES = [('SMS', 'SMS'), ('EMAIL', 'Email')]
    STATUS_CHOICES = [('SENT', 'Sent'), ('FAILED', 'Failed'), ('PENDING', 'Pending')]

    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='reminder_logs')
    visit = models.ForeignKey(ANCVisit, on_delete=models.SET_NULL, null=True, blank=True)
    date_sent = models.DateTimeField(auto_now_add=True)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    message_content = models.TextField()

    class Meta:
        ordering = ['-date_sent']

    def __str__(self):
        return f"Reminder for {self.patient.user.username} via {self.channel} - {self.status}"
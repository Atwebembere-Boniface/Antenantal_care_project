from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import date, timedelta

from .models import ReminderLog
from accounts.models import ANCVisit, PatientProfile
from accounts.utils import send_egosms, format_ugandan_phone


def send_upcoming_reminders():
    """Send SMS + Email for visits scheduled tomorrow."""
    tomorrow = date.today() + timedelta(days=1)
    upcoming = ANCVisit.objects.filter(scheduled_date=tomorrow, is_completed=False).select_related('patient__user')
    sent_count = 0

    for visit in upcoming:
        already_sent = ReminderLog.objects.filter(visit=visit, status='SENT').exists()
        if already_sent:
            continue

        patient = visit.patient
        name = patient.user.first_name or patient.user.username
        phone = patient.user.phone_number
        email = patient.user.email

        sms_msg = (
            f"KRRH Reminder: Dear {name}, your ANC Visit {visit.visit_number} "
            f"is tomorrow {visit.scheduled_date.strftime('%d %b %Y')}. Please attend. KRRH"
        )
        email_msg = (
            f"Dear {name},\n\n"
            f"This is a reminder that your ANC Visit {visit.visit_number} "
            f"is scheduled for tomorrow, {visit.scheduled_date.strftime('%A, %d %B %Y')}.\n\n"
            f"Please ensure you attend. Missing visits can be dangerous.\n\n"
            f"KRRH Antenatal Unit"
        )

        # SMS
        if phone:
            success, resp = send_egosms(phone, sms_msg)
            ReminderLog.objects.create(
                patient=patient, visit=visit, channel='SMS',
                status='SENT' if success else 'FAILED', message_content=sms_msg
            )

        # Email
        if email:
            try:
                send_mail(
                    f"ANC Reminder - Visit {visit.visit_number} Tomorrow",
                    email_msg, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True
                )
                ReminderLog.objects.create(
                    patient=patient, visit=visit, channel='EMAIL',
                    status='SENT', message_content=email_msg
                )
                sent_count += 1
            except Exception:
                ReminderLog.objects.create(
                    patient=patient, visit=visit, channel='EMAIL',
                    status='FAILED', message_content=email_msg
                )

    return sent_count


def send_bulk_welcome_sms():
    """Send welcome SMS to all patients who haven't received one yet."""
    patients = PatientProfile.objects.all().select_related('user')
    sent_count = 0

    for patient in patients:
        already = ReminderLog.objects.filter(
            patient=patient, channel='SMS',
            message_content__icontains='Welcome', status='SENT'
        ).exists()
        if not already:
            phone = patient.user.phone_number
            name = patient.user.first_name or patient.user.username
            edd = patient.edd.strftime('%d %b %Y')
            msg = (
                f"Welcome to KRRH ANC, {name}! Registration successful. "
                f"EDD: {edd}. Please attend all 8 ANC contacts. KRRH"
            )
            if phone:
                success, resp = send_egosms(phone, msg)
                ReminderLog.objects.create(
                    patient=patient, channel='SMS',
                    status='SENT' if success else 'FAILED', message_content=msg
                )
                if success:
                    sent_count += 1
    return sent_count
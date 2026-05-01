import re
import time
import threading
import requests
import json
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

def format_ugandan_phone(phone):
    """Standardizes to 2567XXXXXXXX for EgoSMS."""
    if not phone:
        return None
    clean = re.sub(r'\D', '', str(phone))
    if clean.startswith('0') and len(clean) == 10:
        return '256' + clean[1:]
    elif len(clean) == 9 and clean.startswith('7'):
        return '256' + clean
    elif clean.startswith('256') and len(clean) == 12:
        return clean
    return clean

def send_egosms(phone, message):
    """
    Send SMS via EgoSMS API (egosms.co).
    Updated to use 'sendsms' method and correct parameter mapping.
    """
    formatted = format_ugandan_phone(phone)
    if not formatted:
        return False, "Invalid phone number"

    # These keys are specific to the 'sendsms' method
    params = {
        'username': settings.EGOSMS_USERNAME,
        'password': settings.EGOSMS_PASSWORD,
        'method': 'sendsms',     # Keep this as 'sendsms'
        'number': formatted,     # Change 'numbers' -> 'number'
        'message': message,      # Change 'text' -> 'message'
        'sender': settings.EGOSMS_SENDER_ID, 
    }

    try:
        # GET is the preferred method for the /v1/plain/ endpoint
        response = requests.get(settings.EGOSMS_API_URL, params=params, timeout=15)
        
        # Log the raw response for debugging
        print(f"[SMS DEBUG] Phone: {formatted} | Status: {response.status_code} | Resp: {response.text}")
        
        # Logic to determine success: Check for 'OK' in the response text or JSON
        response_text = response.text.upper()
        success = response.status_code == 200 and 'OK' in response_text
        
        return success, response.text
    except requests.RequestException as e:
        print(f"[SMS ERROR] Connection failed: {e}")
        return False, str(e)

def send_registration_email_delayed(patient_email, context):
    """Sends a welcome email 5 seconds after registration."""
    def _send():
        time.sleep(5)
        # Handle cases where names might be missing
        display_name = context.get('name') or context.get('username') or "Valued Patient"
        
        subject = "Welcome to KRRH ANC Portal"
        message = (
            f"Dear {display_name},\n\n"
            f"You have been successfully registered at Kabale Regional Referral Hospital ANC Unit.\n\n"
            f"• Expected Delivery Date: {context.get('edd', 'N/A')}\n"
            f"• Assigned Doctor: {context.get('doctor_name', 'TBA')}\n"
            f"• Ward: {context.get('ward', 'N/A')}\n\n"
            f"Your login credentials:\n"
            f"• Username: {context.get('username')}\n"
            f"• Password: {context.get('password')}\n\n"
            f"KRRH ANC Portal | Kabale Regional Referral Hospital"
        )
        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [patient_email], fail_silently=False)
            print(f"[EMAIL] Registration email sent to {patient_email}")
        except Exception as e:
            print(f"[EMAIL] Registration email failed: {e}")

    threading.Thread(target=_send, daemon=True).start()

def send_registration_sms(phone, patient_name, edd):
    """Send welcome SMS on registration."""
    msg = (
        f"Welcome to KRRH ANC, {patient_name}! "
        f"Registration successful. Your EDD is {edd}. "
        f"Please attend all checkups. KRRH"
    )
    success, resp = send_egosms(phone, msg)
    return success

def start_reminder_loop(patient_id):
    """
    Background loop: Sends SMS and Email reminders.
    """
    interval = getattr(settings, 'REMINDER_INTERVAL_SECONDS', 120)

    def _loop():
        # Deferred imports to avoid circular dependencies
        from accounts.models import PatientProfile, ANCVisit, SMSLog

        while True:
            time.sleep(interval)
            try:
                profile = PatientProfile.objects.select_related('user').get(id=patient_id)
                
                if not profile.email_alerts_active:
                    print(f"[LOOP] Stopped for patient ID {patient_id} (Alerts Disabled)")
                    break

                next_visit = ANCVisit.objects.filter(
                    patient=profile, is_completed=False, status='PENDING'
                ).order_by('scheduled_date').first()

                if not next_visit:
                    print(f"[LOOP] No pending visits for {profile.user.username}. Stopping.")
                    break

                now = timezone.now()
                target_date = timezone.make_aware(
                    timezone.datetime.combine(next_visit.scheduled_date, timezone.datetime.min.time())
                )
                diff = target_date - now
                
                days_str = "today" if diff.days < 0 else f"{diff.days} days"
                first_name = profile.user.first_name or profile.user.username

                # --- SMS PROCESS ---
                sms_text = (
                    f"KRRH ANC: {first_name}, your visit {next_visit.visit_number} "
                    f"is in {days_str} ({next_visit.scheduled_date}). EDD: {profile.edd}. KRRH"
                )
                
                sms_success, sms_resp = send_egosms(profile.user.phone_number, sms_text)
                
                SMSLog.objects.create(
                    patient=profile,
                    phone_number=profile.user.phone_number,
                    message=sms_text,
                    status="Success" if sms_success else "Failed",
                    response_body=str(sms_resp)[:500]
                )

                # --- EMAIL PROCESS ---
                email_subject = f"ANC Reminder: Visit {next_visit.visit_number} in {days_str}"
                email_body = (
                    f"Dear {first_name},\n\n"
                    f"This is a reminder for your next ANC visit at KRRH.\n"
                    f"Visit Number: {next_visit.visit_number}\n"
                    f"Scheduled Date: {next_visit.scheduled_date}\n\n"
                    f"KRRH Antenatal Unit"
                )
                
                if profile.user.email:
                    try:
                        send_mail(email_subject, email_body, settings.DEFAULT_FROM_EMAIL, 
                                 [profile.user.email], fail_silently=False)
                        print(f"[LOOP] Email sent to {profile.user.email}")
                    except Exception as e:
                        print(f"[LOOP] Email SMTP Error: {e}")

            except PatientProfile.DoesNotExist:
                break
            except Exception as e:
                print(f"[LOOP] Critical loop error: {e}")
                time.sleep(30)

    threading.Thread(target=_loop, daemon=True).start()

def send_missed_visit_alerts(visit):
    """Sends alerts when a staff member marks a visit as MISSED."""
    profile = visit.patient
    name = profile.user.first_name or profile.user.username
    phone = profile.user.phone_number
    email = profile.user.email

    sms_msg = (
        f"KRRH ANC ALERT: Dear {name}, you MISSED your ANC Visit {visit.visit_number} "
        f"scheduled for {visit.scheduled_date}. Please contact KRRH immediately. KRRH"
    )
    
    email_msg = (
        f"Dear {name},\n\n"
        f"You missed your scheduled ANC visit on {visit.scheduled_date}.\n"
        f"Missing checkups is risky for your health. Please visit the clinic today.\n\n"
        f"KRRH Antenatal Unit"
    )

    if phone:
        send_egosms(phone, sms_msg)

    if email:
        try:
            send_mail("MISSED ANC Visit - KRRH", email_msg, settings.DEFAULT_FROM_EMAIL, 
                      [email], fail_silently=False)
        except Exception as e:
            print(f"[ALERT] Missed email failed: {e}")
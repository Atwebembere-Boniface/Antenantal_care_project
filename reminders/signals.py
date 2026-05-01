import threading
import time
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .sms_utils import send_yo_sms
from .models import SMSLog

User = get_user_model()

def delayed_sms_task(user_id, phone, message):
    """The background task that waits 60 seconds."""
    time.sleep(60)
    
    # Re-fetch user to ensure they still exist
    try:
        user = User.objects.get(id=user_id)
        success, response = send_yo_sms(phone, message)
        
        # Log the result
        SMSLog.objects.create(
            user=user,
            phone_number=phone,
            message=message,
            status='SUCCESS' if success else 'FAILED'
        )
    except User.DoesNotExist:
        pass

@receiver(post_save, sender=User)
def trigger_welcome_sms(sender, instance, created, **kwargs):
    if created and instance.phone_number:
        welcome_msg = f"Hello {instance.first_name}, welcome to KRRH ANC system. Your health is our priority."
        
        # Start the thread
        thread = threading.Thread(
            target=delayed_sms_task, 
            args=(instance.id, instance.phone_number, welcome_msg)
        )
        thread.start()
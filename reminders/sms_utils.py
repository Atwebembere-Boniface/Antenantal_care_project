import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

def format_ug_phone(phone):
    """Converts 07... or +256... to 2567XXXXXXXX"""
    phone = str(phone).replace("+", "").replace(" ", "")
    if phone.startswith('0'):
        phone = '256' + phone[1:]
    return phone

def send_yo_sms(phone, message):
    formatted_phone = format_ug_phone(phone)
    
    # Typical Yo! Uganda payload is often XML or JSON via POST
    # Note: Check your specific Yo! documentation for the exact field names
    payload = {
        'username': settings.YO_API_USERNAME,
        'password': settings.YO_API_PASSWORD,
        'to': formatted_phone,
        'text': message,
    }

    try:
        response = requests.post(settings.YO_API_URL, data=payload, timeout=10)
        response.raise_for_status()
        
        # Log successful response
        logger.info(f"SMS sent to {formatted_phone}: {response.text}")
        return True, response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Yo! SMS Failed for {formatted_phone}: {str(e)}")
        return False, str(e)
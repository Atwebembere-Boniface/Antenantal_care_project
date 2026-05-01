from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ANCVisit
from .utils import send_missed_visit_alerts


@receiver(post_save, sender=ANCVisit)
def handle_missed_visit(sender, instance, created, **kwargs):
    """Send immediate alerts when a visit is marked MISSED."""
    if not created and instance.status == 'MISSED':
        send_missed_visit_alerts(instance)
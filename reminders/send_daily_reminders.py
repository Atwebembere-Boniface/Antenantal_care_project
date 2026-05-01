from django.core.management.base import BaseCommand
from reminders.services import send_upcoming_reminders


class Command(BaseCommand):
    help = 'Sends SMS/Email reminders for ANC visits scheduled for tomorrow'

    def handle(self, *args, **options):
        self.stdout.write("Checking for upcoming ANC visits...")
        count = send_upcoming_reminders()
        self.stdout.write(self.style.SUCCESS(f'Successfully sent {count} reminders.'))
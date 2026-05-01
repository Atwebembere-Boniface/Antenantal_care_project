from django.views.generic import ListView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone

from .models import ReminderLog
from .services import send_upcoming_reminders, send_bulk_welcome_sms
from accounts.models import PatientProfile, ANCVisit


class ReminderHistoryView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ReminderLog
    template_name = 'reminders/history.html'
    context_object_name = 'reminders'
    ordering = ['-date_sent']

    def test_func(self):
        return getattr(self.request.user, 'role', None) in ['ADMIN', 'NURSE'] or self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        next_visit = ANCVisit.objects.filter(
            scheduled_date__gt=timezone.now().date(), is_completed=False
        ).order_by('scheduled_date').first()

        if next_visit:
            now = timezone.now()
            target = timezone.make_aware(
                timezone.datetime.combine(next_visit.scheduled_date, timezone.datetime.min.time())
            )
            diff = target - now
            days = diff.days
            hours, rem = divmod(diff.seconds, 3600)
            minutes, seconds = divmod(rem, 60)
            context['next_visit'] = next_visit
            context['countdown'] = {
                'days': days, 'hours': hours,
                'minutes': minutes, 'seconds': seconds,
                'target_iso': target.isoformat()
            }
        return context


def trigger_reminders_view(request):
    count = send_upcoming_reminders()
    messages.success(request, f"Successfully sent {count} reminders.")
    return redirect('reminder_history')


class BulkSMSTriggerView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return getattr(self.request.user, 'role', None) == 'ADMIN' or self.request.user.is_superuser

    def post(self, request):
        count = send_bulk_welcome_sms()
        messages.success(request, f"Bulk SMS complete. {count} messages sent.")
        return redirect('reminder_history')

    def get(self, request):
        return redirect('reminder_history')


class UpdateVisitStatusView(LoginRequiredMixin, View):
    def post(self, request, pk, action):
        visit = get_object_or_404(ANCVisit, pk=pk)

        if action == 'attend':
            visit.status = 'ATTENDED'
            visit.is_completed = True
            visit.clinical_notes = request.POST.get(f'notes_{pk}', 'Patient attended.')
        elif action == 'missed':
            visit.status = 'MISSED'
            visit.is_completed = False
        elif action == 'undo':
            visit.status = 'PENDING'
            visit.is_completed = False
            visit.clinical_notes = ""

        visit.save()
        return redirect('patient_detail', pk=visit.patient.pk)
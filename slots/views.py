from django.views import View
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView
from datetime import date, timedelta

from accounts.models import User, PatientProfile
from .models import Appointment, PractitionerAssignment

HOURS = list(range(9, 18))  # 9am to 5pm

def get_hour_label(h):
    suffix = 'AM' if h < 12 else 'PM'
    display_h = h if h <= 12 else h - 12
    if display_h == 0: display_h = 12
    return f"{display_h}:00 {suffix}"

def get_doctor_display_name(doctor):
    full_name = doctor.get_full_name().strip()
    return full_name if full_name else doctor.username

class BookAppointmentView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'slots/book_appointment.html'

    def test_func(self):
        return getattr(self.request.user, 'role', None) == 'PATIENT'

    def get(self, request):
        profile = get_object_or_404(PatientProfile, user=request.user)
        doctors = User.objects.filter(role='DOCTOR')
        today = date.today()

        for doctor in doctors:
            doctor.display_name = get_doctor_display_name(doctor)

        availability = {}
        for doctor in doctors:
            availability[doctor.id] = {}
            for day_offset in range(7):
                check_date = today + timedelta(days=day_offset)
                day_slots = []
                for h in HOURS:
                    booked = Appointment.objects.filter(
                        doctor=doctor, date=check_date, hour=h,
                        status__in=['APPROVED', 'PENDING']
                    ).count()
                    day_slots.append({
                        'hour': h,
                        'label': get_hour_label(h),
                        'available': booked < 2,
                        'booked': booked,
                    })
                availability[doctor.id][check_date.isoformat()] = day_slots

        existing = Appointment.objects.filter(patient=profile).order_by('-created_at')[:5]

        return render(request, self.template_name, {
            'doctors': doctors,
            'availability': availability,
            'today': today,
            'existing_appointments': existing,
        })

    def post(self, request):
        profile = get_object_or_404(PatientProfile, user=request.user)
        doctor_id = request.POST.get('doctor_id')
        appt_date = request.POST.get('date')
        hour = int(request.POST.get('hour', 9))
        reason = request.POST.get('reason', '')

        doctor = get_object_or_404(User, pk=doctor_id, role='DOCTOR')
        doctor_name = get_doctor_display_name(doctor)

        booked = Appointment.objects.filter(
            doctor=doctor, date=appt_date, hour=hour,
            status__in=['APPROVED', 'PENDING']
        ).count()
        if booked >= 2:
            messages.error(request, f"Dr. {doctor_name} is full at that time.")
            return redirect('slots:book_appointment')

        existing = Appointment.objects.filter(
            patient=profile, date=appt_date, hour=hour,
            status__in=['APPROVED', 'PENDING']
        ).exists()
        if existing:
            messages.warning(request, "You already have an appointment at that time.")
            return redirect('slots:book_appointment')

        Appointment.objects.create(
            patient=profile,
            doctor=doctor,
            date=appt_date,
            hour=hour,
            reason=reason,
            status='PENDING'
        )
        messages.success(request, f"Appointment request sent to Dr. {doctor_name}.")
        return redirect('accounts:patient_dashboard')


class DoctorAppointmentsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'slots/doctor_appointments.html'

    def test_func(self):
        return getattr(self.request.user, 'role', None) in ['DOCTOR', 'NURSE']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doctor = self.request.user
        today = date.today()

        hourly_schedule = []
        for h in HOURS:
            appts = Appointment.objects.filter(
                doctor=doctor, date=today, hour=h,
                status__in=['APPROVED', 'PENDING']
            ).select_related('patient__user')
            hourly_schedule.append({
                'hour': h,
                'label': get_hour_label(h),
                'appointments': list(appts),
                'count': appts.count(),
                'is_full': appts.count() >= 2,
            })

        context['hourly_schedule'] = hourly_schedule
        context['today'] = today
        context['pending_approvals'] = Appointment.objects.filter(
            doctor=doctor, status='PENDING'
        ).select_related('patient__user').order_by('date', 'hour')
        return context


class ApproveAppointmentView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return getattr(self.request.user, 'role', None) in ['DOCTOR', 'NURSE']

    def post(self, request, pk, action):
        appt = get_object_or_404(Appointment, pk=pk, doctor=request.user)
        patient_name = appt.patient.user.get_full_name() or appt.patient.user.username
        if action == 'approve':
            appt.status = 'APPROVED'
            appt.notes = request.POST.get('notes', '')
            messages.success(request, f"Appointment for {patient_name} approved.")
        elif action == 'reject':
            appt.status = 'REJECTED'
            messages.warning(request, "Appointment rejected.")
        elif action == 'complete':
            appt.status = 'COMPLETED'
            appt.notes = request.POST.get('notes', '')
            messages.success(request, "Appointment completed.")
        appt.save()
        return redirect('slots:doctor_appointments')


class AssignPractitionerView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_superuser or getattr(self.request.user, 'role', None) == 'ADMIN'

    def post(self, request, patient_id):
        patient = get_object_or_404(PatientProfile, pk=patient_id)
        doctor_id = request.POST.get('doctor_id')
        doctor = get_object_or_404(User, pk=doctor_id)
        doctor_name = get_doctor_display_name(doctor)
        
        PractitionerAssignment.objects.update_or_create(
            patient=patient, defaults={'practitioner': doctor}
        )
        messages.success(request, f"Assigned {patient.user.username} to Dr. {doctor_name}.")
        return redirect('accounts:admin_dashboard')


class AvailableSlotsView(LoginRequiredMixin, View):
    def get(self, request):
        from django.http import JsonResponse
        doctor_id = request.GET.get('doctor_id')
        appt_date = request.GET.get('date')
        if not doctor_id or not appt_date:
            return JsonResponse({'slots': []})
        slots = []
        for h in HOURS:
            booked = Appointment.objects.filter(
                doctor_id=doctor_id, date=appt_date, hour=h,
                status__in=['APPROVED', 'PENDING']
            ).count()
            slots.append({
                'hour': h,
                'label': get_hour_label(h),
                'available': booked < 2,
            })
        return JsonResponse({'slots': slots})
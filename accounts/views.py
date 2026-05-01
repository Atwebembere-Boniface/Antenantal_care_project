from django.apps import apps
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, update_session_auth_hash
from django.views.generic import CreateView, TemplateView, ListView, DetailView, View
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib import messages
from .models import Message
from django.db.models import Count
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.utils import timezone
from datetime import date
from django.views.generic.edit import UpdateView

# Corrected Imports: Note 'PatientProfile' instead of 'Patient'
from .models import User, StaffProfile, PatientProfile, ANCVisit, generate_anc_visits
from .forms import StaffSignUpForm, PatientRegistrationForm, ForcePasswordChangeForm
from .utils import send_registration_email_delayed, send_registration_sms, start_reminder_loop
from django.contrib.auth import get_user_model
User = get_user_model()

# ... (HomeView, UserLoginView, ForcePasswordChangeView, StaffSignUpView, PatientListView remain the same) ...

class ExportMothersPDFView(LoginRequiredMixin, View):
    """
    Generates a PDF report of all registered mothers, 
    their EDD, and contact information.
    """
    def get(self, request, *args, **kwargs):
        # 1. Fetch Data using the correct model name
        # We select_related('user') to avoid multiple database hits in the template
        patients = PatientProfile.objects.all().select_related('user').order_by('user__last_name')
        today = timezone.now()
        
        # 2. Prepare Context
        context = {
            'patients': patients,
            'today': today,
            'hospital_name': 'KRRH Antenatal Clinic'
        }
        
        # 3. Render Template to HTML String
        template = get_template('reports/mothers_report_pdf.html')
        html = template.render(context)
        
        # 4. Prepare PDF Response
        response = HttpResponse(content_type='application/pdf')
        filename = f"Mothers_Report_{today.strftime('%Y-%m-%d')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # 5. Generate PDF
        pisa_status = pisa.CreatePDF(html, dest=response)
        
        # 6. Error Handling
        if pisa_status.err:
            return HttpResponse(f'Error generating PDF: <pre>{html}</pre>')
        
        return response

# (Keep the rest of your views like AdminDashboardView, etc. below)



class UserLoginView(LoginView):
    template_name = 'accounts/login.html'

    def get_success_url(self):
        user = self.request.user
        if user.must_change_password:
            return reverse_lazy('accounts:force_password_change')
        if user.is_superuser or user.role == 'ADMIN':
            return reverse_lazy('accounts:admin_dashboard')
        elif user.role in ['DOCTOR', 'NURSE']:
            return reverse_lazy('accounts:staff_dashboard')
        elif user.role == 'PATIENT':
            return reverse_lazy('accounts:patient_dashboard')
        return reverse_lazy('accounts:home')

class ForcePasswordChangeView(LoginRequiredMixin, View):
    template_name = 'accounts/force_password_change.html'

    def get(self, request):
        if not request.user.must_change_password:
            return redirect('accounts:home')
        form = ForcePasswordChangeForm(request.user)
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = ForcePasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            new_username = form.cleaned_data['new_username']
            user = form.save()
            user.username = new_username
            user.must_change_password = False
            user.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Your username and password have been updated successfully!")
            if user.role == 'PATIENT':
                return redirect('accounts:patient_dashboard')
            return redirect('accounts:home')
        return render(request, self.template_name, {'form': form})

class StaffSignUpView(CreateView):
    model = User
    form_class = StaffSignUpForm
    template_name = 'accounts/signup_form.html'
    success_url = reverse_lazy('accounts:staff_dashboard')

    def form_valid(self, form):
        user = form.save()
        user.is_staff = True
        user.save()
        StaffProfile.objects.update_or_create(user=user, defaults={'department': "Antenatal Care"})
        login(self.request, user)
        return super().form_valid(form)

class PatientListView(LoginRequiredMixin, ListView):
    model = PatientProfile
    template_name = 'accounts/patient_list.html'
    context_object_name = 'patients'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == 'ADMIN':
            # Removed 'assigned_doctor' from select_related
            return PatientProfile.objects.all().select_related('user')
        return PatientProfile.objects.filter(assigned_doctor=user).select_related('user')
    

    
class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'accounts/admin_dashboard.html'

    def test_func(self):
        return self.request.user.is_superuser or getattr(self.request.user, 'role', None) == 'ADMIN'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()
        from slots.models import Appointment
        context['total_patients'] = PatientProfile.objects.count()
        context['total_staff'] = User.objects.filter(role__in=['DOCTOR', 'NURSE']).count()
        today_appointments = Appointment.objects.filter(
            date=today,
            status__in=['APPROVED', 'PENDING']
        ).select_related('patient__user', 'doctor')
        context['today_visits'] = today_appointments.count()
        context['today_appointments'] = today_appointments.order_by('hour')
        context['all_staff'] = User.objects.filter(role__in=['DOCTOR', 'NURSE']).annotate(
            current_workload=Count('doctor_patients')
        ).order_by('last_name')
        return context

class StaffDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'accounts/staff_dashboard.html'

    def test_func(self):
        return getattr(self.request.user, 'role', None) in ['DOCTOR', 'NURSE']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doctor = self.request.user
        today = date.today()
        from slots.models import Appointment
        
        # 1. Hourly Load Logic (Stays specific to the logged-in doctor)
        hours = list(range(9, 18))
        hourly_slots = []
        for h in hours:
            appts = Appointment.objects.filter(
                doctor=doctor, date=today, hour=h,
                status__in=['APPROVED', 'PENDING']
            ).select_related('patient__user')
            hourly_slots.append({
                'label': f"{h % 12 or 12}:00 {'AM' if h < 12 else 'PM'}",
                'appointments': appts,
                'is_full': appts.count() >= 2,
                'count': appts.count(),
            })

        # 2. Update the Context
        context.update({
            'today': today,
            'hourly_slots': hourly_slots,
            # CHANGE: We now fetch ALL patients instead of just those assigned to the doctor
            'patients': PatientProfile.objects.all().select_related('user').prefetch_related('anc_visits').order_by('-user__date_joined'),
            
            # This counts only the appointments for the current doctor today
            'my_today_count': Appointment.objects.filter(doctor=doctor, date=today, status__in=['APPROVED', 'PENDING']).count(),
            
            # This shows total scheduled visits across the entire system
            'total_scheduled': Appointment.objects.filter(date__gte=today, status__in=['APPROVED', 'PENDING']).count(),
        })
        return context
    

class AppointmentManagementView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'accounts/appointment_management.html'

    def test_func(self):
        return getattr(self.request.user, 'role', None) in ['DOCTOR', 'NURSE']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from slots.models import Appointment
        today = date.today()
        all_appointments = Appointment.objects.filter(
            date__gte=today,
            status__in=['APPROVED', 'PENDING']
        ).select_related('patient__user', 'doctor').order_by('date', 'hour')
        doctors_schedule = {}
        for appt in all_appointments:
            doc_name = appt.doctor.get_full_name() or appt.doctor.username
            if doc_name not in doctors_schedule:
                doctors_schedule[doc_name] = []
            doctors_schedule[doc_name].append(appt)
        context['doctors_schedule'] = doctors_schedule
        return context

class PatientDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'accounts/patient_dashboard.html'

    def test_func(self):
        return getattr(self.request.user, 'role', None) == 'PATIENT'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['today'] = date.today()
        try:
            profile = PatientProfile.objects.get(user=self.request.user)
            context['profile'] = profile
            context['visits'] = profile.anc_visits.all().order_by('scheduled_date')
            context['next_visit'] = profile.anc_visits.filter(
                is_completed=False, status='PENDING'
            ).order_by('scheduled_date').first()
            context['attended_count'] = profile.anc_visits.filter(is_completed=True).count()
            context['total_visits_count'] = profile.anc_visits.count() + 1
        except PatientProfile.DoesNotExist:
            context['profile'] = None
        return context

class PatientRegistrationView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = User
    form_class = PatientRegistrationForm
    template_name = 'accounts/register_patient.html'
    success_url = reverse_lazy('accounts:patient_list')

    def test_func(self):
        return self.request.user.is_superuser or getattr(self.request.user, 'role', None) == 'ADMIN'

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.object
        profile = getattr(user, 'patient_profile', None)
        if profile:
            ANCVisit.objects.get_or_create(
                patient=profile,
                visit_number=1,
                defaults={'scheduled_date': date.today(), 'is_completed': True, 'status': 'ATTENDED',
                          'clinical_notes': 'Initial registration visit.'}
            )
            generate_anc_visits(profile)
            email_context = {
                'name': user.get_full_name() or user.username,
                'edd': profile.edd.strftime('%d %B %Y'),
                'doctor_name': profile.assigned_doctor.get_full_name() if profile.assigned_doctor else "To be assigned",
                'ward': profile.ward_number,
                'username': user.username,
                'password': user.username,
            }
            send_registration_email_delayed(user.email, email_context)
            send_registration_sms(user.phone_number, user.first_name, profile.edd.strftime('%d %b %Y'))
            start_reminder_loop(profile.id)
            messages.success(self.request, f"Patient {user.get_full_name()} registered. Alerts started.")
        return response

class PatientDetailView(LoginRequiredMixin, DetailView):
    model = PatientProfile
    template_name = 'accounts/patient_detail.html'
    context_object_name = 'patient'

    def get_queryset(self):
        # select_related('user') ensures the user object is always available for the URL tag
        return super().get_queryset().select_related('user').prefetch_related('anc_visits', 'sms_logs')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Sort visits by number for the table
        context['visits'] = self.object.anc_visits.all().order_by('visit_number')
        context['today'] = timezone.now().date()
        return context
    

class CompleteVisitView(LoginRequiredMixin, View):
    def post(self, request, visit_id):
        visit = get_object_or_404(ANCVisit, id=visit_id)
        visit.is_completed = True
        visit.status = 'ATTENDED'
        visit.clinical_notes = request.POST.get('notes', '')
        visit.save()
        messages.success(request, "Visit marked as attended.")
        return redirect('accounts:patient_detail', pk=visit.patient.pk)

class StaffListView(LoginRequiredMixin, ListView):
    model = User
    template_name = 'accounts/staff_list.html'
    context_object_name = 'staff_members'

    def get_queryset(self):
        return User.objects.filter(role__in=['DOCTOR', 'NURSE']).select_related('staff_profile').order_by('last_name')

class ToggleEmailAlertsView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.role == 'ADMIN' or self.request.user.is_superuser

    def post(self, request, pk):
        profile = get_object_or_404(PatientProfile, pk=pk)
        profile.email_alerts_active = not profile.email_alerts_active
        profile.save()
        if profile.email_alerts_active:
            start_reminder_loop(profile.id)
            messages.success(request, f"Alerts RESTARTED for {profile.user.get_full_name()}")
        else:
            messages.warning(request, f"Alerts STOPPED for {profile.user.get_full_name()}")
        return redirect('accounts:patient_list')

class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    template_name = 'accounts/profile_update.html'
    fields = ['first_name', 'last_name', 'username', 'email', 'profile_picture']

    def get_object(self):
        return self.request.user

    def get_success_url(self):
        user = self.request.user
        if user.role == 'PATIENT':
            return reverse_lazy('accounts:patient_dashboard')
        elif user.role in ['DOCTOR', 'NURSE']:
            return reverse_lazy('accounts:staff_dashboard')
        elif user.role == 'ADMIN' or user.is_superuser:
            return reverse_lazy('accounts:admin_dashboard')
        return reverse_lazy('accounts:home')

    def form_valid(self, form):
        messages.success(self.request, "Profile updated successfully!")
        return super().form_valid(form)
    


class ConversationView(LoginRequiredMixin, View):
    template_name = 'accounts/conversation.html'

    def get(self, request, user_id):
        # The 'partner' is the patient or staff member being messaged
        partner = get_object_or_404(User, id=user_id)
        
        # Fetch conversation history
        # Note: 'messages' is the variable name used in the template loop
        messages = Message.objects.filter(
            (Q(sender=request.user) & Q(recipient=partner)) |
            (Q(sender=partner) & Q(recipient=request.user))
        ).select_related('sender').order_by('created_at')

        context = {
            'partner': partner,
            'messages': messages,
        }
        return render(request, self.template_name, context)

    def post(self, request, user_id):
        partner = get_object_or_404(User, id=user_id)
        # In the template, the input name was 'body'
        content = request.POST.get('body')

        if content and content.strip():
            Message.objects.create(
                sender=request.user,
                recipient=partner,
                body=content.strip() # Ensure your Model field is named 'body' or change to 'content'
            )
        
        # IMPORTANT: Use 'messaging:conversation' if your app_name is messaging
        # or 'accounts:conversation' if it is in accounts
        return redirect('messaging:conversation', user_id=user_id)
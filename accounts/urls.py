from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.UserLoginView.as_view(), name='login'),
    # Note: Ensure 'home' exists in your main urls.py or change to 'accounts:login'
    path('logout/', LogoutView.as_view(next_page='accounts:login'), name='logout'),
    path('signup/staff/', views.StaffSignUpView.as_view(), name='staff_signup'),
    path('force-password-change/', views.ForcePasswordChangeView.as_view(), name='force_password_change'),

    # Dashboards
    path('dashboard/admin/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('dashboard/staff/', views.StaffDashboardView.as_view(), name='staff_dashboard'),
    path('dashboard/patient/', views.PatientDashboardView.as_view(), name='patient_dashboard'),

    # Patient Management
    path('register-patient/', views.PatientRegistrationView.as_view(), name='register_patient'),
    path('patients/', views.PatientListView.as_view(), name='patient_list'),
    path('patient/<int:pk>/', views.PatientDetailView.as_view(), name='patient_detail'),
    path('staff/', views.StaffListView.as_view(), name='staff_list'),
    path('patient/<int:pk>/toggle-alerts/', views.ToggleEmailAlertsView.as_view(), name='toggle_alerts'),
    
    # Appointments - Renamed to match the template 'appointment_management'
    path('staff/appointments/', views.AdminDashboardView.as_view(), name='appointment_management'),
    
    # Messaging - Ensure the parameter name matches the View's get/post methods
    path('patient/<int:user_id>/message/', views.ConversationView.as_view(), name='conversation'),

    # Visits
    path('visit/complete/<int:visit_id>/', views.CompleteVisitView.as_view(), name='complete_visit'),
    
    # Profile & Reports
    path('profile/update/', views.ProfileUpdateView.as_view(), name='profile_update'),
    path('export/mothers-pdf/', views.ExportMothersPDFView.as_view(), name='generate_mothers_report'),
]
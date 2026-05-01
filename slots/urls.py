from django.urls import path
from . import views

app_name = 'slots' # This is necessary for slots:book_appointment to work

urlpatterns = [
    path('book/', views.BookAppointmentView.as_view(), name='book_appointment'),
    path('doctor/', views.DoctorAppointmentsView.as_view(), name='doctor_appointments'),
    path('appointment/<int:pk>/<str:action>/', views.ApproveAppointmentView.as_view(), name='manage_appointment'),
    path('assign/<int:patient_id>/', views.AssignPractitionerView.as_view(), name='assign_practitioner'),
    path('available-slots/', views.AvailableSlotsView.as_view(), name='available_slots'),
]
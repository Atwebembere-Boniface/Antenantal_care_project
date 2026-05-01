from django.urls import path
from . import views

urlpatterns = [
    path('history/', views.ReminderHistoryView.as_view(), name='reminder_history'),
    path('trigger/', views.trigger_reminders_view, name='trigger_reminders'),
    path('trigger-bulk/', views.BulkSMSTriggerView.as_view(), name='trigger_bulk_sms'),
    path('visit/update/<int:pk>/<str:action>/', views.UpdateVisitStatusView.as_view(), name='update_visit'),
]
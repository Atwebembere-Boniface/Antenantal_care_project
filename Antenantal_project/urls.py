# Antenantal_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Import the Class instead of a function
from accounts.views import PatientDashboardView 

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 1. GLOBAL HOME ROUTE
    # For Class-Based Views, you MUST use .as_view()
    path('', PatientDashboardView.as_view(), name='home'), 
    

    # 2. NAMESPACED APP INCLUDES
    path('accounts/', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('reminders/', include(('reminders.urls', 'reminders'), namespace='reminders')),
    path('slots/', include(('slots.urls', 'slots'), namespace='slots')),
    path('messaging/', include(('messaging.urls', 'messaging'), namespace='messaging')),
    path('chatbot/', include(('chatbot.urls', 'chatbot'), namespace='chatbot')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
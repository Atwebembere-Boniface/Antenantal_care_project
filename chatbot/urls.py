from django.urls import path
from . import views
app_name = 'chatbot'

urlpatterns = [
    path('ask/', views.chat_with_voice, name='chat_with_voice'),
]
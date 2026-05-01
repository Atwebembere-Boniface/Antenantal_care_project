from django.urls import path
from . import views

app_name = 'messaging'  # This links the 'messaging:' prefix to these patterns

urlpatterns = [
    path('inbox/', views.InboxView.as_view(), name='inbox'),
    path('conversation/<int:user_id>/', views.ConversationView.as_view(), name='conversation'),
    path('send/', views.SendMessageView.as_view(), name='send_message'),
]
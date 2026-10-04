from django.urls import path

from . import views

app_name = 'whatsapp'

urlpatterns = [
    path('config/', views.WhatsAppConfigView.as_view(), name='config'),
    path('group/', views.WhatsAppGroupView.as_view(), name='group'),
    path('messages/', views.WhatsAppMessageListView.as_view(), name='message-list'),
    path('messages/<int:pk>/resend/', views.WhatsAppResendView.as_view(), name='message-resend'),
    path('test-message/', views.WhatsAppTestMessageView.as_view(), name='test-message'),
]

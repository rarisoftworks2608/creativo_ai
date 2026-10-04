from django.urls import path

from . import views

app_name = 'whatsapp_global'

urlpatterns = [
    path('status/', views.WhatsAppStatusView.as_view(), name='status'),
    path('templates/', views.WhatsAppTemplateListCreateView.as_view(), name='template-list-create'),
    path('templates/sync/', views.WhatsAppTemplateSyncView.as_view(), name='template-sync'),
    path('templates/<int:pk>/', views.WhatsAppTemplateDetailView.as_view(), name='template-detail'),
    path('webhook/', views.WhatsAppWebhookView.as_view(), name='webhook'),
]

from django.urls import path

from . import views

app_name = 'prompt_templates'

urlpatterns = [
    path('', views.PromptTemplateListCreateView.as_view(), name='list-create'),
    path('<int:pk>/', views.PromptTemplateDetailView.as_view(), name='detail'),
    path('<int:pk>/new-version/', views.PromptTemplateNewVersionView.as_view(), name='new-version'),
    path('<int:pk>/activate/', views.PromptTemplateActivateView.as_view(), name='activate'),
    path('<int:pk>/deactivate/', views.PromptTemplateDeactivateView.as_view(), name='deactivate'),
    path('history/<slug:slug>/', views.PromptTemplateHistoryView.as_view(), name='history'),
]

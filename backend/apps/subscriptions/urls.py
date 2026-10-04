from django.urls import path

from . import views

app_name = 'subscriptions'

urlpatterns = [
    path('', views.SubscriptionListCreateView.as_view(), name='subscription-list-create'),
    path('<int:pk>/', views.SubscriptionDetailView.as_view(), name='subscription-detail'),
    path('plans/', views.PlanListCreateView.as_view(), name='plan-list-create'),
    path('plans/<int:pk>/', views.PlanDetailView.as_view(), name='plan-detail'),
    path('usage-overview/', views.UsageOverviewView.as_view(), name='usage-overview'),
]

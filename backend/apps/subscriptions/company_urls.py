from django.urls import path

from . import views

app_name = 'company_subscription'

urlpatterns = [
    path('', views.CompanySubscriptionView.as_view(), name='current'),
    path('recalculate-storage/', views.CompanyStorageRecalculateView.as_view(), name='recalculate-storage'),
    path('billing/', views.BillingRecordListCreateView.as_view(), name='billing-list-create'),
    path('billing/<int:pk>/', views.BillingRecordDetailView.as_view(), name='billing-detail'),
]

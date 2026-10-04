from django.urls import path

from . import views

app_name = 'health'

urlpatterns = [
    path('', views.HealthView.as_view(), name='health'),
    path('details/', views.HealthDetailsView.as_view(), name='details'),
]

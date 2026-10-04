from django.urls import path

from . import views

app_name = 'publishing_global'

urlpatterns = [
    path('queue/', views.GlobalPublishQueueView.as_view(), name='queue'),
]

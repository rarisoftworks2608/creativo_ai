from django.urls import path

from . import views

app_name = 'music_library'

urlpatterns = [
    path('', views.BackgroundMusicListCreateView.as_view(), name='list-create'),
    path('<int:pk>/', views.BackgroundMusicDetailView.as_view(), name='detail'),
]

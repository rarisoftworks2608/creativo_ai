from django.urls import path

from . import views

app_name = 'content_calendar'

urlpatterns = [
    path('', views.ContentCalendarItemListCreateView.as_view(), name='item-list-create'),
    path('template/', views.ContentCalendarTemplateView.as_view(), name='template'),
    path('import/preview/', views.ContentCalendarImportPreviewView.as_view(), name='import-preview'),
    path('import/commit/', views.ContentCalendarImportCommitView.as_view(), name='import-commit'),
    path('<int:pk>/', views.ContentCalendarItemDetailView.as_view(), name='item-detail'),
    path('<int:pk>/duplicate/', views.ContentCalendarDuplicateView.as_view(), name='item-duplicate'),
]

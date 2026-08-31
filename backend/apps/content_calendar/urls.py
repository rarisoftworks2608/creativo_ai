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
    path('<int:pk>/generate-now/', views.ContentCalendarGenerateNowView.as_view(), name='item-generate-now'),
    path('<int:pk>/approve/', views.ContentCalendarApproveView.as_view(), name='item-approve'),
    path('<int:pk>/reject/', views.ContentCalendarRejectView.as_view(), name='item-reject'),
]

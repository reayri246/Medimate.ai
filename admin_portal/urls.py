from django.urls import path

from . import views

urlpatterns = [
    path('notifications/', views.send_notification, name='admin_send_notification'),
    path('documents/<int:document_id>/', views.document_detail, name='admin_document_detail'),
    path('documents/<int:document_id>/download/', views.document_download, name='admin_document_download'),
    path('', views.portal_home, name='portal_home'),
]

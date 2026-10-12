from django.urls import path

from . import views

urlpatterns = [
    path('', views.prescription_list, name='prescription_list'),
    path('upload/', views.prescription_upload, name='prescription_upload'),
    path('<int:document_id>/review/', views.document_review, name='document_review'),
    path('<int:document_id>/soft-copy/', views.prescription_soft_copy, name='prescription_soft_copy'),
    path('<int:document_id>/api.json', views.document_api, name='document_api'),
    path('<int:document_id>/fhir.json', views.document_fhir_export, name='document_fhir_export'),
    path('<int:document_id>/download/', views.document_download, name='document_download'),
]

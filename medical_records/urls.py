from django.urls import path

from . import views

urlpatterns = [
    path('', views.record_list, name='record_list'),
    path('<int:record_id>/', views.record_detail, name='medical_record_detail'),
]

from django.urls import path

from . import views

urlpatterns = [
    path('', views.guard_home, name='guard_home'),
]

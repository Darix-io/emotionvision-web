from django.urls import path

from . import views

app_name = 'emociones'

urlpatterns = [
    path('', views.inicio, name='inicio'),
]

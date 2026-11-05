from django.urls import path

from . import views

app_name = 'emociones'

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('camara/iniciar/', views.iniciar_camara, name='iniciar_camara'),
    path('camara/video/', views.video, name='video'),
    path('camara/estado/', views.estado, name='estado'),
    path('registros/estadisticas/', views.estadisticas, name='estadisticas'),
    path('registros/borrar/', views.borrar_registros, name='borrar_registros'),
    path('camara/detener/', views.detener_camara, name='detener_camara'),
]

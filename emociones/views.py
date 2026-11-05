from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from .camera import camara, generar_mjpeg


def inicio(request):
    """Página de inicio. No enciende la cámara."""
    return render(request, 'emociones/inicio.html')


@require_POST
def iniciar_camara(request):
    """Abre la cámara. Responde con un mensaje claro si no hay cámara."""
    if camara.iniciar():
        return JsonResponse({'ok': True})
    return JsonResponse(
        {'ok': False,
         'mensaje': 'No se encontró una cámara disponible. Conéctala, '
                    'ciérrala en otros programas y vuelve a intentar.'},
        status=503,
    )


@require_GET
def video(request):
    """Transmite el video al navegador (solo si la cámara ya fue iniciada)."""
    if not camara.activa:
        return JsonResponse(
            {'ok': False, 'mensaje': 'La cámara no está iniciada.'}, status=409)
    return StreamingHttpResponse(
        generar_mjpeg(camara),
        content_type='multipart/x-mixed-replace; boundary=frame',
    )


@require_GET
def estado(request):
    """Estado actual para el panel: cámara y emoción estimada (solo en memoria)."""
    return JsonResponse(camara.estado())


@require_POST
def detener_camara(request):
    """Libera la cámara."""
    camara.detener()
    return JsonResponse({'ok': True})

from django.shortcuts import render


def inicio(request):
    """Página de inicio (sin lógica pesada)."""
    return render(request, 'emociones/inicio.html')

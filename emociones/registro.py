"""Guardado y consulta de registros mínimos (fecha, emoción estimada y confianza).

Si la base de datos falla, nada de aquí lanza errores hacia el video.
"""
import logging
import time

from django.db.models import Count
from django.utils import timezone

from .models import RegistroEmocion

logger = logging.getLogger(__name__)

INTERVALO_SEGUNDOS = 2.0      # máximo un registro cada 2 s
ESPERA_TRAS_FALLO = 30.0      # si la base falla, no se reintenta en cada fotograma
CANTIDAD_ULTIMOS = 10


class RegistradorEmociones:
    """Guarda una estimación como máximo cada `intervalo` segundos."""

    def __init__(self, intervalo=INTERVALO_SEGUNDOS, espera_fallo=ESPERA_TRAS_FALLO,
                 reloj=time.monotonic):
        self.intervalo = intervalo
        self.espera_fallo = espera_fallo
        self._reloj = reloj
        self._proximo = 0.0  # momento a partir del cual se puede guardar de nuevo

    def registrar(self, estimacion):
        """Guarda la estimación si ya pasó el intervalo. Devuelve True si se guardó."""
        if estimacion is None:
            return False
        ahora = self._reloj()
        if ahora < self._proximo:
            return False
        try:
            RegistroEmocion.objects.create(
                emocion=estimacion.emocion, confianza=estimacion.confianza)
        except Exception:
            logger.exception('No se pudo guardar el registro; el video continúa')
            self._proximo = ahora + self.espera_fallo
            return False
        self._proximo = ahora + self.intervalo
        return True

    def reiniciar(self):
        """Permite guardar de inmediato (se usa al encender la cámara)."""
        self._proximo = 0.0


def estadisticas():
    """Total, cantidad por emoción y últimos 10 registros. Si la base falla, lo indica."""
    try:
        por_emocion = list(
            RegistroEmocion.objects.values('emocion')
            .annotate(cantidad=Count('id')).order_by('-cantidad', 'emocion'))
        ultimos = [
            {
                'fecha': timezone.localtime(r.fecha_hora).strftime('%d/%m/%Y'),
                'hora': timezone.localtime(r.fecha_hora).strftime('%H:%M:%S'),
                'emocion': r.emocion,
                'confianza': round(r.confianza * 100),
            }
            for r in RegistroEmocion.objects.all()[:CANTIDAD_ULTIMOS]
        ]
        return {
            'disponible': True,
            'total': sum(e['cantidad'] for e in por_emocion),
            'por_emocion': por_emocion,
            'ultimos': ultimos,
        }
    except Exception:
        logger.exception('No se pudieron leer las estadísticas')
        return {'disponible': False, 'total': 0, 'por_emocion': [], 'ultimos': []}


def borrar_registros():
    """Elimina todos los registros. Devuelve cuántos se borraron, o None si falló."""
    try:
        return RegistroEmocion.objects.all().delete()[0]
    except Exception:
        logger.exception('No se pudieron borrar los registros')
        return None

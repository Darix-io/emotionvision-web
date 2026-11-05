"""Captura de video con OpenCV (solo la cámara del equipo que ejecuta Django)."""
import os
import threading

import cv2

from .detector import DetectorRostros
from .emociones import EstimadorEmociones

SIN_DATOS = {'rostros': 0, 'emocion': None, 'confianza': None}


class Camara:
    """Abre la cámara, entrega fotogramas JPEG y la libera al detener."""

    def __init__(self, indice=0, detector=None, estimador=None):
        self.indice = indice
        self.detector = detector or DetectorRostros()
        self.estimador = estimador or EstimadorEmociones()
        self._captura = None
        self._ultimo = dict(SIN_DATOS)
        self._lock = threading.Lock()

    @property
    def activa(self):
        return self._captura is not None

    def iniciar(self):
        """Abre la cámara. Devuelve True si quedó lista, False si no hay cámara."""
        with self._lock:
            if self._captura is not None:
                return True
            # CAP_DSHOW abre más rápido y estable en Windows.
            api = cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY
            captura = cv2.VideoCapture(self.indice, api)
            if not captura.isOpened():
                captura.release()
                return False
            self._captura = captura
            return True

    def _estimaciones(self, fotograma, rostros):
        """Estimación por rostro (o None si no se pudo estimar)."""
        if not rostros:
            return []
        gris = cv2.cvtColor(fotograma, cv2.COLOR_BGR2GRAY)
        return [self.estimador.estimar(gris[y:y + alto, x:x + ancho])
                for x, y, ancho, alto in rostros]

    def _guardar_resumen(self, rostros, estimaciones):
        """Guarda en memoria (nada va a disco) lo último visto, para el panel."""
        principal = None  # se usa el rostro más grande
        mayor_area = 0
        for (_, _, ancho, alto), estimacion in zip(rostros, estimaciones):
            if estimacion and ancho * alto > mayor_area:
                principal, mayor_area = estimacion, ancho * alto
        self._ultimo = {
            'rostros': len(rostros),
            'emocion': principal.emocion if principal else None,
            'confianza': round(principal.confianza * 100) if principal else None,
        }

    def estado(self):
        """Datos para el panel: cámara, cantidad de rostros y emoción actual."""
        resumen = dict(self._ultimo) if self.activa else dict(SIN_DATOS)
        resumen['activa'] = self.activa
        return resumen

    def leer_jpeg(self):
        """Devuelve un fotograma en bytes JPEG, o None si no se pudo leer."""
        with self._lock:
            if self._captura is None:
                return None
            ok, fotograma = self._captura.read()
            if not ok:
                return None
            # Recuadros y etiquetas; si algo falla, el video sigue sin ellos.
            try:
                rostros = self.detector.detectar(fotograma)
                estimaciones = self._estimaciones(fotograma, rostros)
                etiquetas = [e.texto if e else None for e in estimaciones]
                self.detector.dibujar(fotograma, rostros, etiquetas)
                self._guardar_resumen(rostros, estimaciones)
            except cv2.error:
                self._ultimo = dict(SIN_DATOS)
            ok, jpeg = cv2.imencode('.jpg', fotograma)
            return jpeg.tobytes() if ok else None

    def detener(self):
        """Libera la cámara (la luz de la cámara se apaga)."""
        with self._lock:
            if self._captura is not None:
                self._captura.release()
                self._captura = None
            self._ultimo = dict(SIN_DATOS)


# Una sola cámara compartida por toda la aplicación.
camara = Camara()


def generar_mjpeg(cam=camara):
    """Genera el flujo multipart que el navegador muestra en un <img>."""
    try:
        while cam.activa:
            jpeg = cam.leer_jpeg()
            if jpeg is None:
                break
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n')
    finally:
        # Si el navegador cierra la conexión, no dejamos la cámara encendida.
        cam.detener()

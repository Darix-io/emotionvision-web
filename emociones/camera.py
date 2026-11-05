"""Captura de video con OpenCV (solo la cámara del equipo que ejecuta Django)."""
import os
import threading

import cv2


class Camara:
    """Abre la cámara, entrega fotogramas JPEG y la libera al detener."""

    def __init__(self, indice=0):
        self.indice = indice
        self._captura = None
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

    def leer_jpeg(self):
        """Devuelve un fotograma en bytes JPEG, o None si no se pudo leer."""
        with self._lock:
            if self._captura is None:
                return None
            ok, fotograma = self._captura.read()
            if not ok:
                return None
            ok, jpeg = cv2.imencode('.jpg', fotograma)
            return jpeg.tobytes() if ok else None

    def detener(self):
        """Libera la cámara (la luz de la cámara se apaga)."""
        with self._lock:
            if self._captura is not None:
                self._captura.release()
                self._captura = None


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

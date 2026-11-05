"""Detección de rostros con OpenCV (clasificador Haar cascade incluido en opencv-python).

Solo detecta DÓNDE hay un rostro. No identifica a la persona.
"""
import os

import cv2

ARCHIVO_CASCADA = 'haarcascade_frontalface_default.xml'
COLOR_RECUADRO = (0, 200, 0)  # verde (BGR)
COLOR_TEXTO = (200, 200, 200)
COLOR_TEXTO_ETIQUETA = (0, 0, 0)  # negro sobre fondo verde: se lee bien
TEXTO_SIN_ROSTRO = 'Sin rostro detectado'


class DetectorRostros:
    def __init__(self):
        ruta = os.path.join(cv2.data.haarcascades, ARCHIVO_CASCADA)
        self._clasificador = cv2.CascadeClassifier(ruta)
        if self._clasificador.empty():
            raise RuntimeError(f'No se pudo cargar el clasificador de rostros: {ruta}')

    def detectar(self, fotograma):
        """Devuelve una lista de rostros como (x, y, ancho, alto). Vacía si no hay."""
        if fotograma is None or fotograma.size == 0:
            return []
        gris = cv2.cvtColor(fotograma, cv2.COLOR_BGR2GRAY)
        gris = cv2.equalizeHist(gris)
        rostros = self._clasificador.detectMultiScale(
            gris, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        return [tuple(int(v) for v in r) for r in rostros]

    @staticmethod
    def _dibujar_etiqueta(fotograma, texto, x, y):
        """Texto grande sobre un fondo verde, pegado a la parte de arriba del recuadro."""
        fuente, escala, grosor = cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2
        (ancho_t, alto_t), base = cv2.getTextSize(texto, fuente, escala, grosor)
        alto_caja = alto_t + base + 10
        # Si no cabe arriba del recuadro, se escribe dentro.
        arriba = y - alto_caja if y - alto_caja >= 0 else y
        x0 = max(0, min(x, fotograma.shape[1] - ancho_t - 10))
        cv2.rectangle(fotograma, (x0, arriba), (x0 + ancho_t + 10, arriba + alto_caja),
                      COLOR_RECUADRO, cv2.FILLED)
        cv2.putText(fotograma, texto, (x0 + 5, arriba + alto_t + 5),
                    fuente, escala, COLOR_TEXTO_ETIQUETA, grosor, cv2.LINE_AA)

    def dibujar(self, fotograma, rostros, etiquetas=None):
        """Dibuja un rectángulo por rostro (con su etiqueta si la hay).

        Si no hay rostros, escribe un texto discreto.
        """
        for i, (x, y, ancho, alto) in enumerate(rostros):
            cv2.rectangle(fotograma, (x, y), (x + ancho, y + alto), COLOR_RECUADRO, 2)
            etiqueta = etiquetas[i] if etiquetas and i < len(etiquetas) else None
            if etiqueta:
                self._dibujar_etiqueta(fotograma, etiqueta, x, y)
        if not rostros:
            alto_img = fotograma.shape[0]
            cv2.putText(fotograma, TEXTO_SIN_ROSTRO, (10, alto_img - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_TEXTO, 1, cv2.LINE_AA)
        return fotograma

    def procesar(self, fotograma):
        """Detecta y dibuja sobre el fotograma. Devuelve la lista de rostros."""
        rostros = self.detectar(fotograma)
        self.dibujar(fotograma, rostros)
        return rostros

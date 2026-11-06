"""Estimación de emociones con el modelo ONNX FER+ (emotion-ferplus-8).

Es una ESTIMACIÓN del modelo: puede equivocarse según iluminación, posición y cámara.
No guarda imágenes ni identifica personas.
"""
import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

RUTA_MODELO = Path(__file__).resolve().parent / 'modelos' / 'emotion-ferplus-8.onnx'

# Orden de salida del modelo FER+, en español (sin tildes: OpenCV no las dibuja).
ETIQUETAS = ('neutral', 'feliz', 'sorpresa', 'tristeza',
             'enojo', 'asco', 'miedo', 'desprecio')

TAMANO = 64  # el modelo recibe imágenes grises de 64x64


CANTIDAD_TOP = 3


def porcentajes_enteros(probabilidades):
    """Convierte probabilidades (de mayor a menor) en porcentajes enteros que suman <= 100.

    La primera se redondea (así coincide con 'Feliz 82%'); las demás se truncan y se
    limitan a lo que falta para 100, para que el redondeo nunca pase de 100 en total.
    """
    if not probabilidades:
        return []
    primero = round(probabilidades[0] * 100)
    restante = 100 - primero
    porcentajes = [primero]
    for p in probabilidades[1:]:
        valor = max(0, min(int(p * 100), restante))
        porcentajes.append(valor)
        restante -= valor
    return porcentajes


@dataclass(frozen=True)
class Estimacion:
    emocion: str
    confianza: float  # entre 0 y 1
    # Las más probables, de mayor a menor: ((emocion, probabilidad), ...). Puede ir vacío.
    top: tuple = ()

    @property
    def texto(self):
        """Ejemplo: 'Feliz 82%'."""
        return f'{self.emocion.capitalize()} {round(self.confianza * 100)}%'

    @property
    def top3(self):
        """Ejemplo: [{'emocion': 'feliz', 'porcentaje': 82}, ...]. Vacío si no hay datos."""
        porcentajes = porcentajes_enteros([p for _, p in self.top])
        return [{'emocion': e, 'porcentaje': pct}
                for (e, _), pct in zip(self.top, porcentajes)]


class EstimadorEmociones:
    """Carga el modelo una sola vez y estima la emoción de un recorte de rostro."""

    def __init__(self, ruta_modelo=RUTA_MODELO, sesion=None):
        self._ruta = Path(ruta_modelo)
        self._sesion = sesion
        self._intentado = sesion is not None  # una sesión inyectada no se recarga
        self._entrada = None

    def _cargar(self):
        """Intenta cargar el modelo una sola vez. Si falla, queda desactivado."""
        if self._intentado:
            return
        self._intentado = True
        if not self._ruta.exists():
            logger.warning('Modelo de emociones no encontrado: %s', self._ruta)
            return
        try:
            import onnxruntime
            self._sesion = onnxruntime.InferenceSession(
                str(self._ruta), providers=['CPUExecutionProvider'])
        except Exception:
            logger.exception('No se pudo cargar el modelo de emociones')
            self._sesion = None

    @property
    def disponible(self):
        self._cargar()
        return self._sesion is not None

    def estimar(self, recorte_gris):
        """Recibe el recorte del rostro en gris. Devuelve Estimacion, o None si no se pudo."""
        if recorte_gris is None or recorte_gris.size == 0 or not self.disponible:
            return None
        try:
            imagen = cv2.resize(recorte_gris, (TAMANO, TAMANO))
            entrada = imagen.astype(np.float32).reshape(1, 1, TAMANO, TAMANO)
            if self._entrada is None:
                self._entrada = self._sesion.get_inputs()[0].name
            logits = np.asarray(
                self._sesion.run(None, {self._entrada: entrada})[0]).reshape(-1)
            if logits.size != len(ETIQUETAS):
                return None
            exp = np.exp(logits - logits.max())
            prob = exp / exp.sum()
            orden = np.argsort(-prob, kind='stable')[:CANTIDAD_TOP]  # de mayor a menor
            top = tuple((ETIQUETAS[j], float(prob[j])) for j in orden)
            i = int(orden[0])
            return Estimacion(ETIQUETAS[i], float(prob[i]), top)
        except Exception:
            logger.exception('Falló la estimación de emoción')
            return None

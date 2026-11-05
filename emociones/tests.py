from unittest.mock import MagicMock, patch

import numpy as np
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .camera import Camara, camara, generar_mjpeg


def captura_falsa(abierta=True):
    """Simula cv2.VideoCapture sin necesitar una cámara real."""
    falsa = MagicMock()
    falsa.isOpened.return_value = abierta
    falsa.read.return_value = (True, np.zeros((48, 64, 3), dtype=np.uint8))
    return falsa


class InicioTests(TestCase):
    def setUp(self):
        camara.detener()

    def test_pagina_inicio_responde(self):
        respuesta = self.client.get(reverse('emociones:inicio'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'EmotionVision Web')
        self.assertContains(respuesta, 'Iniciar cámara')
        self.assertContains(respuesta, 'Detener cámara')
        self.assertContains(respuesta, 'estimaciones')

    def test_abrir_pagina_no_enciende_la_camara(self):
        with patch('emociones.camera.cv2.VideoCapture') as vc:
            self.client.get(reverse('emociones:inicio'))
            vc.assert_not_called()
        self.assertFalse(camara.activa)


class VistasCamaraTests(TestCase):
    def setUp(self):
        camara.detener()
        self.addCleanup(camara.detener)

    def test_iniciar_sin_camara_muestra_mensaje_claro(self):
        with patch('emociones.camera.cv2.VideoCapture',
                   return_value=captura_falsa(abierta=False)):
            respuesta = self.client.post(reverse('emociones:iniciar_camara'))
        self.assertEqual(respuesta.status_code, 503)
        self.assertFalse(respuesta.json()['ok'])
        self.assertIn('No se encontró una cámara', respuesta.json()['mensaje'])

    def test_iniciar_y_detener_con_camara_falsa(self):
        falsa = captura_falsa()
        with patch('emociones.camera.cv2.VideoCapture', return_value=falsa):
            r1 = self.client.post(reverse('emociones:iniciar_camara'))
            self.assertTrue(r1.json()['ok'])
            self.assertTrue(camara.activa)
            r2 = self.client.post(reverse('emociones:detener_camara'))
        self.assertTrue(r2.json()['ok'])
        self.assertFalse(camara.activa)
        falsa.release.assert_called()

    def test_video_sin_iniciar_no_transmite(self):
        respuesta = self.client.get(reverse('emociones:video'))
        self.assertEqual(respuesta.status_code, 409)

    def test_iniciar_y_detener_solo_aceptan_post(self):
        self.assertEqual(self.client.get(reverse('emociones:iniciar_camara')).status_code, 405)
        self.assertEqual(self.client.get(reverse('emociones:detener_camara')).status_code, 405)


class CamaraTests(SimpleTestCase):
    def test_entrega_jpeg_y_libera_al_detener(self):
        falsa = captura_falsa()
        cam = Camara()
        with patch('emociones.camera.cv2.VideoCapture', return_value=falsa):
            self.assertTrue(cam.iniciar())
        jpeg = cam.leer_jpeg()
        self.assertTrue(jpeg.startswith(b'\xff\xd8'))  # cabecera JPEG
        cam.detener()
        self.assertFalse(cam.activa)
        falsa.release.assert_called_once()
        self.assertIsNone(cam.leer_jpeg())

    def test_flujo_mjpeg_libera_camara_al_cerrarse(self):
        falsa = captura_falsa()
        cam = Camara()
        with patch('emociones.camera.cv2.VideoCapture', return_value=falsa):
            cam.iniciar()
        flujo = generar_mjpeg(cam)
        self.assertIn(b'Content-Type: image/jpeg', next(flujo))
        flujo.close()  # el navegador cortó la conexión
        self.assertFalse(cam.activa)

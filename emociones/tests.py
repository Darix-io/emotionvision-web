from unittest.mock import MagicMock, patch

import numpy as np
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .camera import Camara, camara, generar_mjpeg
from .detector import TEXTO_SIN_ROSTRO, DetectorRostros
from .emociones import ETIQUETAS, Estimacion, EstimadorEmociones


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

    def test_pagina_tiene_aviso_de_privacidad_estado_y_panel(self):
        html = self.client.get(reverse('emociones:inicio')).content.decode()
        self.assertIn('No se guarda video ni imágenes', html)
        self.assertIn('Cámara apagada', html)
        self.assertIn('Emoción estimada', html)
        self.assertIn('no un diagnóstico', html)
        self.assertIn('Aceptar y encender', html)

    def test_archivos_estaticos_existen(self):
        for ruta in ('emociones/css/estilos.css', 'emociones/js/app.js'):
            self.assertIsNotNone(finders.find(ruta), ruta)

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


class DetectorTests(SimpleTestCase):
    def setUp(self):
        self.detector = DetectorRostros()

    def test_imagen_en_blanco_no_tiene_rostros(self):
        blanco = np.full((240, 320, 3), 255, dtype=np.uint8)
        self.assertEqual(self.detector.detectar(blanco), [])

    def test_imagen_vacia_o_nula_no_falla(self):
        self.assertEqual(self.detector.detectar(None), [])
        self.assertEqual(self.detector.detectar(np.zeros((0, 0, 3), dtype=np.uint8)), [])

    def test_sin_rostro_dibuja_texto_y_no_falla(self):
        negro = np.zeros((240, 320, 3), dtype=np.uint8)
        rostros = self.detector.procesar(negro)
        self.assertEqual(rostros, [])
        self.assertTrue(negro.any(), f'Debe dibujarse "{TEXTO_SIN_ROSTRO}"')

    def test_con_rostro_dibuja_rectangulo_sin_texto(self):
        negro = np.zeros((240, 320, 3), dtype=np.uint8)
        self.detector.dibujar(negro, [(50, 50, 100, 100)])
        self.assertTrue(negro[50, 50:150].any())  # borde superior del rectángulo
        self.assertFalse(negro[220:, :].any())  # no aparece el texto "sin rostro"

    def test_camara_entrega_jpeg_con_detector_integrado(self):
        falsa = captura_falsa()
        cam = Camara()
        with patch('emociones.camera.cv2.VideoCapture', return_value=falsa):
            cam.iniciar()
        self.assertTrue(cam.leer_jpeg().startswith(b'\xff\xd8'))
        cam.detener()


def sesion_falsa(indice_ganador=1):
    """Simula una sesión de onnxruntime: devuelve 8 valores, uno claramente mayor."""
    logits = np.zeros((1, 8), dtype=np.float32)
    logits[0, indice_ganador] = 5.0
    sesion = MagicMock()
    entrada = MagicMock()
    entrada.name = 'Input3'
    sesion.get_inputs.return_value = [entrada]
    sesion.run.return_value = [logits]
    return sesion


class EstimadorEmocionesTests(SimpleTestCase):
    def test_devuelve_emocion_en_espanol_y_confianza(self):
        sesion = sesion_falsa(indice_ganador=1)
        estimador = EstimadorEmociones(sesion=sesion)
        resultado = estimador.estimar(np.full((80, 70), 128, dtype=np.uint8))
        self.assertEqual(resultado.emocion, 'feliz')
        self.assertGreater(resultado.confianza, 0.9)
        self.assertLessEqual(resultado.confianza, 1.0)
        self.assertRegex(resultado.texto, r'^Feliz \d+%$')

    def test_el_recorte_se_ajusta_a_64x64(self):
        sesion = sesion_falsa()
        EstimadorEmociones(sesion=sesion).estimar(np.zeros((90, 50), dtype=np.uint8))
        entrada = sesion.run.call_args[0][1]['Input3']
        self.assertEqual(entrada.shape, (1, 1, 64, 64))
        self.assertEqual(entrada.dtype, np.float32)

    def test_las_8_etiquetas_en_espanol(self):
        self.assertEqual(ETIQUETAS, ('neutral', 'feliz', 'sorpresa', 'tristeza',
                                     'enojo', 'asco', 'miedo', 'desprecio'))

    def test_modelo_inexistente_no_falla(self):
        estimador = EstimadorEmociones(ruta_modelo='no_existe/modelo.onnx')
        self.assertFalse(estimador.disponible)
        self.assertIsNone(estimador.estimar(np.zeros((64, 64), dtype=np.uint8)))

    def test_modelo_que_falla_devuelve_none(self):
        sesion = sesion_falsa()
        sesion.run.side_effect = RuntimeError('fallo simulado')
        estimador = EstimadorEmociones(sesion=sesion)
        with self.assertLogs('emociones.emociones', level='ERROR'):
            self.assertIsNone(estimador.estimar(np.zeros((64, 64), dtype=np.uint8)))

    def test_recorte_vacio_devuelve_none(self):
        estimador = EstimadorEmociones(sesion=sesion_falsa())
        self.assertIsNone(estimador.estimar(np.zeros((0, 0), dtype=np.uint8)))


class IntegracionEtiquetasTests(SimpleTestCase):
    def _camara_con_rostro(self, estimador):
        falsa = captura_falsa()
        cam = Camara(estimador=estimador)
        with patch('emociones.camera.cv2.VideoCapture', return_value=falsa):
            cam.iniciar()
        return cam

    def test_se_estima_cada_rostro_y_se_entrega_jpeg(self):
        estimador = MagicMock()
        estimador.estimar.return_value = Estimacion('feliz', 0.82)
        cam = self._camara_con_rostro(estimador)
        with patch.object(cam.detector, 'detectar', return_value=[(10, 10, 30, 30)]):
            jpeg = cam.leer_jpeg()
        self.assertTrue(jpeg.startswith(b'\xff\xd8'))
        recorte = estimador.estimar.call_args[0][0]
        self.assertEqual(recorte.shape, (30, 30))  # recorte gris del rostro
        cam.detener()

    def test_sin_modelo_el_video_sigue_con_recuadros(self):
        estimador = EstimadorEmociones(ruta_modelo='no_existe/modelo.onnx')
        cam = self._camara_con_rostro(estimador)
        with patch.object(cam.detector, 'detectar', return_value=[(10, 10, 30, 30)]):
            jpeg = cam.leer_jpeg()
        self.assertTrue(jpeg.startswith(b'\xff\xd8'))
        cam.detener()

    def test_etiqueta_se_dibuja_sobre_el_recuadro(self):
        detector = DetectorRostros()
        sin_etiqueta = np.zeros((120, 160, 3), dtype=np.uint8)
        con_etiqueta = sin_etiqueta.copy()
        detector.dibujar(sin_etiqueta, [(40, 50, 60, 60)])
        detector.dibujar(con_etiqueta, [(40, 50, 60, 60)], ['Feliz 82%'])
        self.assertFalse(np.array_equal(sin_etiqueta[30:50], con_etiqueta[30:50]))


class EstadoPanelTests(TestCase):
    def setUp(self):
        camara.detener()
        self.addCleanup(camara.detener)

    def test_estado_con_camara_apagada(self):
        datos = self.client.get(reverse('emociones:estado')).json()
        self.assertEqual(datos, {'activa': False, 'rostros': 0,
                                 'emocion': None, 'confianza': None})

    def test_estado_solo_acepta_get(self):
        self.assertEqual(self.client.post(reverse('emociones:estado')).status_code, 405)

    def test_estado_sin_rostro(self):
        with patch('emociones.camera.cv2.VideoCapture', return_value=captura_falsa()):
            camara.iniciar()
        camara.leer_jpeg()  # fotograma negro: no hay rostros
        datos = self.client.get(reverse('emociones:estado')).json()
        self.assertTrue(datos['activa'])
        self.assertEqual(datos['rostros'], 0)
        self.assertIsNone(datos['emocion'])

    def test_estado_con_rostro_y_emocion(self):
        estimador = MagicMock()
        estimador.estimar.return_value = Estimacion('feliz', 0.82)
        cam = Camara(estimador=estimador)
        with patch('emociones.camera.cv2.VideoCapture', return_value=captura_falsa()):
            cam.iniciar()
        with patch.object(cam.detector, 'detectar', return_value=[(10, 10, 30, 30)]):
            cam.leer_jpeg()
        self.assertEqual(cam.estado(), {'activa': True, 'rostros': 1,
                                        'emocion': 'feliz', 'confianza': 82})
        cam.detener()
        self.assertFalse(cam.estado()['activa'])
        self.assertIsNone(cam.estado()['emocion'])

    def test_con_varios_rostros_se_usa_el_mas_grande(self):
        estimador = MagicMock()
        estimador.estimar.side_effect = [Estimacion('triste', 0.6), Estimacion('feliz', 0.9)]
        cam = Camara(estimador=estimador)
        with patch('emociones.camera.cv2.VideoCapture', return_value=captura_falsa()):
            cam.iniciar()
        rostros = [(0, 0, 10, 10), (20, 5, 40, 40)]
        with patch.object(cam.detector, 'detectar', return_value=rostros):
            cam.leer_jpeg()
        self.assertEqual(cam.estado()['emocion'], 'feliz')
        cam.detener()

    def test_modelo_ausente_reporta_rostro_sin_emocion(self):
        cam = Camara(estimador=EstimadorEmociones(ruta_modelo='no_existe/m.onnx'))
        with patch('emociones.camera.cv2.VideoCapture', return_value=captura_falsa()):
            cam.iniciar()
        with patch.object(cam.detector, 'detectar', return_value=[(10, 10, 30, 30)]):
            cam.leer_jpeg()
        datos = cam.estado()
        self.assertEqual(datos['rostros'], 1)
        self.assertIsNone(datos['emocion'])
        cam.detener()


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

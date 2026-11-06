import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
from django.contrib.staticfiles import finders
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .camera import Camara, camara, generar_mjpeg
from .detector import TEXTO_SIN_ROSTRO, DetectorRostros
from .emociones import ETIQUETAS, Estimacion, EstimadorEmociones, porcentajes_enteros
from .models import RegistroEmocion
from .registro import RegistradorEmociones, borrar_registros, estadisticas


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

    def test_interfaz_sin_recursos_externos(self):
        """La interfaz no carga fuentes, íconos ni scripts de internet."""
        contenidos = [self.client.get(reverse('emociones:inicio')).content.decode()]
        for ruta in ('emociones/css/estilos.css', 'emociones/js/app.js'):
            contenidos.append(Path(finders.find(ruta)).read_text(encoding='utf-8'))
        for texto in contenidos:
            self.assertNotIn('http://', texto)
            self.assertNotIn('https://', texto)
            self.assertNotIn('@import', texto)

    def test_interfaz_tiene_elementos_de_accesibilidad(self):
        html = self.client.get(reverse('emociones:inicio')).content.decode()
        self.assertIn('Saltar al contenido', html)
        self.assertIn('role="progressbar"', html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn('<main', html)
        self.assertIn('lang="es"', html)
        css = Path(finders.find('emociones/css/estilos.css')).read_text(encoding='utf-8')
        self.assertIn(':focus-visible', css)
        self.assertIn('prefers-reduced-motion', css)

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
        cam = Camara(estimador=estimador, registrador=MagicMock())
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
                                 'emocion': None, 'confianza': None, 'top3': []})

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
        self.assertEqual(cam.estado(), {'activa': True, 'rostros': 1, 'emocion': 'feliz',
                                        'confianza': 82, 'top3': []})  # el simulado no trae top
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


class RelojFalso:
    """Reloj controlable para probar el límite de 1 registro cada 2 segundos."""

    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class ModeloRegistroTests(SimpleTestCase):
    def test_solo_guarda_datos_minimos(self):
        campos = {c.name for c in RegistroEmocion._meta.get_fields()}
        self.assertEqual(campos, {'id', 'fecha_hora', 'emocion', 'confianza'})


class RegistradorTests(TestCase):
    def setUp(self):
        self.reloj = RelojFalso()
        self.reg = RegistradorEmociones(reloj=self.reloj)
        self.feliz = Estimacion('feliz', 0.82)

    def test_guarda_un_registro(self):
        self.assertTrue(self.reg.registrar(self.feliz))
        r = RegistroEmocion.objects.get()
        self.assertEqual(r.emocion, 'feliz')
        self.assertAlmostEqual(r.confianza, 0.82)

    def test_maximo_uno_cada_2_segundos(self):
        self.assertTrue(self.reg.registrar(self.feliz))
        self.reloj.t += 1.9
        self.assertFalse(self.reg.registrar(self.feliz))
        self.reloj.t += 0.2  # ya pasaron 2.1 s
        self.assertTrue(self.reg.registrar(self.feliz))
        self.assertEqual(RegistroEmocion.objects.count(), 2)

    def test_sin_estimacion_no_guarda(self):
        self.assertFalse(self.reg.registrar(None))
        self.assertEqual(RegistroEmocion.objects.count(), 0)

    def test_si_la_base_falla_no_lanza_error_y_espera_antes_de_reintentar(self):
        with patch.object(RegistroEmocion.objects, 'create',
                          side_effect=OperationalError('base caída')) as crear:
            with self.assertLogs('emociones.registro', level='ERROR'):
                self.assertFalse(self.reg.registrar(self.feliz))
            self.reloj.t += 5
            self.assertFalse(self.reg.registrar(self.feliz))
            self.assertEqual(crear.call_count, 1)  # no insiste en cada fotograma


class RegistroDesdeCamaraTests(TestCase):
    def setUp(self):
        self.reloj = RelojFalso()
        estimador = MagicMock()
        estimador.estimar.return_value = Estimacion('sorpresa', 0.7)
        self.cam = Camara(estimador=estimador,
                          registrador=RegistradorEmociones(reloj=self.reloj))
        with patch('emociones.camera.cv2.VideoCapture', return_value=captura_falsa()):
            self.cam.iniciar()
        self.addCleanup(self.cam.detener)

    def _leer(self, rostros):
        with patch.object(self.cam.detector, 'detectar', return_value=rostros):
            return self.cam.leer_jpeg()

    def test_con_rostro_se_guarda_pero_no_en_cada_fotograma(self):
        for _ in range(5):
            self._leer([(10, 10, 30, 30)])
        self.assertEqual(RegistroEmocion.objects.count(), 1)
        self.reloj.t += 2.5
        self._leer([(10, 10, 30, 30)])
        self.assertEqual(RegistroEmocion.objects.count(), 2)

    def test_sin_rostro_no_se_guarda(self):
        self._leer([])
        self.assertEqual(RegistroEmocion.objects.count(), 0)

    def test_con_camara_apagada_no_se_guarda(self):
        self.cam.detener()
        self.assertIsNone(self.cam.leer_jpeg())
        self.assertEqual(RegistroEmocion.objects.count(), 0)

    def test_si_la_base_falla_el_video_sigue(self):
        with patch.object(RegistroEmocion.objects, 'create',
                          side_effect=OperationalError('base caída')):
            with self.assertLogs('emociones.registro', level='ERROR'):
                jpeg = self._leer([(10, 10, 30, 30)])
        self.assertTrue(jpeg.startswith(b'\xff\xd8'))


class VistasRegistrosTests(TestCase):
    def test_estadisticas_vacias(self):
        datos = self.client.get(reverse('emociones:estadisticas')).json()
        self.assertEqual(datos, {'disponible': True, 'total': 0,
                                 'por_emocion': [], 'ultimos': []})

    def test_estadisticas_total_por_emocion_y_ultimos_10(self):
        for i in range(12):
            RegistroEmocion.objects.create(emocion='feliz' if i < 8 else 'enojo',
                                           confianza=0.5)
        datos = self.client.get(reverse('emociones:estadisticas')).json()
        self.assertEqual(datos['total'], 12)
        self.assertEqual(datos['por_emocion'],
                         [{'emocion': 'feliz', 'cantidad': 8},
                          {'emocion': 'enojo', 'cantidad': 4}])
        self.assertEqual(len(datos['ultimos']), 10)
        self.assertEqual(datos['ultimos'][0]['emocion'], 'enojo')  # el más reciente primero
        self.assertEqual(datos['ultimos'][0]['confianza'], 50)

    def test_estadisticas_si_la_base_falla(self):
        with patch.object(RegistroEmocion.objects, 'values',
                          side_effect=OperationalError('base caída')):
            with self.assertLogs('emociones.registro', level='ERROR'):
                respuesta = self.client.get(reverse('emociones:estadisticas'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.json()['disponible'])

    def test_borrar_elimina_todo(self):
        RegistroEmocion.objects.create(emocion='feliz', confianza=0.9)
        RegistroEmocion.objects.create(emocion='miedo', confianza=0.4)
        respuesta = self.client.post(reverse('emociones:borrar_registros'))
        self.assertEqual(respuesta.json(), {'ok': True, 'borrados': 2})
        self.assertEqual(RegistroEmocion.objects.count(), 0)

    def test_borrar_solo_acepta_post(self):
        self.assertEqual(self.client.get(reverse('emociones:borrar_registros')).status_code, 405)

    def test_borrar_si_la_base_falla(self):
        with patch.object(RegistroEmocion.objects, 'all',
                          side_effect=OperationalError('base caída')):
            with self.assertLogs('emociones.registro', level='ERROR'):
                respuesta = self.client.post(reverse('emociones:borrar_registros'))
        self.assertEqual(respuesta.status_code, 500)
        self.assertFalse(respuesta.json()['ok'])

    def test_pagina_tiene_seccion_de_estadisticas_y_avisos(self):
        html = self.client.get(reverse('emociones:inicio')).content.decode()
        self.assertIn('Borrar registros', html)
        self.assertIn('Últimos 10 registros', html)
        self.assertIn('No se guarda video ni imágenes', html)
        self.assertIn('no un diagnóstico', html)


class DetectorCasosBordeTests(SimpleTestCase):
    def setUp(self):
        self.detector = DetectorRostros()

    def test_si_no_carga_el_clasificador_lanza_error_claro(self):
        vacio = MagicMock()
        vacio.empty.return_value = True
        with patch('emociones.detector.cv2.CascadeClassifier', return_value=vacio):
            with self.assertRaisesMessage(RuntimeError, 'No se pudo cargar el clasificador'):
                DetectorRostros()

    def test_detectar_devuelve_tuplas_de_enteros(self):
        crudo = np.array([[1, 2, 60, 70]], dtype=np.int32)
        self.detector._clasificador = MagicMock()  # el de OpenCV no se puede parchear
        self.detector._clasificador.detectMultiScale.return_value = crudo
        rostros = self.detector.detectar(np.zeros((100, 100, 3), dtype=np.uint8))
        self.assertEqual(rostros, [(1, 2, 60, 70)])
        self.assertTrue(all(type(v) is int for v in rostros[0]))

    def test_etiqueta_en_el_borde_no_falla_y_queda_dentro_de_la_imagen(self):
        imagen = np.zeros((120, 160, 3), dtype=np.uint8)
        self.detector.dibujar(imagen, [(150, 0, 10, 10)], ['Desprecio 100%'])
        self.assertTrue(imagen.any())
        self.assertEqual(imagen.shape, (120, 160, 3))

    def test_menos_etiquetas_que_rostros(self):
        imagen = np.zeros((120, 160, 3), dtype=np.uint8)
        self.detector.dibujar(imagen, [(10, 40, 30, 30), (90, 40, 30, 30)], ['Feliz 80%'])
        self.assertTrue(imagen[40, 10:40].any())
        self.assertTrue(imagen[40, 90:120].any())  # ambos recuadros se dibujan

    def test_con_rostros_no_aparece_el_texto_sin_rostro(self):
        con_rostro = np.zeros((120, 160, 3), dtype=np.uint8)
        self.detector.dibujar(con_rostro, [(10, 10, 30, 30)])
        self.assertFalse(con_rostro[100:, :].any())

    def test_procesar_devuelve_la_lista_de_rostros(self):
        with patch.object(self.detector, 'detectar', return_value=[(5, 5, 20, 20)]):
            imagen = np.zeros((60, 60, 3), dtype=np.uint8)
            self.assertEqual(self.detector.procesar(imagen), [(5, 5, 20, 20)])
        self.assertTrue(imagen.any())


class EstimadorCasosBordeTests(SimpleTestCase):
    def test_texto_redondea_el_porcentaje(self):
        self.assertEqual(Estimacion('miedo', 0.456).texto, 'Miedo 46%')
        self.assertEqual(Estimacion('neutral', 1.0).texto, 'Neutral 100%')

    def test_la_confianza_es_una_probabilidad(self):
        sesion = sesion_falsa()
        sesion.run.return_value = [np.zeros((1, 8), dtype=np.float32)]  # todos iguales
        resultado = EstimadorEmociones(sesion=sesion).estimar(np.zeros((64, 64), dtype=np.uint8))
        self.assertAlmostEqual(resultado.confianza, 1 / 8, places=5)

    def test_salida_de_tamano_incorrecto_devuelve_none(self):
        sesion = sesion_falsa()
        sesion.run.return_value = [np.zeros((1, 3), dtype=np.float32)]
        self.assertIsNone(
            EstimadorEmociones(sesion=sesion).estimar(np.zeros((64, 64), dtype=np.uint8)))

    def test_no_modifica_el_recorte_recibido(self):
        recorte = np.full((80, 80), 100, dtype=np.uint8)
        copia = recorte.copy()
        EstimadorEmociones(sesion=sesion_falsa()).estimar(recorte)
        self.assertTrue(np.array_equal(recorte, copia))

    def test_archivo_que_no_es_un_modelo_deja_el_estimador_desactivado(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / 'falso.onnx'
            ruta.write_bytes(b'esto no es un modelo onnx')
            estimador = EstimadorEmociones(ruta_modelo=ruta)
            with self.assertLogs('emociones.emociones', level='ERROR'):
                self.assertFalse(estimador.disponible)
            self.assertIsNone(estimador.estimar(np.zeros((64, 64), dtype=np.uint8)))

    def test_el_modelo_se_carga_una_sola_vez(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / 'modelo.onnx'
            ruta.write_bytes(b'x')
            with patch('onnxruntime.InferenceSession', return_value=sesion_falsa()) as cargar:
                estimador = EstimadorEmociones(ruta_modelo=ruta)
                for _ in range(3):
                    estimador.estimar(np.zeros((64, 64), dtype=np.uint8))
                self.assertEqual(cargar.call_count, 1)

    def test_si_la_carga_falla_no_se_reintenta_en_cada_fotograma(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / 'modelo.onnx'
            ruta.write_bytes(b'x')
            with patch('onnxruntime.InferenceSession',
                       side_effect=RuntimeError('fallo')) as cargar:
                estimador = EstimadorEmociones(ruta_modelo=ruta)
                with self.assertLogs('emociones.emociones', level='ERROR'):
                    estimador.estimar(np.zeros((64, 64), dtype=np.uint8))
                estimador.estimar(np.zeros((64, 64), dtype=np.uint8))
                self.assertEqual(cargar.call_count, 1)


class CamaraCasosBordeTests(SimpleTestCase):
    def _camara(self, falsa=None):
        cam = Camara(registrador=MagicMock())
        falsa = falsa or captura_falsa()
        with patch('emociones.camera.cv2.VideoCapture', return_value=falsa) as vc:
            cam.iniciar()
        return cam, falsa, vc

    def test_iniciar_dos_veces_no_vuelve_a_abrir_la_camara(self):
        cam, _, vc = self._camara()
        with patch('emociones.camera.cv2.VideoCapture') as otra:
            self.assertTrue(cam.iniciar())
            otra.assert_not_called()
        self.assertEqual(vc.call_count, 1)
        cam.detener()

    def test_sin_camara_libera_el_recurso_y_queda_apagada(self):
        falsa = captura_falsa(abierta=False)
        cam, _, _ = self._camara(falsa)
        self.assertFalse(cam.activa)
        falsa.release.assert_called_once()

    def test_si_falla_la_lectura_devuelve_none(self):
        falsa = captura_falsa()
        falsa.read.return_value = (False, None)
        cam, _, _ = self._camara(falsa)
        self.assertIsNone(cam.leer_jpeg())
        cam.detener()

    def test_error_del_detector_no_rompe_el_video(self):
        cam, _, _ = self._camara()
        with patch.object(cam.detector, 'detectar', side_effect=cv2.error('fallo simulado')):
            jpeg = cam.leer_jpeg()
        self.assertTrue(jpeg.startswith(b'\xff\xd8'))
        self.assertEqual(cam.estado()['rostros'], 0)
        cam.detener()

    def test_estado_apagada(self):
        self.assertEqual(Camara(registrador=MagicMock()).estado(),
                         {'activa': False, 'rostros': 0, 'emocion': None,
                          'confianza': None, 'top3': []})

    def test_flujo_sin_camara_encendida_no_entrega_nada(self):
        cam = Camara(registrador=MagicMock())
        self.assertEqual(list(generar_mjpeg(cam)), [])

    def test_flujo_termina_y_libera_si_falla_la_lectura(self):
        falsa = captura_falsa()
        cam, _, _ = self._camara(falsa)
        falsa.read.return_value = (False, None)
        self.assertEqual(list(generar_mjpeg(cam)), [])
        self.assertFalse(cam.activa)
        falsa.release.assert_called_once()

    def test_detener_dos_veces_no_falla(self):
        cam, falsa, _ = self._camara()
        cam.detener()
        cam.detener()
        falsa.release.assert_called_once()


class RegistroCasosBordeTests(TestCase):
    def test_reiniciar_permite_guardar_de_inmediato(self):
        reloj = RelojFalso()
        reg = RegistradorEmociones(reloj=reloj)
        self.assertTrue(reg.registrar(Estimacion('feliz', 0.8)))
        self.assertFalse(reg.registrar(Estimacion('feliz', 0.8)))
        reg.reiniciar()
        self.assertTrue(reg.registrar(Estimacion('feliz', 0.8)))

    def test_borrar_registros_devuelve_la_cantidad(self):
        self.assertEqual(borrar_registros(), 0)
        RegistroEmocion.objects.create(emocion='feliz', confianza=0.5)
        RegistroEmocion.objects.create(emocion='feliz', confianza=0.6)
        self.assertEqual(borrar_registros(), 2)
        self.assertEqual(RegistroEmocion.objects.count(), 0)

    def test_empate_en_estadisticas_se_ordena_por_nombre(self):
        RegistroEmocion.objects.create(emocion='miedo', confianza=0.5)
        RegistroEmocion.objects.create(emocion='asco', confianza=0.5)
        nombres = [e['emocion'] for e in estadisticas()['por_emocion']]
        self.assertEqual(nombres, ['asco', 'miedo'])

    def test_ultimos_registros_traen_fecha_hora_y_porcentaje(self):
        RegistroEmocion.objects.create(emocion='tristeza', confianza=0.734)
        ultimo = estadisticas()['ultimos'][0]
        self.assertEqual(set(ultimo), {'fecha', 'hora', 'emocion', 'confianza'})
        self.assertEqual(ultimo['confianza'], 73)
        self.assertRegex(ultimo['hora'], r'^\d{2}:\d{2}:\d{2}$')


class VistasCasosBordeTests(TestCase):
    def setUp(self):
        camara.detener()
        self.addCleanup(camara.detener)

    def test_iniciar_dos_veces_responde_ok(self):
        with patch('emociones.camera.cv2.VideoCapture', return_value=captura_falsa()):
            self.assertTrue(self.client.post(reverse('emociones:iniciar_camara')).json()['ok'])
            self.assertTrue(self.client.post(reverse('emociones:iniciar_camara')).json()['ok'])

    def test_detener_sin_haber_iniciado_responde_ok(self):
        respuesta = self.client.post(reverse('emociones:detener_camara'))
        self.assertTrue(respuesta.json()['ok'])

    def test_video_transmite_jpeg_y_libera_la_camara_al_cerrar(self):
        with patch('emociones.camera.cv2.VideoCapture', return_value=captura_falsa()):
            self.client.post(reverse('emociones:iniciar_camara'))
        respuesta = self.client.get(reverse('emociones:video'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta['Content-Type'].startswith('multipart/x-mixed-replace'))
        primer_trozo = next(iter(respuesta.streaming_content))
        self.assertIn(b'Content-Type: image/jpeg', primer_trozo)
        respuesta.close()  # el navegador cortó la conexión
        self.assertFalse(camara.activa)

    def test_video_sin_iniciar_devuelve_mensaje(self):
        datos = self.client.get(reverse('emociones:video')).json()
        self.assertFalse(datos['ok'])
        self.assertIn('no está iniciada', datos['mensaje'])


def sesion_con_logits(logits):
    """Sesión simulada que devuelve los logits indicados (8 valores)."""
    sesion = sesion_falsa()
    sesion.run.return_value = [np.array([logits], dtype=np.float32)]
    return sesion


RECORTE = np.full((64, 64), 120, dtype=np.uint8)


class Top3EstimadorTests(SimpleTestCase):
    def test_top3_ordenado_de_mayor_a_menor(self):
        # feliz (1) > sorpresa (2) > enojo (4)
        sesion = sesion_con_logits([0.1, 3.0, 2.0, 0.0, 1.0, -1.0, -2.0, -3.0])
        resultado = EstimadorEmociones(sesion=sesion).estimar(RECORTE)
        self.assertEqual([e for e, _ in resultado.top], ['feliz', 'sorpresa', 'enojo'])
        probabilidades = [p for _, p in resultado.top]
        self.assertEqual(probabilidades, sorted(probabilidades, reverse=True))
        self.assertEqual(len(resultado.top), 3)

    def test_lo_anterior_no_cambia(self):
        sesion = sesion_con_logits([0.1, 3.0, 2.0, 0.0, 1.0, -1.0, -2.0, -3.0])
        resultado = EstimadorEmociones(sesion=sesion).estimar(RECORTE)
        self.assertEqual(resultado.emocion, 'feliz')
        self.assertEqual(resultado.confianza, resultado.top[0][1])
        self.assertRegex(resultado.texto, r'^Feliz \d+%$')

    def test_top3_en_porcentajes_enteros_y_en_espanol(self):
        sesion = sesion_con_logits([0.1, 3.0, 2.0, 0.0, 1.0, -1.0, -2.0, -3.0])
        top3 = EstimadorEmociones(sesion=sesion).estimar(RECORTE).top3
        self.assertEqual(len(top3), 3)
        self.assertTrue(all(t['emocion'] in ETIQUETAS for t in top3))
        self.assertTrue(all(type(t['porcentaje']) is int for t in top3))
        porcentajes = [t['porcentaje'] for t in top3]
        self.assertEqual(porcentajes, sorted(porcentajes, reverse=True))

    def test_el_primero_coincide_con_el_texto_principal(self):
        sesion = sesion_con_logits([0.1, 3.0, 2.0, 0.0, 1.0, -1.0, -2.0, -3.0])
        resultado = EstimadorEmociones(sesion=sesion).estimar(RECORTE)
        self.assertEqual(resultado.texto, f"Feliz {resultado.top3[0]['porcentaje']}%")

    def test_la_suma_nunca_pasa_de_100_con_muchos_casos(self):
        azar = np.random.default_rng(7)
        for _ in range(300):
            logits = list(azar.normal(0, azar.choice([0.1, 1, 5, 20]), 8))
            resultado = EstimadorEmociones(sesion=sesion_con_logits(logits)).estimar(RECORTE)
            porcentajes = [t['porcentaje'] for t in resultado.top3]
            self.assertLessEqual(sum(porcentajes), 100, porcentajes)
            self.assertTrue(all(0 <= p <= 100 for p in porcentajes))
            self.assertEqual(porcentajes, sorted(porcentajes, reverse=True))

    def test_casos_limite_de_redondeo(self):
        self.assertEqual(porcentajes_enteros([0.996, 0.0039, 0.0001]), [100, 0, 0])
        self.assertEqual(porcentajes_enteros([0.5, 0.3, 0.2]), [50, 30, 20])
        self.assertEqual(porcentajes_enteros([0.995, 0.004, 0.001]), [100, 0, 0])
        self.assertLessEqual(sum(porcentajes_enteros([1 / 3, 1 / 3, 1 / 3])), 100)
        self.assertEqual(porcentajes_enteros([]), [])

    def test_probabilidades_iguales_dan_tres_resultados(self):
        sesion = sesion_con_logits([0] * 8)
        resultado = EstimadorEmociones(sesion=sesion).estimar(RECORTE)
        self.assertEqual(len(resultado.top3), 3)
        self.assertLessEqual(sum(t['porcentaje'] for t in resultado.top3), 100)

    def test_estimacion_sin_top_da_lista_vacia(self):
        self.assertEqual(Estimacion('feliz', 0.8).top3, [])

    def test_sin_modelo_no_hay_estimacion_ni_top(self):
        estimador = EstimadorEmociones(ruta_modelo='no_existe/modelo.onnx')
        self.assertIsNone(estimador.estimar(RECORTE))


class Top3EnCamaraTests(TestCase):
    TOP = (('feliz', 0.60), ('sorpresa', 0.30), ('neutral', 0.05))

    def _camara(self, estimador, registrador=None):
        cam = Camara(estimador=estimador, registrador=registrador or MagicMock())
        with patch('emociones.camera.cv2.VideoCapture', return_value=captura_falsa()):
            cam.iniciar()
        self.addCleanup(cam.detener)
        return cam

    def _leer(self, cam, rostros):
        with patch.object(cam.detector, 'detectar', return_value=rostros):
            cam.leer_jpeg()

    def test_estado_incluye_el_top3_del_rostro(self):
        estimador = MagicMock()
        estimador.estimar.return_value = Estimacion('feliz', 0.60, self.TOP)
        cam = self._camara(estimador)
        self._leer(cam, [(10, 10, 30, 30)])
        self.assertEqual(cam.estado()['top3'], [
            {'emocion': 'feliz', 'porcentaje': 60},
            {'emocion': 'sorpresa', 'porcentaje': 30},
            {'emocion': 'neutral', 'porcentaje': 5},
        ])

    def test_con_varios_rostros_el_top3_es_del_mas_grande(self):
        chico = Estimacion('triste', 0.9, (('tristeza', 0.9), ('miedo', 0.05), ('asco', 0.02)))
        grande = Estimacion('feliz', 0.60, self.TOP)
        estimador = MagicMock()
        estimador.estimar.side_effect = [chico, grande]
        cam = self._camara(estimador)
        self._leer(cam, [(0, 0, 10, 10), (20, 5, 40, 40)])
        self.assertEqual(cam.estado()['top3'][0]['emocion'], 'feliz')

    def test_sin_rostro_el_top3_va_vacio(self):
        cam = self._camara(MagicMock())
        self._leer(cam, [])
        self.assertEqual(cam.estado()['top3'], [])
        self.assertEqual(cam.estado()['rostros'], 0)

    def test_sin_modelo_el_top3_va_vacio_y_el_video_sigue(self):
        cam = self._camara(EstimadorEmociones(ruta_modelo='no_existe/modelo.onnx'))
        with patch.object(cam.detector, 'detectar', return_value=[(10, 10, 30, 30)]):
            jpeg = cam.leer_jpeg()
        self.assertTrue(jpeg.startswith(b'\xff\xd8'))
        datos = cam.estado()
        self.assertEqual(datos['rostros'], 1)
        self.assertEqual(datos['top3'], [])
        self.assertIsNone(datos['emocion'])

    def test_al_detener_el_top3_se_borra(self):
        estimador = MagicMock()
        estimador.estimar.return_value = Estimacion('feliz', 0.60, self.TOP)
        cam = self._camara(estimador)
        self._leer(cam, [(10, 10, 30, 30)])
        cam.detener()
        self.assertEqual(cam.estado()['top3'], [])

    def test_el_estado_devuelve_una_copia_del_top3(self):
        estimador = MagicMock()
        estimador.estimar.return_value = Estimacion('feliz', 0.60, self.TOP)
        cam = self._camara(estimador)
        self._leer(cam, [(10, 10, 30, 30)])
        cam.estado()['top3'].clear()
        self.assertEqual(len(cam.estado()['top3']), 3)

    def test_el_registro_sigue_guardando_solo_lo_minimo(self):
        estimador = MagicMock()
        estimador.estimar.return_value = Estimacion('feliz', 0.60, self.TOP)
        cam = self._camara(estimador, registrador=RegistradorEmociones())
        self._leer(cam, [(10, 10, 30, 30)])
        registro = RegistroEmocion.objects.get()
        self.assertEqual((registro.emocion, registro.confianza), ('feliz', 0.60))
        campos = {c.name for c in RegistroEmocion._meta.get_fields()}
        self.assertEqual(campos, {'id', 'fecha_hora', 'emocion', 'confianza'})

    def test_el_registro_recibe_solo_emocion_y_confianza(self):
        estimador = MagicMock()
        estimador.estimar.return_value = Estimacion('feliz', 0.60, self.TOP)
        cam = self._camara(estimador, registrador=RegistradorEmociones())
        with patch.object(RegistroEmocion.objects, 'create') as crear:
            self._leer(cam, [(10, 10, 30, 30)])
        crear.assert_called_once_with(emocion='feliz', confianza=0.60)


class Top3RutaTests(TestCase):
    def setUp(self):
        camara.detener()
        self.addCleanup(camara.detener)

    def test_la_ruta_estado_incluye_top3_vacio_con_la_camara_apagada(self):
        datos = self.client.get(reverse('emociones:estado')).json()
        self.assertEqual(datos['top3'], [])

    def test_la_ruta_estado_entrega_el_top3_de_la_camara(self):
        top3 = [{'emocion': 'feliz', 'porcentaje': 60}, {'emocion': 'sorpresa', 'porcentaje': 30}]
        falso = {'activa': True, 'rostros': 1, 'emocion': 'feliz', 'confianza': 60, 'top3': top3}
        with patch.object(camara, 'estado', return_value=falso):
            datos = self.client.get(reverse('emociones:estado')).json()
        self.assertEqual(datos['top3'], top3)

    def test_la_pagina_tiene_el_panel_del_top3(self):
        html = self.client.get(reverse('emociones:inicio')).content.decode()
        self.assertIn('id="panel-top3"', html)
        self.assertIn('Las 3 más probables', html)
        self.assertIn('No se guarda video ni imágenes', html)
        self.assertIn('no un diagnóstico', html)


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

from django.test import TestCase
from django.urls import reverse


class InicioTests(TestCase):
    def test_pagina_inicio_responde(self):
        respuesta = self.client.get(reverse('emociones:inicio'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'EmotionVision Web')

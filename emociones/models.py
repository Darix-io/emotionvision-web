from django.db import models
from django.utils import timezone


class RegistroEmocion(models.Model):
    """Dato mínimo de una estimación. No guarda video, imágenes ni datos de la persona."""

    fecha_hora = models.DateTimeField(default=timezone.now, db_index=True)
    emocion = models.CharField(max_length=20)
    confianza = models.FloatField(help_text='Entre 0 y 1')

    class Meta:
        ordering = ['-fecha_hora', '-id']

    def __str__(self):
        return f'{self.emocion} {round(self.confianza * 100)}% ({self.fecha_hora:%Y-%m-%d %H:%M:%S})'

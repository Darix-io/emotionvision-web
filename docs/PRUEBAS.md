# Pruebas de EmotionVision Web

## 1. Casos de prueba manuales (CP-01 a CP-10)

La columna "Resultado observado" solo contiene lo que el estudiante confirmó con capturas
de pantalla. No se anotan detalles que no se hayan comprobado.

| Código | Prueba | Resultado esperado | Cómo se prueba | Resultado observado | Estado |
|---|---|---|---|---|---|
| CP-01 | Iniciar aplicación | Django funciona | Activar `.venv`, ejecutar `python manage.py runserver` y abrir http://127.0.0.1:8000/ | Django funciona (confirmado con captura) | Aprobado |
| CP-02 | Activar cámara | El video aparece | Pulsar "Iniciar cámara", aceptar el aviso de privacidad | El video aparece (confirmado con captura) | Aprobado |
| CP-03 | Mostrar un rostro | El rostro es detectado | Con la cámara encendida, ubicarse de frente con buena luz | El rostro es detectado (confirmado con captura) | Aprobado |
| CP-04 | Analizar una expresión | El modelo devuelve una estimación | Con el rostro detectado, hacer distintas expresiones | El modelo devuelve una estimación (confirmado con captura) | Aprobado |
| CP-05 | Mostrar resultado | La etiqueta aparece en el video | Observar la etiqueta sobre el recuadro del rostro y el panel "Emoción estimada" | La etiqueta aparece en el video (confirmado con captura) | Aprobado |
| CP-06 | No detectar rostro | El sistema continúa funcionando | Salir de la imagen o taparse con la cámara encendida | El sistema continúa funcionando sin rostro (confirmado con captura) | Aprobado |
| CP-07 | Detener cámara | La captura finaliza | Pulsar "Detener cámara" | La captura finaliza (confirmado con captura) | Aprobado |
| CP-08 | Conectar PostgreSQL | La aplicación accede a la base de datos | Configurar `.env`, ejecutar `python manage.py migrate` y abrir la página | La aplicación accede a la base de datos (confirmado con captura) | Aprobado |
| CP-09 | Registrar un resultado | El registro se guarda correctamente | Encender la cámara con un rostro y revisar la sección "Estadísticas" | El registro se guarda correctamente (confirmado con captura) | Aprobado |
| CP-10 | Instalar desde GitHub | Se configura siguiendo el README | Clonar el repositorio en otro equipo y seguir el README paso a paso | — | Pendiente (depende del README y de GitHub) |

## 2. Pruebas automáticas

Se ejecutan con:

```
python manage.py test
```

No necesitan cámara real ni el modelo descargado: usan una cámara y un modelo simulados.
Los archivos y rutas están en `emociones/tests.py`. Resultado de la última ejecución
(Fase 7): **75 pruebas, OK**. También se comprobó que pasan con el archivo del modelo
ausente.

| Módulo | Qué se comprueba |
|---|---|
| `camera.py` | Abrir y liberar la cámara; no reabrir si ya está abierta; cámara no disponible; fallo de lectura; flujo de video que libera la cámara al cerrarse; el video sigue si falla el detector; estado del panel (rostros, emoción más grande). |
| `detector.py` | Imagen en blanco, vacía o nula; recuadros y etiquetas (incluso en los bordes); texto "Sin rostro detectado"; clasificador que no carga. |
| `emociones.py` | Etiquetas en español; recorte a 64x64; confianza como probabilidad; modelo ausente, corrupto o con salida inválida; el modelo se carga una sola vez. |
| `registro.py` | Máximo un registro cada 2 s; no guardar sin estimación; fallo de la base sin romper el video; estadísticas; borrado. |
| Vistas y rutas | Página de inicio y sus avisos; iniciar, transmitir y detener; solo los métodos permitidos; estadísticas y borrado; archivos estáticos. |

## 3. Limitaciones conocidas

- **Falsos positivos del detector.** El detector Haar puede marcar como rostro algo que no
  lo es (por ejemplo, un brazo). También puede fallar con rostros de lado, poca luz o
  contraluz.
- **Tendencia a "Neutral".** El modelo FER+ tiende a clasificar como "Neutral". Es una
  estimación y puede equivocarse según la iluminación, la posición y la cámara. No es un
  diagnóstico ni el estado psicológico real de una persona.
- **Solo funciona en el equipo que ejecuta Django.** La cámara se abre en el servidor con
  `cv2.VideoCapture`, así que solo sirve en local. Publicarla en internet requeriría
  capturar con la cámara del navegador (`getUserMedia`), que no está implementado.
- **Un solo rostro en el panel.** Si hay varios rostros, el panel y el registro usan el más
  grande; en el video se dibujan todos.
- **El modelo no está en Git.** `emotion-ferplus-8.onnx` (~33 MB) se descarga aparte; ver
  `emociones/modelos/LEEME.md`. Sin él, el video muestra recuadros pero sin etiqueta.
- **Versión de OpenCV.** Se usa `opencv-python` 4.14.0.94 porque la serie 5.0 no incluye
  los archivos Haar cascade.

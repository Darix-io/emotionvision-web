# EmotionVision Web — Plan por fases

Regla: al terminar cada fase, Claude Code ejecuta `check` y `test`, explica en
pocas líneas, hace commit y **se detiene**. Se continúa solo con
"continúa con la fase N".

| Fase | Sesión | Qué se construye | Criterio de finalización |
|---|---|---|---|
| 1 | S1 | Entorno virtual, Django, PostgreSQL local, app `emociones`, `.gitignore`, `.env.example`, `requirements.txt` | `runserver` abre la página de inicio |
| 2 | S1 | `camera.py` con OpenCV y transmisión al navegador | El navegador muestra la cámara en vivo |
| 3 | S2 | `detector.py`: detección de rostros y rectángulos sobre el video; control de "sin rostro" | Se dibuja un recuadro en cada rostro |
| 4 | S2 | `emociones.py`: elegir e integrar modelo (2 opciones gratuitas explicadas), etiqueta sobre el video | Se ve la emoción estimada sobre el rostro |
| 5 | S3 | Diseño de la interfaz y dashboard, botones iniciar/detener cámara | Interfaz clara y controles funcionando |
| 6 | S3 | Modelo en PostgreSQL, guardar resultados mínimos, estadísticas básicas | Los registros se guardan y se consultan |
| 7 | S3 | Pruebas automáticas y casos CP-01 a CP-10 documentados | `test` en verde y tabla de pruebas completa |
| 8 | S3 | README, revisión de `.gitignore`, verificar que otra persona pueda instalarlo | Instalación desde cero comprobada |
| 9 | — | Push a GitHub y pull request, **juntos** | Repositorio publicado |
| Extra | — | (Opcional) cámara del navegador con `getUserMedia` para publicar en internet | Funciona fuera de la laptop |

## Qué debe mandar el estudiante tras cada fase

1. Capturas de la pantalla o del navegador.
2. La línea final de `test` (total y OK).
3. Cualquier error, copiado completo.

## Casos de prueba (se llenan solo con lo que el estudiante observó)

| Código | Prueba | Resultado esperado | Resultado observado |
|---|---|---|---|
| CP-01 | Iniciar aplicación | Django funciona | |
| CP-02 | Activar cámara | El video aparece | |
| CP-03 | Mostrar un rostro | El rostro es detectado | |
| CP-04 | Analizar una expresión | El modelo devuelve una estimación | |
| CP-05 | Mostrar resultado | La etiqueta aparece en el video | |
| CP-06 | No detectar rostro | El sistema continúa funcionando | |
| CP-07 | Detener cámara | La captura finaliza | |
| CP-08 | Conectar PostgreSQL | La aplicación accede a la base de datos | |
| CP-09 | Registrar un resultado | El registro se guarda correctamente | |
| CP-10 | Instalar desde GitHub | Se configura siguiendo el README | |

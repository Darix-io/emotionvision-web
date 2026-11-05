# EmotionVision Web — Memoria del proyecto para Claude Code

Proyecto académico (Construcción de Software, UNEMI): aplicación web que captura
video con una cámara, detecta rostros con OpenCV y muestra una **estimación** de
emociones sobre el video. Es independiente de cualquier otro proyecto del
estudiante (no reutilizar nombres, módulos ni decisiones de otros proyectos).

## Cómo trabajar con el estudiante (reglas obligatorias)

- El estudiante es principiante en Git y Django. Explica en **español sencillo**,
  corto y directo. Nada de textos largos.
- Trabajas **por fases** (ver `FASES.md`). Al terminar cada fase: ejecuta
  `python manage.py check` y `python manage.py test`, explica en pocas líneas qué
  cambiaste y **detente**. No avances hasta que el estudiante escriba
  "continúa con la fase N".
- Un commit por fase (o por ajuste), mensaje claro en español. **No hagas push**:
  el push se hace junto con el estudiante al final.
- Antes de cambiar código existente, léelo. No inventes archivos, campos ni
  resultados. No digas que algo funciona hasta que el estudiante lo pruebe.
- Al explicar, usa: qué se hizo → para qué sirve → cómo probarlo → qué debe ver.
- Si hay un error, analiza el mensaje exacto antes de proponer solución.
- Recursos **gratuitos primero**; no propongas servicios de pago.

## Stack obligatorio (no sustituir sin consultar)

Python · Django · OpenCV (`cv2`) · PostgreSQL · HTML/CSS/JS · modelo de
reconocimiento de emociones · Git y GitHub.

Aclaración técnica: OpenCV captura y procesa imágenes y detecta rostros, pero
**no reconoce emociones por sí solo**; hay que integrar un modelo aparte.

## Arquitectura (capas, sin lógica pesada en views.py)

```
Navegador (HTML/CSS/JS) → Django (views delgadas)
                              ├─ camera.py    → captura con OpenCV
                              ├─ detector.py  → detección de rostros
                              ├─ emociones.py → modelo de estimación
                              └─ PostgreSQL   → registros
```

Estructura de referencia (se construye de a poco, no crear archivos de más):

```
emotionvision_web/
├── config/ (settings/, urls.py, wsgi.py)
├── emociones/ (camera.py, detector.py, emociones.py, models.py, views.py,
│               urls.py, tests.py, templates/emociones/, static/emociones/)
├── manage.py · requirements.txt · .gitignore · .env.example · README.md · CLAUDE.md
```

## Decisiones técnicas

- Fases 1–3 siguen la práctica de clase: `cv2.VideoCapture` en el servidor y
  transmisión al navegador. Esto solo funciona con la cámara del equipo que
  ejecuta Django (local).
- Si se quiere publicar en internet, hará falta una Fase extra: capturar con la
  cámara del navegador (`getUserMedia`) y enviar fotogramas a Django.
- El modelo de emociones se elige en la Fase 4 explicando 2 opciones gratuitas y
  livianas; no se instala nada pesado sin consultar.
- Configuración con variables de entorno (`.env`, nunca subido a GitHub).
  `.env.example` documenta cada variable.

## Privacidad y uso responsable

- Pedir permiso antes de usar la cámara y permitir detenerla fácilmente.
- No guardar video ni imágenes completas. Guardar solo datos mínimos (fecha,
  emoción estimada, confianza).
- No identificar personas. Presentar los resultados como **estimaciones del
  modelo**, nunca como diagnóstico ni como estado psicológico real. Avisar que
  puede equivocarse según iluminación, posición y cámara.

## Errores conocidos a evitar

- Comentarios Django `{# #}` de varias líneas: usar `{% comment %}`.
- Reiniciar `runserver` tras crear rutas nuevas si aparece `NoReverseMatch`.

## Entrega

Repositorio con código, `requirements.txt`, `.gitignore` (excluye `.venv` y
`.env`), pruebas documentadas (CP-01 a CP-10 en `FASES.md`) y README con
instalación paso a paso.

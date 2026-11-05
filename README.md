# EmotionVision Web

Proyecto académico de Construcción de Software (UNEMI).

## Qué hace

Es una aplicación web que usa la cámara del computador, detecta rostros y muestra sobre el
video una **estimación** de la emoción. También muestra un panel con la emoción actual y
estadísticas básicas de los registros guardados.

Los resultados son **estimaciones de un modelo**, no un diagnóstico ni el estado psicológico
real de una persona.

## Tecnologías

- Python 3.12 y Django
- OpenCV (`opencv-python`): captura de video y detección de rostros (Haar cascade)
- ONNX Runtime con el modelo FER+ (`emotion-ferplus-8`): estimación de la emoción
- PostgreSQL: registros mínimos
- HTML, CSS y JavaScript propios
- Git y GitHub

## Requisitos

- Windows (así se probó el proyecto)
- Python 3.12
- PostgreSQL 17
- Git
- Una cámara web conectada al mismo equipo que ejecuta Django

## Instalación paso a paso

Los comandos son para **PowerShell**.

### 1. Clonar el proyecto

```powershell
git clone <URL-DEL-REPOSITORIO>
cd emotionvision_web
```

Cambia `<URL-DEL-REPOSITORIO>` por la dirección real del repositorio en GitHub.

### 2. Crear el entorno virtual e instalar las librerías

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si PowerShell no deja activar el entorno, prueba con
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y vuelve a intentar.

### 3. Crear la base de datos en PostgreSQL

Abre `psql` con tu usuario (te pide la contraseña):

```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres
```

Dentro de `psql` escribe:

```sql
CREATE DATABASE emotionvision;
\q
```

El usuario de PostgreSQL debe poder crear bases de datos, porque las pruebas automáticas
crean una base temporal.

### 4. Crear el archivo `.env`

Copia el ejemplo y complétalo con tus datos:

```powershell
Copy-Item .env.example .env
```

Abre `.env` y escribe los valores:

```
SECRET_KEY=una-clave-larga-y-aleatoria
DB_NAME=emotionvision
DB_USER=postgres
DB_PASSWORD=tu-contraseña-de-postgresql
DB_HOST=localhost
DB_PORT=5432
```

Para generar una `SECRET_KEY`:

```powershell
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

El archivo `.env` tiene tus claves: **nunca se sube a GitHub** (ya está en `.gitignore`).

### 5. Descargar el modelo FER+

El modelo pesa unos 33 MB y no está en el repositorio. Descárgalo así:

```powershell
Invoke-WebRequest -Uri "https://github.com/onnx/models/raw/main/validated/vision/body_analysis/emotion_ferplus/model/emotion-ferplus-8.onnx" -OutFile "emociones\modelos\emotion-ferplus-8.onnx"
```

El archivo debe pesar 35.040.571 bytes. Más detalles en
[emociones/modelos/LEEME.md](emociones/modelos/LEEME.md).

Sin el modelo, la aplicación funciona pero muestra solo los recuadros, sin etiqueta de emoción.

### 6. Crear las tablas

```powershell
python manage.py migrate
```

### 7. Ejecutar el servidor

```powershell
python manage.py runserver
```

Abre http://127.0.0.1:8000/ en el navegador, pulsa "Iniciar cámara" y acepta el aviso de
privacidad.

## Pruebas

```powershell
python manage.py check
python manage.py test
```

Las pruebas automáticas no necesitan cámara real ni el modelo descargado, pero sí que
PostgreSQL esté funcionando y el `.env` completo.

Los casos de prueba manuales (CP-01 a CP-10), las pruebas automáticas y las limitaciones
están en [docs/PRUEBAS.md](docs/PRUEBAS.md).

## Privacidad

- Se pide permiso (aviso de privacidad) antes de encender la cámara y se puede detener
  en cualquier momento con "Detener cámara".
- **No se guarda video ni imágenes.**
- No se identifica a ninguna persona.
- Solo se guarda la fecha, la emoción estimada y la confianza, como máximo un registro cada
  2 segundos y solo con la cámara encendida.
- El botón "Borrar registros" elimina todos los datos guardados.

## Limitaciones

- La cámara se abre en el servidor, así que **solo funciona en el equipo que ejecuta Django**.
  No sirve para publicarla en internet tal como está.
- El detector Haar puede marcar falsos positivos (por ejemplo, un brazo) y falla con rostros
  de lado, poca luz o contraluz.
- El modelo FER+ tiende a responder "Neutral" y puede equivocarse según la iluminación, la
  posición y la cámara.
- Si hay varios rostros, el panel y los registros usan el más grande.
- Se usa `opencv-python` 4.14.0.94 porque la serie 5.0 no incluye los archivos Haar cascade.

## Estructura

```
config/      configuración de Django
emociones/   app principal (camera.py, detector.py, emociones.py, registro.py, models.py, views.py)
docs/        pruebas y limitaciones
```

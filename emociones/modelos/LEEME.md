# Modelo de emociones (FER+)

El archivo `emotion-ferplus-8.onnx` (~33 MB) **no se sube a GitHub**. Hay que descargarlo
del repositorio oficial ONNX Model Zoo y dejarlo en esta carpeta.

En PowerShell, desde la raíz del proyecto:

```powershell
Invoke-WebRequest -Uri "https://github.com/onnx/models/raw/main/validated/vision/body_analysis/emotion_ferplus/model/emotion-ferplus-8.onnx" -OutFile "emociones\modelos\emotion-ferplus-8.onnx"
```

Comprobación: el archivo debe pesar 35.040.571 bytes.
SHA256: `A2A2BA6A335A3B29C21ACB6272F962BD3D47F84952AAFFA03B60986E04EFA61C`

Si el archivo no está, la aplicación sigue funcionando: muestra el video con los
recuadros, pero sin etiqueta de emoción.

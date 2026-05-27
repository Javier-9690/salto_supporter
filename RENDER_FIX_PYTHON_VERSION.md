# Corrección para Render: Python 3.14 / greenlet

Si Render muestra en logs:

```text
Using Python version 3.14.3 (default)
Failed building wheel for greenlet
```

el servicio fue creado como **Python runtime nativo** y Render está usando su versión por defecto.

## Opción recomendada: Docker

Crea un nuevo Web Service en Render usando:

- Runtime/Environment: Docker
- Dockerfile: `./Dockerfile`

No uses el runtime Python nativo para este proyecto si vas a usar Playwright con Chromium.

## Opción alternativa: Python runtime nativo

Si sigues usando Python runtime nativo:

1. Agrega la variable de entorno:

```text
PYTHON_VERSION=3.11.9
```

2. Confirma que exista en la raíz del repo:

```text
.python-version
```

con el contenido:

```text
3.11.9
```

3. Build Command:

```bash
pip install -r requirements.txt && playwright install chromium
```

4. Start Command:

```bash
gunicorn -b 0.0.0.0:${PORT:-10000} app:app --timeout 1800 --workers 1
```

## Variables obligatorias

```text
APP_PASSWORD=clave_para_entrar_a_la_web
TARGET_BASE_URL=https://url-publica-del-sistema-hoteleria
FLASK_SECRET_KEY=clave_larga_aleatoria
```

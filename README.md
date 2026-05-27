# Importador de calendarios - Reportabilidad 5400

Aplicación web Flask con estética Aramark / Escondida BHP para cargar un Excel con columnas `RUT` y `CALENDARIO`, actualizar calendarios en el sistema hotelero usando Playwright y descargar un Excel de resultados.

## Error corregido de Render

El proyecto anterior incluía `pandas`. Render intentó compilar pandas con Python 3.14 y falló. Esta versión elimina pandas y usa `openpyxl`, además incluye `runtime.txt` con Python 3.11.9 y un `Dockerfile` con `python:3.11-slim`.

## Excel requerido

El archivo debe ser `.xlsx` y tener estos encabezados exactos en la primera fila:

```text
RUT | CALENDARIO
```

Ejemplo:

```text
26136058-6 | Calendar general
21095018-4 | Turno 4x3 Lu
```

## Variables de entorno en Render

```text
APP_PASSWORD=clave_para_entrar_a_esta_web
TARGET_BASE_URL=https://url-publica-del-sistema-hoteleria
FLASK_SECRET_KEY=clave_larga_aleatoria
```

## Despliegue recomendado en Render

### Opción recomendada: Docker

1. Sube esta carpeta a GitHub.
2. En Render crea un Web Service.
3. Selecciona Docker.
4. Agrega las variables de entorno.
5. Deploy.

El `Dockerfile` instala Chromium con:

```dockerfile
RUN playwright install --with-deps chromium
```

### Opción alternativa: Native Python

También se incluye `runtime.txt` para fijar Python 3.11.9. En Native Python usa:

Build command:

```bash
pip install -r requirements.txt && playwright install chromium
```

Start command:

```bash
gunicorn -b 0.0.0.0:${PORT:-10000} app:app --timeout 1800 --workers 1
```

## Importante de red

Render corre en la nube. Si el sistema hotelero solo existe como `http://hoteleria_vca:8100` dentro de tu red local, Render no podrá accederlo. Debes usar una URL pública, VPN, túnel autorizado o desplegar esta app dentro de la misma red donde existe el sistema.

## Fix Render Python 3.14 / greenlet

Si el deploy falla con `Failed building wheel for greenlet` y el log indica `Using Python version 3.14.3`, revisa `RENDER_FIX_PYTHON_VERSION.md`.
La solución recomendada es crear el servicio como **Docker Web Service**. Si usas runtime Python nativo, configura `PYTHON_VERSION=3.11.9` y asegúrate de que `.python-version` esté en la raíz del repositorio.

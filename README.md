# Importador de calendarios para Render

Aplicación Flask para subir un Excel con columnas `RUT` y `CALENDARIO`, entrar al sistema hotelero con Playwright, actualizar el calendario del usuario y devolver un Excel de resultados.

## Importante

Render corre en la nube. Si tu sistema solo existe como `http://hoteleria_vca:8100` dentro de tu computador, Render no podrá accederlo. Debes exponer el sistema con una URL pública/VPN/túnel permitido por tu organización y usarla en `TARGET_BASE_URL`.

## Columnas del Excel

```text
RUT | CALENDARIO
26136058-6 | Calendar general
21095018-4 | Turno 4x3 Lu
```

## Variables de entorno recomendadas en Render

```text
APP_PASSWORD=una_clave_para_abrir_la_web
TARGET_BASE_URL=https://url-publica-del-sistema
FLASK_SECRET_KEY=clave_larga_aleatoria
```

## Local

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
python app.py
```

## Render con Docker

1. Sube estos archivos a un repositorio GitHub.
2. En Render, crea un Web Service nuevo.
3. Selecciona Docker.
4. Agrega las variables de entorno.
5. Deploy.

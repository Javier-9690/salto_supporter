import os
import uuid
from pathlib import Path

import pandas as pd
from flask import Flask, render_template, request, send_file, abort, flash, redirect, url_for
from werkzeug.utils import secure_filename

from automation_worker import run_import_job


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "cambia-esta-clave-local")

BASE_DIR = Path(__file__).resolve().parent
JOBS_DIR = Path(os.getenv("JOBS_DIR", "/tmp/hoteleria_jobs"))
JOBS_DIR.mkdir(parents=True, exist_ok=True)

APP_PASSWORD = os.getenv("APP_PASSWORD", "")
DEFAULT_TARGET_BASE_URL = os.getenv("TARGET_BASE_URL", "http://hoteleria_vca:8100")

ALLOWED_EXTENSIONS = {"xlsx", "xls"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_app_password(form_value: str) -> bool:
    if not APP_PASSWORD:
        return True
    return form_value == APP_PASSWORD


@app.get("/")
def index():
    return render_template(
        "index.html",
        default_target_base_url=DEFAULT_TARGET_BASE_URL,
        app_password_required=bool(APP_PASSWORD),
    )


@app.post("/run")
def run_job():
    if not validate_app_password(request.form.get("app_password", "")):
        abort(401, "Clave de la aplicación incorrecta.")

    target_base_url = request.form.get("target_base_url", "").strip().rstrip("/")
    system_user = request.form.get("system_user", "").strip()
    system_password = request.form.get("system_password", "")

    if not target_base_url:
        flash("Debes indicar la URL base del sistema hotelero.", "error")
        return redirect(url_for("index"))

    if not system_user or not system_password:
        flash("Debes indicar usuario y contraseña del sistema hotelero.", "error")
        return redirect(url_for("index"))

    uploaded = request.files.get("excel_file")
    if not uploaded or uploaded.filename == "":
        flash("Debes subir un archivo Excel.", "error")
        return redirect(url_for("index"))

    if not allowed_file(uploaded.filename):
        flash("El archivo debe ser .xlsx o .xls.", "error")
        return redirect(url_for("index"))

    job_id = uuid.uuid4().hex
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    filename = secure_filename(uploaded.filename)
    input_path = job_dir / filename
    output_path = job_dir / "resultado_importacion.xlsx"

    uploaded.save(input_path)

    try:
        # Validación rápida para dar error temprano si faltan columnas.
        df = pd.read_excel(input_path)
        required = {"RUT", "CALENDARIO"}
        missing = required.difference(set(df.columns))
        if missing:
            raise ValueError(f"Faltan columnas obligatorias: {', '.join(sorted(missing))}")

        results = run_import_job(
            excel_path=str(input_path),
            output_path=str(output_path),
            base_url=target_base_url,
            username=system_user,
            password=system_password,
            job_dir=str(job_dir),
        )

    except Exception as exc:
        # Resultado con error general para que el usuario pueda descargar evidencia.
        pd.DataFrame([
            {
                "ESTADO": "ERROR",
                "MENSAJE": str(exc),
                "RUT": "",
                "CALENDARIO": "",
            }
        ]).to_excel(output_path, index=False)
        results = [{"ESTADO": "ERROR", "MENSAJE": str(exc), "RUT": "", "CALENDARIO": ""}]

    return render_template(
        "index.html",
        default_target_base_url=target_base_url,
        app_password_required=bool(APP_PASSWORD),
        results=results,
        job_id=job_id,
    )


@app.get("/download/<job_id>")
def download_result(job_id: str):
    safe_job_id = secure_filename(job_id)
    output_path = JOBS_DIR / safe_job_id / "resultado_importacion.xlsx"
    if not output_path.exists():
        abort(404, "No se encontró el resultado.")
    return send_file(output_path, as_attachment=True, download_name="resultado_importacion.xlsx")


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

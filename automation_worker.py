import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


TIMEOUT = 20000


def normalizar_rut(valor) -> str:
    return re.sub(r"[^0-9Kk]", "", str(valor)).upper()


def safe_name(valor: str) -> str:
    limpio = re.sub(r"[^0-9A-Za-zKk_-]", "_", str(valor))
    return limpio[:80] or "sin_rut"


def screenshot(page, job_dir: str, name: str, rut: str = "") -> None:
    try:
        filename = f"{name}_{safe_name(rut)}.png" if rut else f"{name}.png"
        path = Path(job_dir) / filename
        page.screenshot(path=str(path), full_page=True)
    except Exception:
        pass


def validar_excel(df: pd.DataFrame) -> pd.DataFrame:
    required = ["RUT", "CALENDARIO"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Falta la columna obligatoria: {col}")

    df = df.copy()
    df["RUT"] = df["RUT"].astype(str).str.strip()
    df["CALENDARIO"] = df["CALENDARIO"].astype(str).str.strip()

    df = df[(df["RUT"] != "") & (df["CALENDARIO"] != "")]
    df = df[~df["RUT"].str.lower().isin(["nan", "none"])]
    df = df[~df["CALENDARIO"].str.lower().isin(["nan", "none"])]

    if df.empty:
        raise ValueError("El Excel no tiene filas válidas con RUT y CALENDARIO.")

    return df


def aceptar_cookies_si_aparece(page):
    try:
        page.get_by_role("button", name=re.compile("Aceptar cookies", re.I)).click(timeout=2500)
    except Exception:
        pass


def esta_en_login(page) -> bool:
    try:
        if "/login" in page.url.lower():
            return True
    except Exception:
        pass

    try:
        u = page.get_by_role("textbox", name="Nombre de usuario").is_visible(timeout=1000)
        p = page.get_by_role("textbox", name="Contraseña").is_visible(timeout=1000)
        return bool(u and p)
    except Exception:
        return False


def login(page, base_url: str, username: str, password: str, job_dir: str):
    page.goto(f"{base_url}/login", wait_until="domcontentloaded")
    aceptar_cookies_si_aparece(page)

    page.get_by_role("textbox", name="Nombre de usuario").fill(username)
    page.get_by_role("textbox", name="Contraseña").fill(password)

    try:
        page.get_by_role("button", name=re.compile("Entrar", re.I)).click(timeout=5000)
    except Exception:
        page.locator('button:has-text("ENTRAR"), input[type="submit"]').first.click()

    try:
        page.locator("text=Personas").first.wait_for(timeout=TIMEOUT)
    except PlaywrightTimeoutError:
        screenshot(page, job_dir, "error_login")
        raise RuntimeError("No se pudo iniciar sesión. Revisa usuario/contraseña o conectividad.")


def relogin_si_aparece(page, base_url: str, username: str, password: str, job_dir: str) -> bool:
    if not esta_en_login(page):
        return False

    aceptar_cookies_si_aparece(page)

    page.get_by_role("textbox", name="Nombre de usuario").fill(username)
    page.get_by_role("textbox", name="Contraseña").fill(password)

    try:
        page.get_by_role("button", name=re.compile("Entrar", re.I)).click(timeout=5000)
    except Exception:
        page.locator('button:has-text("ENTRAR"), input[type="submit"]').first.click()

    try:
        page.locator("text=Personas").first.wait_for(timeout=TIMEOUT)
    except PlaywrightTimeoutError:
        screenshot(page, job_dir, "error_relogin")
        raise RuntimeError("El sistema pidió login, pero no se pudo reingresar.")

    return True


def ir_a_usuarios(page, base_url: str, username: str, password: str, job_dir: str):
    relogin_si_aparece(page, base_url, username, password, job_dir)
    page.goto(f"{base_url}/users", wait_until="domcontentloaded")
    relogin_si_aparece(page, base_url, username, password, job_dir)

    if esta_en_login(page):
        relogin_si_aparece(page, base_url, username, password, job_dir)
        page.goto(f"{base_url}/users", wait_until="domcontentloaded")

    page.locator("text=EXT. ID").first.wait_for(timeout=TIMEOUT)
    page.wait_for_timeout(1000)


def obtener_bbox_ext_id(page) -> Dict[str, float]:
    try:
        encabezado = page.locator("text=EXT. ID").first
        encabezado.wait_for(timeout=5000)
        caja = encabezado.bounding_box()
        if caja:
            return caja
    except Exception:
        pass

    caja_js = page.evaluate(
        """
        () => {
            function visible(el) {
                const r = el.getBoundingClientRect();
                const s = window.getComputedStyle(el);
                return r.width > 0 && r.height > 0 &&
                       s.display !== "none" && s.visibility !== "hidden";
            }
            for (const el of document.querySelectorAll("*")) {
                const texto = (el.innerText || el.textContent || "").trim();
                if (texto.includes("EXT") && texto.includes("ID") && visible(el)) {
                    const r = el.getBoundingClientRect();
                    return {x: r.x, y: r.y, width: r.width, height: r.height};
                }
            }
            return null;
        }
        """
    )

    if caja_js:
        return caja_js

    raise RuntimeError("No se pudo ubicar visualmente el encabezado EXT. ID.")


def abrir_filtro_ext_id(page):
    caja_ext_id = obtener_bbox_ext_id(page)
    botones = page.get_by_role("button", name="f")
    cantidad = botones.count()

    mejor_boton = None
    mejor_score = None
    centro_y_ext_id = caja_ext_id["y"] + caja_ext_id["height"] / 2

    for i in range(cantidad):
        boton = botones.nth(i)
        try:
            if not boton.is_visible():
                continue
            caja_boton = boton.bounding_box()
            if not caja_boton:
                continue
            centro_x = caja_boton["x"] + caja_boton["width"] / 2
            centro_y = caja_boton["y"] + caja_boton["height"] / 2
            if centro_x < caja_ext_id["x"]:
                continue
            score = abs(centro_y - centro_y_ext_id)
            if mejor_score is None or score < mejor_score:
                mejor_score = score
                mejor_boton = boton
        except Exception:
            pass

    if mejor_boton:
        mejor_boton.click(force=True)
        page.wait_for_timeout(800)
        return caja_ext_id

    page.mouse.click(caja_ext_id["x"] + 235, caja_ext_id["y"] + caja_ext_id["height"] / 2)
    page.wait_for_timeout(800)
    return caja_ext_id


def obtener_input_filtro_ext_id(page, caja_ext_id):
    inputs = page.locator("input:visible")
    cantidad = inputs.count()
    mejor_input = None
    mejor_score = None

    for i in range(cantidad):
        inp = inputs.nth(i)
        try:
            tipo = (inp.get_attribute("type") or "").lower()
            if tipo in ["checkbox", "radio", "submit", "password", "hidden"]:
                continue
            caja = inp.bounding_box()
            if not caja:
                continue
            if caja["y"] < caja_ext_id["y"]:
                continue
            score = abs(caja["x"] - (caja_ext_id["x"] - 20)) + abs(caja["y"] - (caja_ext_id["y"] + 45))
            if mejor_score is None or score < mejor_score:
                mejor_score = score
                mejor_input = inp
        except Exception:
            pass

    if not mejor_input:
        raise RuntimeError("No se encontró el input del filtro EXT. ID.")

    return mejor_input


def presionar_lupa_filtro_ext_id(page, caja_ext_id):
    botones = page.get_by_role("button", name="☥")
    cantidad = botones.count()
    mejor_boton = None
    mejor_score = None

    for i in range(cantidad):
        boton = botones.nth(i)
        try:
            if not boton.is_visible():
                continue
            caja = boton.bounding_box()
            if not caja:
                continue
            score = abs(caja["x"] - (caja_ext_id["x"] + 225)) + abs(caja["y"] - (caja_ext_id["y"] + 45))
            if mejor_score is None or score < mejor_score:
                mejor_score = score
                mejor_boton = boton
        except Exception:
            pass

    if mejor_boton:
        mejor_boton.click(force=True)
    else:
        page.mouse.click(caja_ext_id["x"] + 225, caja_ext_id["y"] + 45)

    page.wait_for_timeout(2500)


def aplicar_filtro_ext_id(page, rut: str):
    caja_ext_id = abrir_filtro_ext_id(page)
    input_filtro = obtener_input_filtro_ext_id(page, caja_ext_id)
    input_filtro.click(force=True)
    input_filtro.fill("")
    input_filtro.fill(rut)
    presionar_lupa_filtro_ext_id(page, caja_ext_id)


def obtener_info_fila_por_rut(page, rut: str):
    rut_normalizado = normalizar_rut(rut)
    info = page.evaluate(
        """
        (rutNormalizado) => {
            function normalizar(texto) {
                return String(texto || "").replace(/[^0-9Kk]/g, "").toUpperCase();
            }
            function visible(el) {
                const r = el.getBoundingClientRect();
                const s = window.getComputedStyle(el);
                return r.width > 0 && r.height > 0 &&
                       s.display !== "none" && s.visibility !== "hidden";
            }
            function bbox(el) {
                const r = el.getBoundingClientRect();
                return {x: r.x, y: r.y, width: r.width, height: r.height};
            }
            const filas = Array.from(document.querySelectorAll("tbody tr, tr, [role='row']"));
            for (const fila of filas) {
                if (!visible(fila)) continue;
                const textoFila = (fila.innerText || fila.textContent || "").trim();
                if (!normalizar(textoFila).includes(rutNormalizado)) continue;
                const celdas = Array.from(fila.querySelectorAll("td, [role='cell']")).filter(visible);
                let celdaUsuario = null;
                for (const celda of celdas) {
                    const texto = (celda.innerText || celda.textContent || "").trim();
                    const textoNorm = normalizar(texto);
                    const tieneLetras = /[A-Za-zÁÉÍÓÚÑáéíóúñ]/.test(texto);
                    const noEsRut = !textoNorm.includes(rutNormalizado);
                    if (texto && tieneLetras && noEsRut) {
                        celdaUsuario = celda;
                        break;
                    }
                }
                const target = celdaUsuario || fila;
                return {
                    textoFila: textoFila,
                    textoUsuario: celdaUsuario ? (celdaUsuario.innerText || celdaUsuario.textContent || "").trim() : "",
                    rowBox: bbox(fila),
                    usuarioBox: bbox(target)
                };
            }
            return null;
        }
        """,
        rut_normalizado,
    )

    if not info:
        raise RuntimeError(f"No se detectó una fila visible con el RUT: {rut}")

    return info


def seleccionar_checkbox_de_la_misma_fila(page, info_fila):
    y_fila = info_fila["rowBox"]["y"] + info_fila["rowBox"]["height"] / 2
    page.mouse.click(50, y_fila)
    page.wait_for_timeout(800)


def detalle_usuario_visible(page) -> bool:
    return page.evaluate(
        """
        () => {
            function visible(el) {
                const r = el.getBoundingClientRect();
                const s = window.getComputedStyle(el);
                return r.width > 0 && r.height > 0 &&
                       s.display !== "none" && s.visibility !== "hidden";
            }
            const objetivos = [
                "OPCIONES DE LLAVE",
                "EXPIRACIÓN DE USUARIO Y LLAVE",
                "Activación del usuario",
                "Expiración del usuario",
                "Calendario"
            ];
            for (const el of document.querySelectorAll("*")) {
                if (!visible(el)) continue;
                const texto = (el.innerText || el.textContent || "").trim();
                if (objetivos.includes(texto)) return true;
            }
            return false;
        }
        """
    )


def esperar_detalle_usuario(page, timeout_ms=15000) -> bool:
    limite = datetime.now().timestamp() + timeout_ms / 1000
    while datetime.now().timestamp() < limite:
        if detalle_usuario_visible(page):
            return True
        page.wait_for_timeout(500)
    return False


def abrir_usuario_para_opciones(page, info_fila, rut: str, job_dir: str):
    box = info_fila["usuarioBox"]
    x_usuario = box["x"] + box["width"] / 2
    y_usuario = box["y"] + box["height"] / 2

    page.mouse.click(x_usuario, y_usuario)
    page.wait_for_timeout(2000)

    if not esperar_detalle_usuario(page, timeout_ms=5000):
        page.mouse.dblclick(x_usuario, y_usuario)
        page.wait_for_timeout(3000)

    if not esperar_detalle_usuario(page, timeout_ms=8000):
        screenshot(page, job_dir, "error_no_abre_usuario", rut)
        raise RuntimeError("No se abrió la ficha del usuario.")


def abrir_usuario_con_relogin_si_es_necesario(page, base_url: str, username: str, password: str, rut: str, job_dir: str):
    aplicar_filtro_ext_id(page, rut)
    screenshot(page, job_dir, "resultado_filtro", rut)
    info_fila = obtener_info_fila_por_rut(page, rut)
    seleccionar_checkbox_de_la_misma_fila(page, info_fila)

    try:
        abrir_usuario_para_opciones(page, info_fila, rut, job_dir)
    except Exception:
        if esta_en_login(page):
            relogin_si_aparece(page, base_url, username, password, job_dir)
            ir_a_usuarios(page, base_url, username, password, job_dir)
            aplicar_filtro_ext_id(page, rut)
            info_fila = obtener_info_fila_por_rut(page, rut)
            seleccionar_checkbox_de_la_misma_fila(page, info_fila)
            abrir_usuario_para_opciones(page, info_fila, rut, job_dir)
        else:
            raise

    if esta_en_login(page):
        relogin_si_aparece(page, base_url, username, password, job_dir)
        ir_a_usuarios(page, base_url, username, password, job_dir)
        aplicar_filtro_ext_id(page, rut)
        info_fila = obtener_info_fila_por_rut(page, rut)
        seleccionar_checkbox_de_la_misma_fila(page, info_fila)
        abrir_usuario_para_opciones(page, info_fila, rut, job_dir)


def seleccionar_calendario_select2(page, calendario: str, job_dir: str, rut: str):
    try:
        page.locator(
            "span > .select2 > .selection > .select2-selection > .select2-selection__arrow"
        ).first.click(timeout=5000)
    except Exception:
        page.evaluate(
            """
            () => {
                function visible(el) {
                    const r = el.getBoundingClientRect();
                    const s = window.getComputedStyle(el);
                    return r.width > 0 && r.height > 0 &&
                           s.display !== "none" && s.visibility !== "hidden";
                }
                const elementos = Array.from(document.querySelectorAll("*"));
                const label = elementos.find(el => {
                    if (!visible(el)) return false;
                    const texto = (el.innerText || el.textContent || "").trim();
                    return texto === "Calendario";
                });
                if (!label) throw new Error("No se encontró label Calendario");
                const labelBox = label.getBoundingClientRect();
                const arrows = Array.from(document.querySelectorAll(".select2-selection__arrow")).filter(visible);
                let mejor = null;
                let mejorScore = null;
                for (const arrow of arrows) {
                    const r = arrow.getBoundingClientRect();
                    const score = Math.abs(r.y - (labelBox.y + 35)) + Math.abs(r.x - (labelBox.x + 220));
                    if (mejorScore === null || score < mejorScore) {
                        mejorScore = score;
                        mejor = arrow;
                    }
                }
                if (!mejor) throw new Error("No se encontró flecha Select2 Calendario");
                mejor.click();
            }
            """
        )

    page.wait_for_timeout(800)
    search = page.locator('input[type="search"]').last
    search.wait_for(timeout=5000)
    search.click()
    search.fill("")
    search.fill(calendario)
    page.wait_for_timeout(1200)
    screenshot(page, job_dir, "calendario_filtrado", rut)

    try:
        opcion = page.locator(".select2-results__option", has_text=calendario).first
        opcion.wait_for(timeout=5000)
        opcion.click(force=True)
        page.wait_for_timeout(1200)
        screenshot(page, job_dir, "calendario_seleccionado", rut)
        return
    except Exception:
        pass

    opciones = page.locator(".select2-results__option:visible")
    if opciones.count() == 0:
        screenshot(page, job_dir, "error_no_opciones_calendario", rut)
        raise RuntimeError("No se encontraron opciones visibles en el calendario Select2.")

    opciones.first.click(force=True)
    page.wait_for_timeout(1200)
    screenshot(page, job_dir, "calendario_seleccionado_primera_opcion", rut)


def guardar_cambios(page, job_dir: str, rut: str):
    aceptar_cookies_si_aparece(page)
    try:
        page.get_by_role("button", name=re.compile("Guardar", re.I)).click(timeout=5000)
        page.wait_for_timeout(3500)
        screenshot(page, job_dir, "despues_de_guardar", rut)
        return
    except Exception:
        pass

    try:
        page.get_by_role("button", name="✓Guardar").click(timeout=5000)
        page.wait_for_timeout(3500)
        screenshot(page, job_dir, "despues_de_guardar", rut)
        return
    except Exception:
        pass

    boton = page.evaluate(
        """
        () => {
            function visible(el) {
                const r = el.getBoundingClientRect();
                const s = window.getComputedStyle(el);
                return r.width > 0 && r.height > 0 &&
                       s.display !== "none" && s.visibility !== "hidden";
            }
            const elementos = Array.from(document.querySelectorAll("button, a, div[role='button'], span"));
            const candidatos = [];
            for (const el of elementos) {
                if (!visible(el)) continue;
                const texto = (el.innerText || el.textContent || "").trim().toUpperCase();
                const cls = String(el.className || "").toLowerCase();
                if (!texto.includes("GUARDAR")) continue;
                if (cls.includes("disabled")) continue;
                if (el.disabled) continue;
                if (el.getAttribute("aria-disabled") === "true") continue;
                const r = el.getBoundingClientRect();
                candidatos.push({x: r.x, y: r.y, width: r.width, height: r.height, texto: texto});
            }
            candidatos.sort((a, b) => b.y - a.y);
            return candidatos.length ? candidatos[0] : null;
        }
        """
    )

    if not boton:
        screenshot(page, job_dir, "error_no_boton_guardar", rut)
        raise RuntimeError("No se encontró un botón GUARDAR habilitado.")

    page.mouse.click(boton["x"] + boton["width"] / 2, boton["y"] + boton["height"] / 2)
    page.wait_for_timeout(3500)
    screenshot(page, job_dir, "despues_de_guardar", rut)


def procesar_usuario(page, base_url: str, username: str, password: str, rut: str, calendario: str, job_dir: str):
    ir_a_usuarios(page, base_url, username, password, job_dir)
    abrir_usuario_con_relogin_si_es_necesario(page, base_url, username, password, rut, job_dir)
    relogin_si_aparece(page, base_url, username, password, job_dir)
    seleccionar_calendario_select2(page, calendario, job_dir, rut)
    relogin_si_aparece(page, base_url, username, password, job_dir)
    guardar_cambios(page, job_dir, rut)


def guardar_resultados(resultados: List[Dict], output_path: str):
    pd.DataFrame(resultados).to_excel(output_path, index=False)


def run_import_job(
    excel_path: str,
    output_path: str,
    base_url: str,
    username: str,
    password: str,
    job_dir: str,
) -> List[Dict]:
    base_url = base_url.rstrip("/")
    df = pd.read_excel(excel_path)
    df = validar_excel(df)

    resultados: List[Dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(viewport={"width": 1500, "height": 900})
        page = context.new_page()

        try:
            login(page, base_url, username, password, job_dir)

            for index, fila in df.iterrows():
                rut = str(fila["RUT"]).strip()
                calendario = str(fila["CALENDARIO"]).strip()

                try:
                    procesar_usuario(page, base_url, username, password, rut, calendario, job_dir)
                    resultados.append(
                        {
                            "Fila Excel": index + 2,
                            "RUT": rut,
                            "CALENDARIO": calendario,
                            "ESTADO": "OK",
                            "MENSAJE": "Calendario actualizado correctamente",
                            "FECHA_HORA": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )

                except Exception as exc:
                    screenshot(page, job_dir, "error", rut)
                    resultados.append(
                        {
                            "Fila Excel": index + 2,
                            "RUT": rut,
                            "CALENDARIO": calendario,
                            "ESTADO": "ERROR",
                            "MENSAJE": str(exc),
                            "FECHA_HORA": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )
                    try:
                        relogin_si_aparece(page, base_url, username, password, job_dir)
                    except Exception:
                        pass

                guardar_resultados(resultados, output_path)

        finally:
            context.close()
            browser.close()

    guardar_resultados(resultados, output_path)
    return resultados

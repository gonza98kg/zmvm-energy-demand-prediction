"""
Descargador automático de Demanda Real del Sistema — CENACE SIM Portal
Usa Safari WebDriver para automatizar la descarga de archivos ZIP por trimestre.

Uso:
    python3 src/download_demanda.py

Guarda los ZIPs en: data/raw/demanda_real/
Luego ejecuta load_demanda_real() en data_loader.py para procesar los CSV.

Requiere:
    - Safari con "Permitir automatización remota" activado
    - pip install selenium
"""

import time
import shutil
from datetime import date
from dateutil.relativedelta import relativedelta
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.safari.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoAlertPresentException

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RAW_DIR    = Path(__file__).resolve().parents[1] / "data" / "raw" / "demanda_real"
DL_DIR     = Path.home() / "Downloads"
RAW_DIR.mkdir(parents=True, exist_ok=True)

PORTAL_URL  = "https://www.cenace.gob.mx/SIM/VISTA/REPORTES/DemandaRealSist.aspx"
START_DATE  = date(2016, 1, 1)
END_DATE    = date(2024, 12, 31)
CHUNK_MONTHS = 3
DL_TIMEOUT  = 300  # seconds to wait for Safari to download + extract the ZIP


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def date_chunks(start: date, end: date, months: int):
    current = start
    while current <= end:
        chunk_end = min(current + relativedelta(months=months) - relativedelta(days=1), end)
        yield current, chunk_end
        current = chunk_end + relativedelta(days=1)


def chunk_done(fi: date, ff: date) -> bool:
    """Un chunk está completo si existe su carpeta marcadora en RAW_DIR."""
    marker = RAW_DIR / f".done_{fi.isoformat()}_{ff.isoformat()}"
    return marker.exists()


def mark_done(fi: date, ff: date):
    marker = RAW_DIR / f".done_{fi.isoformat()}_{ff.isoformat()}"
    marker.touch()


def fill_date(driver, field_id: str, val: str):
    """Escribe fecha en un RadDatePicker vía teclado."""
    el = driver.find_element(By.ID, field_id)
    driver.execute_script("arguments[0].removeAttribute('readonly')", el)
    el.click()
    time.sleep(0.3)
    el.send_keys(Keys.CONTROL + "a")
    el.send_keys(val)
    el.send_keys(Keys.TAB)
    time.sleep(1)


def wait_for_new_folder(before_entries: set, timeout: int = DL_TIMEOUT) -> Path | None:
    """
    Safari descarga el ZIP como una carpeta .zip.download (en progreso),
    luego lo extrae en una carpeta final y elimina el .download.

    Estrategia principal:
      1. Espera a que aparezca UNA NUEVA carpeta .zip.download (no en before_entries)
      2. Deriva el nombre final eliminando el sufijo .zip.download
      3. Espera a que esa carpeta final exista Y el .download desaparezca
      4. Verifica estabilidad de tamaño antes de retornar

    Fallback: si aparece alguna nueva carpeta (sin .download) que no estaba en before, la usa.
    """
    elapsed = 0
    dl_folder_path: Path | None = None   # el .zip.download detectado
    final_folder_path: Path | None = None   # el destino esperado

    while elapsed < timeout:
        all_entries = {p: p.stat().st_mtime for p in DL_DIR.iterdir()}

        # --- Fase 1: detectar qué .zip.download nuevo apareció ---
        if dl_folder_path is None:
            new_dl = [
                p for p in all_entries
                if p.is_dir()
                and p.name.endswith(".download")
                and p not in before_entries
            ]
            if new_dl:
                dl_folder_path = sorted(new_dl, key=lambda p: all_entries[p], reverse=True)[0]
                # El nombre de la carpeta extraída = nombre sin sufijo .zip.download
                stem = dl_folder_path.name
                if stem.endswith(".zip.download"):
                    stem = stem[: -len(".zip.download")]
                elif stem.endswith(".download"):
                    stem = stem[: -len(".download")]
                final_folder_path = DL_DIR / stem
                print(f"\n  [↓ {stem[:55]}...]", end=" ", flush=True)

        # --- Fase 2: esperar a que aparezca la carpeta extraída ---
        if final_folder_path is not None and final_folder_path.exists() and final_folder_path.is_dir():
            # Verificar que el .download ya desapareció (extracción terminó)
            if dl_folder_path is None or not dl_folder_path.exists():
                # Esperar estabilidad
                prev_size = -1
                for _ in range(10):
                    size = sum(f.stat().st_size for f in final_folder_path.rglob("*") if f.is_file())
                    if size == prev_size and size > 0:
                        break
                    prev_size = size
                    time.sleep(2)
                return final_folder_path

        # --- Fallback: nueva carpeta directa (sin .download) no estaba en before ---
        new_direct = [
            p for p in all_entries
            if p.is_dir()
            and not p.name.endswith(".download")
            and p not in before_entries
        ]
        if new_direct:
            folder = sorted(new_direct, key=lambda p: all_entries[p], reverse=True)[0]
            prev_size = -1
            for _ in range(10):
                size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
                if size == prev_size and size > 0:
                    break
                prev_size = size
                time.sleep(2)
            return folder

        time.sleep(3)
        elapsed += 3

    return None


def copy_csvs(src_folder: Path) -> int:
    """Copia todos los CSV de src_folder (recursivo) a RAW_DIR."""
    count = 0
    for csv in src_folder.rglob("*.csv"):
        dest = RAW_DIR / csv.name
        if not dest.exists():
            shutil.copy2(csv, dest)
            count += 1
    return count


# ---------------------------------------------------------------------------
# Main downloader
# ---------------------------------------------------------------------------

def download_all():
    print(f"Iniciando descarga: {START_DATE} → {END_DATE}")
    print(f"Destino: {RAW_DIR}\n")

    driver = webdriver.Safari(options=Options())
    wait   = WebDriverWait(driver, 20)

    try:
        driver.get(PORTAL_URL)
        time.sleep(5)

        chunks = list(date_chunks(START_DATE, END_DATE, CHUNK_MONTHS))
        total  = len(chunks)

        for i, (fi, ff) in enumerate(chunks, 1):
            fi_str = fi.strftime("%d/%m/%Y")
            ff_str = ff.strftime("%d/%m/%Y")

            if chunk_done(fi, ff):
                print(f"[{i:02d}/{total}] {fi_str} → {ff_str}  (skip)")
                continue

            print(f"[{i:02d}/{total}] {fi_str} → {ff_str} ...", end=" ", flush=True)

            try:
                # Snapshot completo de Downloads ANTES de descargar
                before = set(DL_DIR.iterdir())

                # Set dates via Telerik JS API (más confiable que teclado)
                driver.execute_script(f"""
                    var fi = $find('ctl00_ContentPlaceHolder1_RadDatePickerFIVisualizarPorBalance');
                    var ff = $find('ctl00_ContentPlaceHolder1_RadDatePickerFFVisualizarPorBalance');
                    if(fi) fi.set_selectedDate(new Date({fi.year},{fi.month-1},{fi.day}));
                    if(ff) ff.set_selectedDate(new Date({ff.year},{ff.month-1},{ff.day}));
                """)
                time.sleep(2)

                # Click download button
                btn = wait.until(EC.element_to_be_clickable(
                    (By.ID, "ContentPlaceHolder1_DescargarArchivosCsv_PorBalance")
                ))
                driver.execute_script("arguments[0].click()", btn)
                time.sleep(2)

                # Dismiss any alert
                try:
                    driver.switch_to.alert.accept()
                except NoAlertPresentException:
                    pass

                # Wait for new folder in Downloads
                new_folder = wait_for_new_folder(before, timeout=DL_TIMEOUT)

                if new_folder:
                    n = copy_csvs(new_folder)
                    mark_done(fi, ff)
                    print(f"OK ({n} CSVs copiados de '{new_folder.name}')")
                else:
                    print("TIMEOUT — no apareció carpeta nueva en Downloads")

                # Reload portal for next iteration
                driver.get(PORTAL_URL)
                time.sleep(5)

            except Exception as e:
                print(f"ERROR: {e}")
                driver.get(PORTAL_URL)
                time.sleep(5)

    finally:
        driver.quit()
        total_csvs = len(list(RAW_DIR.glob("*.csv")))
        print(f"\nDescarga completada. CSVs en proyecto: {total_csvs:,}")


if __name__ == "__main__":
    download_all()

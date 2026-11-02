"""Captura de pantallas de la aplicación con Playwright (para el README.md)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8050"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "screenshots")
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1500, "height": 1100}, device_scale_factor=2)
    errores = []
    page.on("console", lambda m: errores.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errores.append(f"pageerror: {e}"))

    page.goto(BASE, wait_until="networkidle", timeout=120_000)
    page.wait_for_selector("#g-mapa .plot-container", timeout=120_000)
    time.sleep(6)

    page.screenshot(path=str(OUT / "00-vista-completa.png"), full_page=True)

    tarjetas = {
        "01-mapa": ".card:has(#g-mapa)",
        "02-lineas-mensuales": ".card:has(#g-mes)",
        "03-barras-ciudades-violentas": ".card:has(#g-ciudad)",
        "04-circular-menor-mortalidad": ".card:has(#g-pie)",
        "05-tabla-causas": ".card:has(#t-causas)",
        "06-barras-apiladas-sexo": ".card:has(#g-sexo)",
        "07-histograma-edad": ".card:has(#g-edad)",
        "08-filtros-y-kpis": ".bloque",
    }
    for nombre, selector in tarjetas.items():
        el = page.query_selector(selector)
        if el is None:
            errores.append(f"no se encontró {selector}")
            continue
        el.scroll_into_view_if_needed()
        time.sleep(1.2)
        el.screenshot(path=str(OUT / f"{nombre}.png"))

    # Interacción: filtro por Bogotá desde el mapa
    page.locator("#g-mapa path.choroplethlocation").nth(0).click(force=True)
    time.sleep(4)
    page.screenshot(path=str(OUT / "09-interaccion-filtro.png"), full_page=False)

    browser.close()

print("capturas generadas en", OUT)
if errores:
    print("ERRORES DETECTADOS:")
    for e in errores[:25]:
        print(" -", e)
else:
    print("sin errores de consola")

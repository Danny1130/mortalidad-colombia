"""
Preparación reproducible de los datos para el tablero de mortalidad 2019.

Descarga las fuentes oficiales del DANE (cacheadas en `data/raw/`), y construye
los cuatro archivos de trabajo que consume la aplicación Dash:

    data/NoFatal2019.xlsx    microdatos de defunciones no fetales 2019 (curados)
    data/CodigosDeMuerte.xlsx CIE-10 OPS/OMS v.2019 + listas 105 Colombia y 6/67 OPS
    data/Dipipola.xlsx       codificación DIVIPOLA (departamentos, municipios, centros poblados)
    data/Poblacion2019.xlsx  proyección de población municipal 2019 (CNPV 2018)

Uso:
    python scripts/preparar_datos.py
"""

from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data"

# --------------------------------------------------------------------------------------
# Fuentes oficiales
# --------------------------------------------------------------------------------------
URLS = {
    # Estadísticas Vitales 2019, microdatos de defunciones no fetales (catálogo 696)
    "Defunciones.zip": "https://microdatos.dane.gov.co/index.php/catalog/696/download/21424",
    # CIE-10 OPS/OMS versión 2019 (usada por el DANE para codificar defunciones desde 2019)
    "CIE10_OMS_OPS_V19.xlsx": (
        "https://www.dane.gov.co/files/investigaciones/poblacion/defunciones/"
        "clasificacion-int-enfermedades-OMS-OPS-V19.xlsx"
    ),
    # Lista 105 Colombia para la tabulación de mortalidad
    "Lista105_Colombia.xls": (
        "https://www.dane.gov.co/files/investigaciones/poblacion/defunciones/"
        "Lista_105_Colombia_CIE9-y-CIE10.xls"
    ),
    # Lista 6/67 OPS para la tabulación de mortalidad
    "Lista667_PAHO_2018.xlsx": (
        "https://www.dane.gov.co/files/investigaciones/poblacion/defunciones/"
        "Lista667_PAHO_2018.xlsx"
    ),
    # Proyecciones de población municipal 2018-2042 (base CNPV 2018)
    "PPED-AreaMun-2018-2042_VP.xlsx": (
        "https://www.dane.gov.co/files/censo2018/proyecciones-de-poblacion/Municipal/"
        "PPED-AreaMun-2018-2042_VP.xlsx"
    ),
    # DIVIPOLA (datos abiertos DANE): departamentos y centros poblados
    "divipola_departamentos.csv": "https://www.datos.gov.co/resource/t7kp-7a7c.csv",
    "divipola_centros.csv": "https://www.datos.gov.co/resource/xaxy-8nri.csv?$limit=100000",
    # GeoJSON de los 33 departamentos (MGN DANE)
    "col_departamentos.geojson": (
        "https://raw.githubusercontent.com/ytolosa/mapas-colombia/main/output/geojson/"
        "col_departamentos_real_nacional.geojson"
    ),
}

# Referencia de grupos de edad (GRUPO_EDAD1) tomada de la ficha técnica de la actividad.
GRUPOS_EDAD = [
    ("00-04", "Mortalidad neonatal", "Menor de 1 mes"),
    ("05-06", "Mortalidad infantil", "1 a 11 meses"),
    ("07-08", "Primera infancia", "1 a 4 años"),
    ("09-10", "Niñez", "5 a 14 años"),
    ("11", "Adolescencia", "15 a 19 años"),
    ("12-13", "Juventud", "20 a 29 años"),
    ("14-16", "Adultez temprana", "30 a 44 años"),
    ("17-19", "Adultez intermedia", "45 a 59 años"),
    ("20-24", "Vejez", "60 a 84 años"),
    ("25-28", "Longevidad / Centenarios", "85 a 100+ años"),
    ("29", "Edad desconocida", "Sin información"),
]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def descargar() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for nombre, url in URLS.items():
        destino = RAW / nombre
        if destino.exists() and destino.stat().st_size > 0:
            log(f"cache  {nombre} ({destino.stat().st_size/1e6:.1f} MB)")
            continue
        log(f"descarga {nombre} <- {url}")
        r = requests.get(url, timeout=900)
        r.raise_for_status()
        destino.write_bytes(r.content)
        log(f"        -> {destino.stat().st_size/1e6:.1f} MB")


# --------------------------------------------------------------------------------------
# 1. Defunciones no fetales 2019
# --------------------------------------------------------------------------------------
def construir_defunciones() -> None:
    log("1/4 Defunciones no fetales 2019")
    import zipfile

    zip_outer = RAW / "Defunciones.zip"
    with zipfile.ZipFile(zip_outer) as z:
        z.extractall(RAW)
    candidatos = list(RAW.rglob("nofetal2019.zip"))
    if not candidatos:
        raise FileNotFoundError("no se encontró nofetal2019.zip dentro de Defunciones.zip")
    zip_inner = candidatos[0]
    with zipfile.ZipFile(zip_inner) as z:
        z.extractall(RAW)
    csv = next(RAW.glob("nofetal2019.csv"))

    df = pd.read_csv(csv, dtype=str, encoding="latin-1", keep_default_na=False)
    log(f"    registros leídos: {len(df):,}")

    salida = pd.DataFrame(
        {
            "COD_DPTO": df["COD_DPTO"].str.zfill(2),
            "COD_MUNIC": df["COD_MUNIC"].str.zfill(3),
            "SEXO": df["SEXO"],
            "GRUPO_EDAD1": df["GRU_ED1"].str.zfill(2),
            "MES": df["MES"].str.zfill(2),
            "ANO": df["ANO"],
            "CAUSA": df["C_BAS1"],          # causa básica de defunción (CIE-10)
            "CAUSA_667": df["CAUSA_667"],   # lista 6/67 OPS
            "CAUSA_105": df["CAU_HOMOL"],   # lista 105 Colombia
        }
    )

    dicc = pd.DataFrame(
        [
            ("COD_DPTO", "Código DIVIPOLA del departamento donde ocurrió la defunción"),
            ("COD_MUNIC", "Código DIVIPOLA del municipio donde ocurrió la defunción"),
            ("SEXO", "1 = Hombre; 2 = Mujer; 3 = Sexo no especificado"),
            ("GRUPO_EDAD1", "Grupo de edad del fallecido (códigos 00-29, ver hoja Referencia_GRUPO_EDAD1)"),
            ("MES", "Mes de ocurrencia de la defunción (01-12)"),
            ("ANO", "Año de ocurrencia de la defunción"),
            ("CAUSA", "Causa básica de defunción, codificada en CIE-10 (4 caracteres)"),
            ("CAUSA_667", "Código de la causa dentro de la lista 6/67 de la OPS"),
            ("CAUSA_105", "Código de la causa dentro de la lista 105 de Colombia"),
        ],
        columns=["VARIABLE", "DESCRIPCION"],
    )

    ref = pd.DataFrame(GRUPOS_EDAD, columns=["RANGO_GRUPO_EDAD1", "CATEGORIA", "RANGO_EDAD_APROXIMADO"])
    ref.insert(0, "CODIGOS_INDIVIDUALES", ["00,01,02,03,04", "05,06", "07,08", "09,10", "11",
                                            "12,13", "14,15,16", "17,18,19", "20,21,22,23,24",
                                            "25,26,27,28", "29"])

    OUT.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT / "NoFatal2019.xlsx", engine="openpyxl") as xw:
        salida.to_excel(xw, sheet_name="Defunciones", index=False)
        dicc.to_excel(xw, sheet_name="Diccionario", index=False)
        ref.to_excel(xw, sheet_name="Referencia_GRUPO_EDAD1", index=False)
    # Copia en CSV: la aplicación carga este archivo (mucho más rápido que abrir
    # un .xlsx de 244.000 filas en cada arranque).
    salida.to_csv(OUT / "NoFatal2019.csv", index=False)
    log(f"    -> data/NoFatal2019.xlsx  {salida.shape}")


# --------------------------------------------------------------------------------------
# 2. Códigos de muerte
# --------------------------------------------------------------------------------------
def construir_codigos() -> None:
    log("2/4 Códigos de muerte (CIE-10 + listas 105 y 6/67)")

    cie = pd.read_excel(RAW / "CIE10_OMS_OPS_V19.xlsx", sheet_name=0, header=None).iloc[:, :2]
    cie.columns = ["CODIGO", "NOMBRE"]
    cie = cie[cie["CODIGO"].astype(str).str.match(r"^[A-Z][0-9]{2,3}$", na=False)].copy()
    cie["CODIGO"] = cie["CODIGO"].astype(str).str.strip()
    cie["NOMBRE"] = cie["NOMBRE"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    cie = cie[cie["NOMBRE"] != ""].drop_duplicates("CODIGO")
    cie["NIVEL"] = cie["CODIGO"].str.len().map({3: "3 caracteres", 4: "4 caracteres"})
    cie = cie[["CODIGO", "NOMBRE", "NIVEL"]].sort_values("CODIGO")

    l105 = pd.read_excel(RAW / "Lista105_Colombia.xls", sheet_name="Anexo1", header=None).dropna(how="all")
    l105 = l105[l105.iloc[:, 0].astype(str).str.match(r"^\d{1,3}$", na=False)].copy()
    l105.columns = ["CODIGO_LISTA_105", "CAUSA", "CODIGOS_CIE10", "CODIGOS_CIE9"]
    l105["CODIGO_LISTA_105"] = l105["CODIGO_LISTA_105"].astype(str).str.zfill(3)
    l105["CAUSA"] = l105["CAUSA"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()

    l667 = pd.read_excel(RAW / "Lista667_PAHO_2018.xlsx", sheet_name=0, header=None)
    l667 = l667.iloc[4:, :4].copy()
    l667.columns = ["NO", "DESCRIPCION", "CODIGOS_CIE10", "NOTAS"]
    l667 = l667[l667["NO"].astype(str).str.strip().ne("No.")]
    for col in l667.columns:
        l667[col] = l667[col].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    l667 = l667[l667["NO"] != "nan"]

    with pd.ExcelWriter(OUT / "CodigosDeMuerte.xlsx", engine="openpyxl") as xw:
        cie.to_excel(xw, sheet_name="CIE10", index=False)
        l105.to_excel(xw, sheet_name="Lista_105_Colombia", index=False)
        l667.to_excel(xw, sheet_name="Lista_6_67_OPS", index=False)
    log(f"    -> data/CodigosDeMuerte.xlsx  CIE10={len(cie)} L105={len(l105)} L667={len(l667)}")


# --------------------------------------------------------------------------------------
# 3. DIVIPOLA
# --------------------------------------------------------------------------------------
def construir_divipola() -> None:
    log("3/4 DIVIPOLA")

    dep = pd.read_csv(RAW / "divipola_departamentos.csv", dtype=str)
    dep["COD_DPTO"] = dep["cod_dpto"].str.zfill(2)
    dep["NOM_DPTO"] = dep["nom_dpto"]
    dep["LATITUD"] = pd.to_numeric(dep["latitud"], errors="coerce")
    dep["LONGITUD"] = pd.to_numeric(dep["longitud"], errors="coerce")
    departamentos = dep[["COD_DPTO", "NOM_DPTO", "LATITUD", "LONGITUD"]].sort_values("COD_DPTO")

    cp = pd.read_csv(RAW / "divipola_centros.csv", dtype=str)
    cp["COD_DPTO"] = cp["codigo_departamento"].str.zfill(2)
    cp["COD_MUNIC"] = cp["codigo_municipio"].str.zfill(5)
    cp["COD_MUNIC_3"] = cp["codigo_municipio"].str[-3:]
    cp["LATITUD"] = pd.to_numeric(cp["latitud"].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    cp["LONGITUD"] = pd.to_numeric(cp["longitud"].astype(str).str.replace(",", ".", regex=False), errors="coerce")

    # Cabecera municipal (CM) por municipio: una fila por municipio
    cm = cp[cp["tipo_centro_poblado"] == "CM"].copy()
    municipios = (
        cm.groupby(["COD_DPTO", "nombre_departamento", "COD_MUNIC_3", "codigo_municipio", "nombre_municipio"], as_index=False)
        .agg(LATITUD=("LATITUD", "first"), LONGITUD=("LONGITUD", "first"), TIPO=("tipo_centro_poblado", "first"))
        .rename(
            columns={
                "nombre_departamento": "NOM_DPTO",
                "COD_MUNIC_3": "COD_MUNIC",
                "codigo_municipio": "COD_MUNIC_COMPLETO",
                "nombre_municipio": "NOM_MUNIC",
            }
        )
    )
    municipios["TIPO"] = "Cabecera municipal"
    municipios = municipios[["COD_DPTO", "NOM_DPTO", "COD_MUNIC", "COD_MUNIC_COMPLETO", "NOM_MUNIC", "TIPO", "LATITUD", "LONGITUD"]]

    centros = cp[["COD_DPTO", "nombre_departamento", "COD_MUNIC_3", "codigo_municipio", "nombre_municipio",
                  "codigo_centro_poblado", "nombre_centro_poblado", "tipo_centro_poblado", "LATITUD", "LONGITUD"]].rename(
        columns={"nombre_departamento": "NOM_DPTO", "COD_MUNIC_3": "COD_MUNIC",
                 "codigo_municipio": "COD_MUNIC_COMPLETO", "nombre_municipio": "NOM_MUNIC",
                 "codigo_centro_poblado": "COD_CENTRO_POBLADO", "nombre_centro_poblado": "NOM_CENTRO_POBLADO",
                 "tipo_centro_poblado": "TIPO"})

    with pd.ExcelWriter(OUT / "Dipipola.xlsx", engine="openpyxl") as xw:
        departamentos.to_excel(xw, sheet_name="Departamentos", index=False)
        municipios.to_excel(xw, sheet_name="Municipios", index=False)
        centros.to_excel(xw, sheet_name="CentrosPoblados", index=False)
    log(f"    -> data/Dipipola.xlsx  dept={len(departamentos)} mun={len(municipios)} cp={len(centros)}")


# --------------------------------------------------------------------------------------
# 4. Población 2019 + GeoJSON
# --------------------------------------------------------------------------------------
def construir_poblacion() -> None:
    log("4/4 Población municipal 2019 y GeoJSON")

    raw = pd.read_excel(RAW / "PPED-AreaMun-2018-2042_VP.xlsx", sheet_name="PobMunicipalxÁrea", header=7)
    raw.columns = ["COD_DPTO", "NOM_DPTO", "COD_MUNIC", "NOM_MUNIC", "ANO", "AREA", "TOTAL"]
    raw = raw.dropna(subset=["COD_DPTO", "COD_MUNIC", "ANO", "TOTAL"])
    raw["ANO"] = pd.to_numeric(raw["ANO"], errors="coerce")
    raw["TOTAL"] = pd.to_numeric(raw["TOTAL"], errors="coerce")
    raw["COD_MUNIC"] = pd.to_numeric(raw["COD_MUNIC"], errors="coerce").astype("Int64")
    sel = raw[(raw["ANO"] == 2019) & (raw["AREA"].astype(str).str.strip() == "Total")].copy()
    sel["COD_DPTO"] = sel["COD_DPTO"].astype(str).str.zfill(2)
    sel["COD_MUNIC"] = sel["COD_MUNIC"].astype(str).str.zfill(5).str[-3:]
    sel = sel[["COD_DPTO", "NOM_DPTO", "COD_MUNIC", "NOM_MUNIC", "TOTAL"]]
    sel.columns = ["COD_DPTO", "NOM_DPTO", "COD_MUNIC", "NOM_MUNIC", "POBLACION_2019"]
    sel = sel.drop_duplicates(["COD_DPTO", "COD_MUNIC"]).sort_values(["COD_DPTO", "COD_MUNIC"])

    with pd.ExcelWriter(OUT / "Poblacion2019.xlsx", engine="openpyxl") as xw:
        sel.to_excel(xw, sheet_name="Poblacion2019", index=False)
    log(f"    -> data/Poblacion2019.xlsx  municipios={len(sel)}")

    geo_dst = OUT / "geo" / "col_departamentos.geojson"
    geo_dst.parent.mkdir(parents=True, exist_ok=True)
    geo_dst.write_bytes((RAW / "col_departamentos.geojson").read_bytes())
    log(f"    -> data/geo/col_departamentos.geojson")


if __name__ == "__main__":
    t0 = time.time()
    descargar()
    construir_defunciones()
    construir_codigos()
    construir_divipola()
    construir_poblacion()
    log(f"Listo en {time.time()-t0:.0f} s")

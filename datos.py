"""
Capa de datos de la aplicación Dash.

Carga una sola vez los archivos de `data/`, ejecuta los cruces con DIVIPOLA,
CIE-10, lista 105 Colombia y población 2019, y expone agregados listos para
graficar. Todas las cifras de la aplicación salen de este módulo, de modo que
el tablero y el informe (README.md) usan exactamente la misma fuente.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"

MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

SEXOS = {1: "Hombres", 2: "Mujeres", 3: "Sexo no especificado"}

# Categorías y rangos de edad (tabla de referencia de la actividad).
GRUPOS_EDAD = [
    ("00,01,02,03,04", "Mortalidad neonatal", "Menor de 1 mes"),
    ("05,06", "Mortalidad infantil", "1 a 11 meses"),
    ("07,08", "Primera infancia", "1 a 4 años"),
    ("09,10", "Niñez", "5 a 14 años"),
    ("11", "Adolescencia", "15 a 19 años"),
    ("12,13", "Juventud", "20 a 29 años"),
    ("14,15,16", "Adultez temprana", "30 a 44 años"),
    ("17,18,19", "Adultez intermedia", "45 a 59 años"),
    ("20,21,22,23,24", "Vejez", "60 a 84 años"),
    ("25,26,27,28", "Longevidad / Centenarios", "85 a 100+ años"),
    ("29", "Edad desconocida", "Sin información"),
]

# Códigos CIE-10 que la ficha técnica de la actividad asocia a_urban homicide.
COD_HOMICIDIO_105 = "101"                                  # lista 105: Agresiones (homicidios) y secuelas
COD_HOMICIDIO_ARMA_FUEGO = ("X93", "X94", "X95")           # agresión con disparo de arma de fuego


def _cargar_defunciones() -> pd.DataFrame:
    """Carga el microdato curado. Se usa el CSV cuando existe (arranque ~200 veces
    más rápido que abrir el .xlsx); si no, se recurre al .xlsx."""
    csv = DATA / "NoFatal2019.csv"
    if csv.exists():
        df = pd.read_csv(csv, dtype=str, keep_default_na=False)
    else:
        df = pd.read_excel(DATA / "NoFatal2019.xlsx", sheet_name="Defunciones", dtype=str)
    df["COD_DPTO"] = df["COD_DPTO"].str.zfill(2)
    df["COD_MUNIC"] = df["COD_MUNIC"].str.zfill(3)
    df["MES"] = df["MES"].astype(int)
    df["SEXO"] = df["SEXO"].astype(int)
    df["GRUPO_EDAD1"] = df["GRUPO_EDAD1"].str.zfill(2)
    return df


@lru_cache(maxsize=1)
def datos() -> dict:
    """Devuelve el paquete completo de datos y agregados (se calcula una sola vez)."""
    defl = _cargar_defunciones()

    # ---- DIVIPOLA ----------------------------------------------------------------
    mun = pd.read_excel(DATA / "Dipipola.xlsx", sheet_name="Municipios", dtype=str)
    mun["COD_DPTO"] = mun["COD_DPTO"].str.zfill(2)
    mun["COD_MUNIC"] = mun["COD_MUNIC"].str.zfill(3)
    dep = pd.read_excel(DATA / "Dipipola.xlsx", sheet_name="Departamentos", dtype=str)
    dep["COD_DPTO"] = dep["COD_DPTO"].str.zfill(2)

    # ---- Población 2019 ---------------------------------------------------------
    pob = pd.read_excel(DATA / "Poblacion2019.xlsx", sheet_name="Poblacion2019", dtype=str)
    pob["COD_DPTO"] = pob["COD_DPTO"].str.zfill(2)
    pob["COD_MUNIC"] = pob["COD_MUNIC"].str.zfill(3)
    pob["POBLACION_2019"] = pob["POBLACION_2019"].astype(float)

    # ---- CIE-10 y listas ---------------------------------------------------------
    cie = pd.read_excel(DATA / "CodigosDeMuerte.xlsx", sheet_name="CIE10", dtype=str)
    cie["NOMBRE"] = cie["NOMBRE"].str.strip()
    mapa_cie = dict(zip(cie["CODIGO"], cie["NOMBRE"]))

    l105 = pd.read_excel(DATA / "CodigosDeMuerte.xlsx", sheet_name="Lista_105_Colombia", dtype=str)
    l105["CODIGO_LISTA_105"] = l105["CODIGO_LISTA_105"].str.zfill(3)
    mapa_105 = dict(zip(l105["CODIGO_LISTA_105"], l105["CAUSA"]))

    # ---- Cruces -----------------------------------------------------------------
    muni_div = mun[["COD_DPTO", "COD_MUNIC", "NOM_DPTO", "NOM_MUNIC"]].rename(
        columns={"NOM_DPTO": "NOM_DPTO_DIV", "NOM_MUNIC": "NOM_MUNIC_DIV"}
    )
    muni_pob = pob[["COD_DPTO", "COD_MUNIC", "NOM_DPTO", "NOM_MUNIC", "POBLACION_2019"]].rename(
        columns={"NOM_DPTO": "NOM_DPTO_POB", "NOM_MUNIC": "NOM_MUNIC_POB"}
    )
    catalogo = muni_div.merge(muni_pob, on=["COD_DPTO", "COD_MUNIC"], how="outer")
    catalogo["NOM_DPTO"] = catalogo["NOM_DPTO_DIV"].fillna(catalogo["NOM_DPTO_POB"])
    catalogo["NOM_MUNIC"] = catalogo["NOM_MUNIC_DIV"].fillna(catalogo["NOM_MUNIC_POB"])
    catalogo = catalogo.drop(columns=["NOM_DPTO_DIV", "NOM_DPTO_POB", "NOM_MUNIC_DIV", "NOM_MUNIC_POB"])

    defl = defl.merge(
        catalogo[["COD_DPTO", "COD_MUNIC", "NOM_DPTO", "NOM_MUNIC", "POBLACION_2019"]],
        on=["COD_DPTO", "COD_MUNIC"], how="left",
    )
    defl["NOM_DPTO"] = defl["NOM_DPTO"].fillna(
        defl["COD_DPTO"].map(dict(zip(dep["COD_DPTO"], dep["NOM_DPTO"])))
    )

    # Nombre de la causa: se colapsa el código CIE-10 de 4 caracteres a su capítulo
    # de 3 caracteres (de esa forma se agrupan causas como I219 -> I21).
    defl["CAUSA_3"] = defl["CAUSA"].str[:3]
    defl["NOMBRE_CAUSA"] = defl["CAUSA_3"].map(mapa_cie).fillna(defl["CAUSA_3"])
    defl["NOMBRE_CAUSA_105"] = defl["CAUSA_105"].map(mapa_105).fillna("")
    defl["ES_HOMICIDIO"] = defl["CAUSA_105"] == COD_HOMICIDIO_105
    defl["ES_HOMICIDIO_ARMA_FUEGO"] = defl["CAUSA_3"].isin(COD_HOMICIDIO_ARMA_FUEGO)

    mapa_grupo = {}
    for codigos, categoria, rango in GRUPOS_EDAD:
        for c in codigos.split(","):
            mapa_grupo[c] = (categoria, rango)
    defl["CATEGORIA_EDAD"] = defl["GRUPO_EDAD1"].map(lambda c: mapa_grupo.get(c, ("Sin clasificar", ""))[0])
    defl["RANGO_EDAD"] = defl["GRUPO_EDAD1"].map(lambda c: mapa_grupo.get(c, ("", ""))[1])
    defl["NOMBRE_SEXO"] = defl["SEXO"].map(SEXOS).fillna("Sin especificar")

    # ---- Agregados --------------------------------------------------------------
    pob_dep = pob.groupby("COD_DPTO", as_index=False)["POBLACION_2019"].sum()
    pob_dep["NOM_DPTO"] = pob_dep["COD_DPTO"].map(dict(zip(dep["COD_DPTO"], dep["NOM_DPTO"])))

    por_depto = defl.groupby("COD_DPTO", as_index=False).size().rename(columns={"size": "MUERTES"})
    por_depto = por_depto.merge(pob_dep[["COD_DPTO", "NOM_DPTO", "POBLACION_2019"]], on="COD_DPTO", how="left")
    por_depto["NOM_DPTO"] = por_depto["NOM_DPTO"].fillna(
        por_depto["COD_DPTO"].map(dict(zip(dep["COD_DPTO"], dep["NOM_DPTO"])))
    )
    por_depto["TASA_100K"] = por_depto["MUERTES"] / por_depto["POBLACION_2019"] * 100_000

    sexo_depto = defl.pivot_table(
        index=["COD_DPTO", "NOM_DPTO"], columns="NOMBRE_SEXO", values="CAUSA",
        aggfunc="count", fill_value=0,
    ).reset_index()

    por_mes = defl.groupby("MES", as_index=False).size().rename(columns={"size": "MUERTES"})
    por_mes["MES_NOMBRE"] = por_mes["MES"].map(lambda m: MESES[m - 1])

    por_edad = (
        defl.groupby(["GRUPO_EDAD1", "CATEGORIA_EDAD", "RANGO_EDAD"], as_index=False)
        .size().rename(columns={"size": "MUERTES"})
    )
    orden_edad = {c: i for i, (codigos, _, _) in enumerate(GRUPOS_EDAD) for c in codigos.split(",")}
    por_edad["ORDEN"] = por_edad["GRUPO_EDAD1"].map(orden_edad)
    por_edad = por_edad.sort_values("ORDEN")

    por_causa = (
        defl.groupby(["CAUSA_3", "NOMBRE_CAUSA"], as_index=False)
        .size().rename(columns={"size": "MUERTES"})
        .sort_values("MUERTES", ascending=False)
    )
    causa_105_top = (
        defl.groupby(["CAUSA_3", "CAUSA_105"], as_index=False).size()
        .sort_values("size", ascending=False).drop_duplicates("CAUSA_3")
        .set_index("CAUSA_3")["CAUSA_105"].to_dict()
    )
    por_causa["CAUSA_105"] = por_causa["CAUSA_3"].map(causa_105_top)
    por_causa["NOMBRE_CAUSA_105"] = por_causa["CAUSA_105"].map(mapa_105).fillna("")

    # Ciudades: municipios con población y deaths
    ciudad = (
        defl.groupby(["COD_DPTO", "COD_MUNIC", "NOM_DPTO", "NOM_MUNIC"], as_index=False)
        .agg(MUERTES=("CAUSA", "size"), HOMICIDIOS=("ES_HOMICIDIO", "sum"),
             HOMICIDIOS_ARMA=("ES_HOMICIDIO_ARMA_FUEGO", "sum"), POBLACION=("POBLACION_2019", "first"))
    )
    ciudad = ciudad.dropna(subset=["POBLACION"])
    ciudad["TASA_100K"] = ciudad["MUERTES"] / ciudad["POBLACION"] * 100_000
    ciudad["TASA_HOMICIDIO_100K"] = ciudad["HOMICIDIOS"] / ciudad["POBLACION"] * 100_000
    ciudad = ciudad[ciudad["POBLACION"] > 0].copy()

    geo = json.loads((DATA / "geo" / "col_departamentos.geojson").read_text(encoding="utf-8"))

    return {
        "defunciones": defl,
        "por_depto": por_depto,
        "sexo_depto": sexo_depto,
        "por_mes": por_mes,
        "por_edad": por_edad,
        "por_causa": por_causa,
        "ciudad": ciudad,
        "geo": geo,
        "mapa_cie": mapa_cie,
        "mapa_105": mapa_105,
        "departamentos": dep,
        "poblacion": pob,
        "mun": mun,
        "total_nacional": int(len(defl)),
    }


# --------------------------------------------------------------------------------------
# Funciones de filtrado usadas por los callbacks
# --------------------------------------------------------------------------------------
def aplicar_filtros(d: dict, deptos: list[str] | None, sexo: str | None, grupos: list[str] | None) -> pd.DataFrame:
    df = d["defunciones"]
    if deptos:
        df = df[df["COD_DPTO"].isin(deptos)]
    if sexo and sexo != "Todos":
        df = df[df["NOMBRE_SEXO"] == sexo]
    if grupos:
        df = df[df["CATEGORIA_EDAD"].isin(grupos)]
    return df


def recalcular(df: pd.DataFrame, d: dict) -> dict:
    """Recalcula los agregados sobre el subconjunto filtrado."""
    por_depto = df.groupby("COD_DPTO", as_index=False).size().rename(columns={"size": "MUERTES"})
    pob = d["poblacion"].groupby("COD_DPTO", as_index=False)["POBLACION_2019"].sum()
    por_depto = por_depto.merge(pob, on="COD_DPTO", how="left")
    por_depto["NOM_DPTO"] = por_depto["COD_DPTO"].map(dict(zip(d["departamentos"]["COD_DPTO"], d["departamentos"]["NOM_DPTO"])))
    por_depto["TASA_100K"] = por_depto["MUERTES"] / por_depto["POBLACION_2019"] * 100_000

    sexo_depto = df.pivot_table(
        index=["COD_DPTO", "NOM_DPTO"], columns="NOMBRE_SEXO", values="CAUSA",
        aggfunc="count", fill_value=0,
    ).reset_index()

    por_mes = df.groupby("MES", as_index=False).size().rename(columns={"size": "MUERTES"})
    por_mes["MES_NOMBRE"] = por_mes["MES"].map(lambda m: MESES[m - 1])

    por_edad = (
        df.groupby(["GRUPO_EDAD1", "CATEGORIA_EDAD", "RANGO_EDAD"], as_index=False)
        .size().rename(columns={"size": "MUERTES"})
    )
    orden_edad = {c: i for i, (codigos, _, _) in enumerate(GRUPOS_EDAD) for c in codigos.split(",")}
    por_edad["ORDEN"] = por_edad["GRUPO_EDAD1"].map(orden_edad)
    por_edad = por_edad.sort_values("ORDEN")

    por_causa = (
        df.groupby(["CAUSA_3", "NOMBRE_CAUSA"], as_index=False)
        .size().rename(columns={"size": "MUERTES"})
        .sort_values("MUERTES", ascending=False)
    )
    mapa_105 = d["mapa_105"]
    por_causa["NOMBRE_CAUSA_105"] = por_causa["CAUSA_3"].map(
        df.groupby("CAUSA_3")["CAUSA_105"].agg(lambda s: s.mode().iat[0] if len(s.mode()) else "")
    ).map(lambda c: mapa_105.get(c, ""))

    ciudad = (
        df.groupby(["COD_DPTO", "COD_MUNIC", "NOM_DPTO", "NOM_MUNIC"], as_index=False)
        .agg(MUERTES=("CAUSA", "size"), HOMICIDIOS=("ES_HOMICIDIO", "sum"),
             HOMICIDIOS_ARMA=("ES_HOMICIDIO_ARMA_FUEGO", "sum"), POBLACION=("POBLACION_2019", "first"))
    )
    ciudad = ciudad.dropna(subset=["POBLACION"])
    ciudad = ciudad[ciudad["POBLACION"] > 0].copy()
    ciudad["TASA_100K"] = ciudad["MUERTES"] / ciudad["POBLACION"] * 100_000
    ciudad["TASA_HOMICIDIO_100K"] = ciudad["HOMICIDIOS"] / ciudad["POBLACION"] * 100_000

    return {
        "por_depto": por_depto,
        "sexo_depto": sexo_depto,
        "por_mes": por_mes,
        "por_edad": por_edad,
        "por_causa": por_causa,
        "ciudad": ciudad,
    }

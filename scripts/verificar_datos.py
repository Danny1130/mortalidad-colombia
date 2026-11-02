"""
Verificación de consistencia de los datos y de las cifras que muestra la aplicación.

Ejecuta: python scripts/verificar_datos.py
Devuelve código de salida 0 si todo cuadra.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import datos  # noqa: E402

fallos = []


def comprobar(descripcion, condicion, detalle=""):
    estado = "OK " if condicion else "FALLA"
    print(f"[{estado}] {descripcion}{(' -> ' + detalle) if detalle else ''}")
    if not condicion:
        fallos.append(descripcion)


d = datos.datos()
df = d["defunciones"]

comprobar("Total de defunciones = 244.355", len(df) == 244355, f"{len(df):,}")
comprobar("Año 2019 en todas las filas", set(df["ANO"]) == {"2019"}, str(set(df["ANO"])))
comprobar("33 departamentos + Bogotá D.C.", df["COD_DPTO"].nunique() == 33, str(df["COD_DPTO"].nunique()))
comprobar("12 meses completos", sorted(df["MES"].unique().tolist()) == list(range(1, 13)))
comprobar("Sin municipio sin nombre DIVIPOLA", df["NOM_MUNIC"].isna().sum() == 0)
comprobar("Sin municipio sin población 2019", df["POBLACION_2019"].isna().sum() == 0)
comprobar("Suma por sexo = total", df["NOMBRE_SEXO"].value_counts().sum() == len(df))
comprobar("Suma por mes = total", d["por_mes"]["MUERTES"].sum() == len(df))
comprobar("Suma por grupo de edad = total", d["por_edad"]["MUERTES"].sum() == len(df))
comprobar("Suma por departamento = total", d["por_depto"]["MUERTES"].sum() == len(df))
comprobar("Suma por causa = total", d["por_causa"]["MUERTES"].sum() == len(df))

top = d["por_depto"].sort_values("MUERTES", ascending=False).iloc[0]
comprobar("Bogotá D.C. es el departamento con más muertes", top["NOM_DPTO"].startswith("BOGOT"),
          f"{top['NOM_DPTO']} {top['MUERTES']:,}")

causa = d["por_causa"].iloc[0]
comprobar("Primera causa = infarto agudo del miocardio (I21)", causa["CAUSA_3"] == "I21",
          f"{causa['CAUSA_3']} {causa['MUERTES']:,}")

hom = int(df["ES_HOMICIDIO"].sum())
comprobar("Homicidios (lista 105 cat. 101) = 13.055", hom == 13055, f"{hom:,}")

arma = int(df["ES_HOMICIDIO_ARMA_FUEGO"].sum())
comprobar("Homicidios con arma de fuego (X93-X95) = 9.357", arma == 9357, f"{arma:,}")

edad = d["por_edad"].groupby("CATEGORIA_EDAD")["MUERTES"].sum()
comprobar("Mortalidad neonatal (menor de 1 mes) = 4.520", int(edad["Mortalidad neonatal"]) == 4520,
          f"{int(edad['Mortalidad neonatal']):,}")
comprobar("Vejez (60-84 años) = 115.453", int(edad["Vejez"]) == 115453, f"{int(edad['Vejez']):,}")

top5 = d["ciudad"].sort_values("HOMICIDIOS", ascending=False).head(5)["NOM_MUNIC"].str.title().tolist()
comprobar("Las 5 ciudades más violentas son Cali, Bogotá, Medellín, Barranquilla y Cúcuta",
          top5 == ["Santiago De Cali", "Bogotá, D.C.", "Medellín", "Barranquilla", "San José De Cúcuta"],
          " | ".join(top5))

geo = d["geo"]
comprobar("GeoJSON con 33 departamentos", len(geo["features"]) == 33, str(len(geo["features"])))
codigos_geo = {f["properties"]["divipola_dep"] for f in geo["features"]}
comprobar("Los códigos DIVIPOLA del GeoJSON coinciden con los de las defunciones",
          codigos_geo == set(df["COD_DPTO"]))

print()
if fallos:
    print(f"❌ {len(fallos)} verificación(es) fallida(s): {fallos}")
    sys.exit(1)
print("✅ Todas las verificaciones pasaron.")

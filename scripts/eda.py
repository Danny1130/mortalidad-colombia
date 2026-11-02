"""Salida de las cifras clave del informe (README.md). Uso: python scripts/eda.py"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import datos  # noqa: E402

pd.set_option("display.width", 200)
d = datos.datos()
df = d["defunciones"]
total = len(df)
pob = d["poblacion"]["POBLACION_2019"].sum()

print("=" * 78)
print(f"TOTAL NACIONAL DE DEFUNCIONES NO FETALES 2019: {total:,}")
print(f"POBLACIÓN (suma proyecciones municipales 2019): {pob:,.0f}")
print(f"TASA BRUTA NACIONAL: {total / pob * 100_000:,.2f} por 100.000 hab.")
print(f"PROMEDIO DIARIO: {total / 365:,.1f}")
print(f"HOMICIDIOS (lista 105 cat. 101): {int(df['ES_HOMICIDIO'].sum()):,} "
      f"({df['ES_HOMICIDIO'].sum() / total * 100:.1f}%)")
print(f"HOMICIDIOS CON ARMA DE FUEGO (X93-X95): {int(df['ES_HOMICIDIO_ARMA_FUEGO'].sum()):,} "
      f"({df['ES_HOMICIDIO_ARMA_FUEGO'].sum() / df['ES_HOMICIDIO'].sum() * 100:.1f}% de los Asesinatos)")
print()

print("=== POR DEPARTAMENTO (cantidad) ===")
pd_dep = d["por_depto"].sort_values("MUERTES", ascending=False)
print(pd_dep[["NOM_DPTO", "MUERTES", "POBLACION_2019", "TASA_100K"]].head(8).to_string(index=False))
print(f"\nTop 3 departamentos concentran: {pd_dep.head(3)['MUERTES'].sum() / total * 100:.1f}% del total")
print("\n=== POR DEPARTAMENTO (tasa bruta) ===")
print(pd_dep.sort_values("TASA_100K", ascending=False)[["NOM_DPTO", "MUERTES", "TASA_100K"]].head(6).to_string(index=False))
print()

print("=== POR MES ===")
mes = d["por_mes"].copy()
dias = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
mes["DIAS"] = dias
mes["POR_DIA"] = mes["MUERTES"] / mes["DIAS"]
mes["TASA_MENSUAL_100K"] = mes["MUERTES"] / (pob / 12) * 100_000
print(mes.to_string(index=False))
print(f"Máximo: {mes.loc[mes['MUERTES'].idxmax(), 'MES_NOMBRE']} · "
      f"Mínimo: {mes.loc[mes['MUERTES'].idxmin(), 'MES_NOMBRE']}")
print(f"Máximo por día: {mes.loc[mes['POR_DIA'].idxmax(), 'MES_NOMBRE']} ({mes['POR_DIA'].max():,.0f}/día) · "
      f"Mínimo por día: {mes.loc[mes['POR_DIA'].idxmin(), 'MES_NOMBRE']} ({mes['POR_DIA'].min():,.0f}/día)")
print()

print("=== CAUSAS (CIE-10, 3 caracteres) ===")
pc = d["por_causa"].head(12).copy()
pc["PART_%"] = pc["MUERTES"] / total * 100
print(pc[["CAUSA_3", "NOMBRE_CAUSA", "NOMBRE_CAUSA_105", "MUERTES", "PART_%"]].to_string(index=False))
print(f"\nLas 10 primeras causas explican {pc.head(10)['MUERTES'].sum() / total * 100:.1f}% de las muertes")
causas_105 = (
    df.groupby("CAUSA_105").size().sort_values(ascending=False).head(10)
    .to_frame("MUERTES")
)
causas_105["CAUSA"] = [d["mapa_105"].get(c, "") for c in causas_105.index]
causas_105["PART_%"] = causas_105["MUERTES"] / total * 100
print("\n=== LISTA 105 COLOMBIA (top 10) ===")
print(causas_105.to_string())
print()

print("=== SEXO ===")
sexo = df["NOMBRE_SEXO"].value_counts()
for k, v in sexo.items():
    print(f"{k}: {v:,} ({v / total * 100:.1f}%)")
print(f"Ratio hombres/mujeres: {sexo['Hombres'] / sexo['Mujeres']:.2f}")
print()

print("=== CICLO DE VIDA (GRUPO_EDAD1) ===")
edad = (
    df.groupby("CATEGORIA_EDAD").size().sort_values(ascending=False).to_frame("MUERTES")
)
edad["PART_%"] = edad["MUERTES"] / total * 100
print(edad.to_string())
print()

print("=== 5 CIUDADES MÁS VIOLENTAS (homicidios, lista 105) ===")
ciudad = d["ciudad"]
top = ciudad.sort_values("HOMICIDIOS", ascending=False).head(5)
print(top[["NOM_DPTO", "NOM_MUNIC", "HOMICIDIOS", "HOMICIDIOS_ARMA", "TASA_HOMICIDIO_100K", "MUERTES"]].to_string(index=False))
print("\nTasa de homicidio por 100.000 hab. (top 5 por número):")
print(top[["NOM_MUNIC", "TASA_HOMICIDIO_100K"]].to_string(index=False))
print()

print("=== 10 CIUDADES CON MENOR TASA BRUTA (población >= 50.000) ===")
bajo = ciudad[ciudad["POBLACION"] >= 50000].sort_values("TASA_100K").head(10)
print(bajo[["NOM_DPTO", "NOM_MUNIC", "MUERTES", "POBLACION", "TASA_100K"]].to_string(index=False))
print("\nSin umbral de población (los 10 municipios con menos muertes):")
print(ciudad.sort_values("TASA_100K").head(10)[["NOM_MUNIC", "MUERTES", "POBLACION", "TASA_100K"]].to_string(index=False))
print()

print("=== COHERENCIA DE LA MUESTRA ===")
print(f"Municipios con defunciones: {df.groupby(['COD_DPTO', 'COD_MUNIC']).ngroups}")
print(f"Municipios con población 2019: {d['poblacion'].groupby(['COD_DPTO', 'COD_MUNIC']).ngroups}")
print(f"Defunciones sin municipio DIVIPOLA: {df['NOM_MUNIC'].isna().sum()}")
print(f"Defunciones sin población: {df['POBLACION_2019'].isna().sum()}")

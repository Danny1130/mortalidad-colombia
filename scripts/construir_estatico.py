"""
Genera una versión estática (HTML autónomo) del tablero, con los mismos gráficos
interactivos de Plotly.js. Sirve como publicación pública de respaldo y como
demostración ejecutable sin conexión.

Uso: python scripts/construir_estatico.py [carpeta_destino]
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import datos  # noqa: E402

DESTINO = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site"
DESTINO.mkdir(parents=True, exist_ok=True)

d = datos.datos()
df = d["defunciones"]
total = len(df)
pob = d["poblacion"]["POBLACION_2019"].sum()

NAVY = "#0d2340"
GOLD = "#f2b134"
ROJO = "#b3261e"
GRIS = "#5b6b7c"
PALETA_SEXO = {"Hombres": "#1f4e79", "Mujeres": "#d1495b", "Sexo no especificado": "#9aa5b1"}


def fmt(n):
    return f"{n:,.0f}".replace(",", ".")


def base(fig, altura):
    fig.update_layout(
        template="plotly_white",
        font=dict(family="Inter, Segoe UI, system-ui, sans-serif", size=13, color="#1f2d3d"),
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=20, b=10),
        hoverlabel=dict(font_size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        height=altura,
    )
    return fig


# ------------------------------------------------------------------ indicadores
por_depto = d["por_depto"].sort_values("MUERTES", ascending=False)
por_mes = d["por_mes"]
por_edad = (
    df.groupby(["CATEGORIA_EDAD", "RANGO_EDAD"], as_index=False).size().rename(columns={"size": "MUERTES"})
)
orden = {c: i for i, (codigos, _, _) in enumerate(datos.GRUPOS_EDAD) for c in codigos.split(",")}
por_edad["ORDEN"] = por_edad["CATEGORIA_EDAD"].map(
    {c: i for i, (codigos, _, _) in enumerate(datos.GRUPOS_EDAD) for c in codigos.split(",")}
)
por_edad = por_edad.sort_values("ORDEN")
por_causa = d["por_causa"].head(10)
ciudad = d["ciudad"]
top5 = ciudad.sort_values("HOMICIDIOS", ascending=False).head(5).copy()
bajo = ciudad[ciudad["POBLACION"] >= 50000].sort_values("TASA_100K").head(10).copy()
bajo = bajo.sort_values("TASA_100K", ascending=False)
sexo_depto = d["sexo_depto"].copy()
sexo_depto["TOTAL"] = sexo_depto[[c for c in sexo_depto.columns if c in PALETA_SEXO]].sum(axis=1)
sexo_depto = sexo_depto.sort_values("TOTAL")

pico = por_mes.loc[por_mes["MUERTES"].idxmax()]
minimo = por_mes.loc[por_mes["MUERTES"].idxmin()]

# ----------------------------------------------------------------------- mapa
fig_mapa = go.Figure(
    go.Choropleth(
        geojson=d["geo"],
        locations=por_depto["COD_DPTO"].tolist(),
        z=por_depto["MUERTES"].tolist(),
        zmin=0,
        zmax=float(por_depto["MUERTES"].max()),
        featureidkey="properties.divipola_dep",
        colorscale="YlOrRd",
        marker_line_color="white",
        marker_line_width=0.7,
        colorbar=dict(title=dict(text="Defunciones", side="right"), outlinewidth=0),
        customdata=list(
            zip(
                por_depto["NOM_DPTO"].str.title(),
                por_depto["MUERTES"].map(fmt),
                por_depto["TASA_100K"].map(lambda v: f"{v:,.1f}".replace(",", ".")),
            )
        ),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>Defunciones: %{customdata[1]}<br>"
            "Tasa por 100.000 hab.: %{customdata[2]}<extra></extra>"
        ),
    )
)
fig_mapa.update_geos(fitbounds="locations", visible=False, bgcolor="white")
fig_mapa.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=520)
fig_mapa = base(fig_mapa, 520)

# ------------------------------------------------------------------- líneas
fig_mes = go.Figure()
fig_mes.add_trace(
    go.Scatter(
        x=por_mes["MES_NOMBRE"],
        y=por_mes["MUERTES"],
        mode="lines+markers+text",
        line=dict(color=NAVY, width=3),
        marker=dict(size=9, color=GOLD, line=dict(color=NAVY, width=1.5)),
        text=[fmt(v) for v in por_mes["MUERTES"]],
        textposition="top center",
        textfont=dict(size=10, color=GRIS),
        customdata=list(zip(por_mes["MUERTES"].map(fmt),)),
        hovertemplate="<b>%{x}</b><br>Muertes: %{customdata[0]}<extra></extra>",
    )
)
fig_mes.add_annotation(
    x=pico["MES_NOMBRE"], y=pico["MUERTES"], text="máximo", showarrow=False, yshift=28,
    font=dict(size=11, color=ROJO),
)
fig_mes.add_annotation(
    x=minimo["MES_NOMBRE"], y=minimo["MUERTES"], text="mínimo", showarrow=False, yshift=-26,
    font=dict(size=11, color="#1b7f79"),
)
fig_mes.update_layout(
    xaxis=dict(title="Mes de la defunción", showgrid=False),
    yaxis=dict(title="Número de muertes", gridcolor="#eef2f6", rangemode="tozero"),
    showlegend=False,
)
fig_mes = base(fig_mes, 380)

# ------------------------------------------------------------------- barras
top5["NOM_MUNIC_T"] = top5["NOM_MUNIC"].str.title()
top5 = top5.sort_values("HOMICIDIOS")
top5["ETIQUETA"] = top5["NOM_MUNIC_T"] + " · " + top5["HOMICIDIOS"].map(fmt)
fig_ciudad = px.bar(
    top5,
    x="HOMICIDIOS",
    y="NOM_MUNIC_T",
    orientation="h",
    color="HOMICIDIOS",
    color_continuous_scale=[[0, "#e9a09a"], [1, "#8c1d18"]],
    labels={"HOMICIDIOS": "Número de muertes por agresión", "NOM_MUNIC_T": ""},
)
fig_ciudad.update_traces(
    marker_line_width=0,
    text=top5["ETIQUETA"],
    textposition="outside",
    textfont=dict(size=11, color=NAVY),
    cliponaxis=False,
    customdata=list(
        zip(
            top5["HOMICIDIOS"].map(fmt),
            top5["MUERTES"].map(fmt),
            top5["POBLACION"].map(fmt),
            top5["TASA_HOMICIDIO_100K"].map(lambda v: f"{v:,.1f}".replace(",", ".")),
        )
    ),
    hovertemplate=(
        "<b>%{y}</b><br>Homicidios: %{customdata[0]}<br>Total de muertes: %{customdata[1]}<br>"
        "Población 2019: %{customdata[2]}<br>Tasa por 100.000 hab.: %{customdata[3]}<extra></extra>"
    ),
)
fig_ciudad.update_layout(
    xaxis=dict(title="Número de muertes por agresión", gridcolor="#eef2f6", rangemode="tozero",
               range=[0, float(top5["HOMICIDIOS"].max()) * 1.32]),
    yaxis=dict(title="", tickfont=dict(size=12)),
    coloraxis_showscale=False,
    showlegend=False,
    margin=dict(l=10, r=150, t=20, b=10),
)
fig_ciudad = base(fig_ciudad, 380)

# ------------------------------------------------------------------ circular
fig_pie = go.Figure(
    go.Pie(
        labels=bajo["NOM_MUNIC"].str.title(),
        values=bajo["TASA_100K"],
        hole=0.45,
        sort=False,
        direction="clockwise",
        domain=dict(x=[0.07, 0.93], y=[0.12, 0.96]),
        marker=dict(
            colors=["#0d2340", "#1b4d6e", "#2a6f97", "#40916c", "#52b788",
                    "#74c69d", "#95d5b2", "#b7e4c7", "#d8f3dc", "#bde0fe"][: len(bajo)],
            line=dict(color="white", width=1.5),
        ),
        customdata=list(
            zip(
                bajo["MUERTES"].map(fmt),
                bajo["POBLACION"].map(fmt),
                bajo["TASA_100K"].map(lambda v: f"{v:,.1f}".replace(",", ".")),
            )
        ),
        hovertemplate=(
            "<b>%{label}</b><br>Tasa bruta: %{customdata[2]} por 100.000 hab.<br>"
            "Defunciones: %{customdata[0]}<br>Población 2019: %{customdata[1]}<extra></extra>"
        ),
        textinfo="label+percent",
        textposition="outside",
        textfont=dict(size=11, color=NAVY),
        insidetextorientation="radial",
    )
)
fig_pie.update_layout(
    margin=dict(l=40, r=40, t=30, b=150),
    uniformtext_minsize=9,
    legend=dict(orientation="h", yanchor="top", y=-0.02, xanchor="center", x=0.5, font=dict(size=10)),
)
fig_pie = base(fig_pie, 560)

# --------------------------------------------------------------- apiladas
registros = []
for fila in sexo_depto.to_dict("records"):
    for col in [c for c in sexo_depto.columns if c in PALETA_SEXO]:
        registros.append(
            {
                "NOM_DPTO": fila["NOM_DPTO"],
                "Sexo": col,
                "MUERTES": fila[col],
                "F_MUERTES": fmt(fila[col]),
            }
        )
sexo_long = __import__("pandas").DataFrame(registros)
fig_sexo = px.bar(
    sexo_long,
    x="MUERTES",
    y="NOM_DPTO",
    color="Sexo",
    orientation="h",
    barmode="stack",
    color_discrete_map=PALETA_SEXO,
    labels={"NOM_DPTO": "", "MUERTES": "Defunciones"},
    category_orders={"NOM_DPTO": sexo_depto["NOM_DPTO"].tolist()},
)
fig_sexo.update_traces(
    marker_line_width=0,
    customdata=list(zip(sexo_long["F_MUERTES"],)),
    hovertemplate="<b>%{y}</b><br>%{fullData.name}: %{customdata[0]}<extra></extra>",
)
fig_sexo.update_layout(
    xaxis=dict(title="Defunciones", gridcolor="#eef2f6"),
    yaxis=dict(title="", tickfont=dict(size=11)),
    barmode="stack",
    margin=dict(l=10, r=20, t=30, b=10),
    legend=dict(title_text="", orientation="h", yanchor="bottom", y=1.01, x=0),
)
fig_sexo = base(fig_sexo, 760)

# ---------------------------------------------------------------- histograma
por_edad["ETIQUETA"] = por_edad["CATEGORIA_EDAD"] + " (" + por_edad["RANGO_EDAD"] + ")"
por_edad["PORC"] = por_edad["MUERTES"] / total * 100
fig_edad = px.bar(
    por_edad,
    x="ETIQUETA",
    y="MUERTES",
    color="MUERTES",
    color_continuous_scale=[[0, "#dbeafe"], [0.5, "#24476f"], [1, NAVY]],
    labels={"ETIQUETA": "Grupo de edad (GRUPO_EDAD1)", "MUERTES": "Defunciones"},
)
fig_edad.update_traces(
    text=[fmt(v) for v in por_edad["MUERTES"]],
    textposition="outside",
    textfont=dict(size=11, color=NAVY),
    marker_line_width=0,
    cliponaxis=False,
    customdata=list(
        zip(
            por_edad["MUERTES"].map(fmt),
            por_edad["PORC"].map(lambda v: f"{v:,.2f}%".replace(",", ".")),
        )
    ),
    hovertemplate="<b>%{x}</b><br>Defunciones: %{customdata[0]}<br>Participación: %{customdata[1]}<extra></extra>",
)
fig_edad.update_layout(
    xaxis=dict(title="", tickangle=-20, tickfont=dict(size=11)),
    yaxis=dict(title="Defunciones", gridcolor="#eef2f6", rangemode="tozero"),
    coloraxis_showscale=False,
    margin=dict(l=10, r=20, t=30, b=10),
)
fig_edad = base(fig_edad, 420)

# -------------------------------------------------------------------- tabla
filas = "".join(
    f"<tr><td class='cod'>{r.CAUSA_3}</td><td>{r.NOMBRE_CAUSA}</td>"
    f"<td class='c105'>{r.NOMBRE_CAUSA_105}</td><td class='num'>{fmt(r.MUERTES)}</td>"
    f"<td class='num'>{r.MUERTES / total * 100:.2f} %</td></tr>"
    for r in por_causa.itertuples()
)

# --------------------------------------------------------------------- KPIs
kpis = [
    ("Muertes registradas", fmt(total), "defunciones no fetales EEVV 2019"),
    ("Promedio diario", fmt(total / 365), "muertes / día (365 días)"),
    ("Tasa bruta nacional", f"{total / pob * 100_000:,.1f}".replace(",", "."), "por 100.000 habitantes"),
    ("Mes con más muertes", pico["MES_NOMBRE"], f"{fmt(pico['MUERTES'])} muertes"),
    ("Homicidios", fmt(int(df['ES_HOMICIDIO'].sum())), "lista 105 Colombia, categoría 101"),
]
kpi_html = "".join(
    f"<div class='kpi'><div class='kpi-titulo'>{t}</div><div class='kpi-valor'>{v}</div>"
    f"<div class='kpi-nota'>{n}</div></div>"
    for t, v, n in kpis
)

css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
# Plotly.js embebido: la página funciona sin conexión a un CDN
from plotly.offline import get_plotlyjs
plotly_js = get_plotlyjs()


def div(fig, identificador):
    return pio.to_html(
        fig,
        include_plotlyjs=False,
        full_html=False,
        div_id=identificador,
        config={"displayModeBar": True, "displaylogo": False, "responsive": True},
    )


html_doc = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mortalidad en Colombia 2019 · Tablero interactivo</title>
<meta name="description" content="Análisis interactivo de la mortalidad en Colombia 2019 con microdatos del DANE (Estadísticas Vitales).">
<style>{css}</style>
<script>{plotly_js}</script>
</head>
<body>
<div class="app">
  <header class="header">
    <div class="header-texto">
      <div class="kicker">DANE · Estadísticas Vitales 2019</div>
      <h1>Mortalidad en Colombia, 2019</h1>
      <p class="subtitulo">Tablero interactivo de análisis de las {fmt(total)} defunciones no fetales
      registradas en el país, con lectura territorial, demográfica y por causa de muerte.</p>
    </div>
    <div class="header-datos">
      <div><div class="header-dato-num">{fmt(total)}</div><div class="header-dato-lab">defunciones no fetales</div></div>
      <div><div class="header-dato-num">32</div><div class="header-dato-lab">departamentos + Bogotá D.C.</div></div>
      <div><div class="header-dato-num">12</div><div class="header-dato-lab">meses analizados</div></div>
    </div>
  </header>

  <main class="contenido">
    <div class="kpis">{kpi_html}</div>

    <div class="grid">
      <section class="card col-12">
        <div class="card-cabecera">
          <h2 class="card-titulo">Mapa coroplético · muertes por departamento</h2>
          <p class="card-subtitulo">Distribución del total de defunciones según el departamento donde
          ocurrió la defunción. Pase el cursor sobre cada departamento para ver el detalle.</p>
        </div>
        <div class="card-cuerpo">{div(fig_mapa, "mapa")}</div>
        <div class="nota-fuente">Fuente: DANE, EEVV 2019 (catálogo 696). Población: proyecciones
        municipales CNPV 2018 (DANE).</div>
      </section>

      <section class="card col-6">
        <div class="card-cabecera">
          <h2 class="card-titulo">Gráfico de líneas · muertes por mes</h2>
          <p class="card-subtitulo">Evolución mensual de las defunciones durante 2019: estacionalidad
          y picos de mortalidad del año.</p>
        </div>
        <div class="card-cuerpo">{div(fig_mes, "mes")}</div>
        <div class="nota-fuente">Fuente: DANE, EEVV 2019. Cada punto representa el total de muertes del mes.</div>
      </section>

      <section class="card col-6">
        <div class="card-cabecera">
          <h2 class="card-titulo">Gráfico de barras · las 5 ciudades más violentas</h2>
          <p class="card-subtitulo">Defunciones por agresión (homicidio) en las cinco ciudades con
          mayor número de casos registrados en 2019.</p>
        </div>
        <div class="card-cuerpo">{div(fig_ciudad, "ciudad")}</div>
        <div class="nota-fuente">Homicidio = lista 105 Colombia, categoría 101 «Agresiones (homicidios) y
        secuelas» (CIE-10 X85–Y09, Y87.1). Fuente: DANE, EEVV 2019.</div>
      </section>

      <section class="card col-6">
        <div class="card-cabecera">
          <h2 class="card-titulo">Gráfico circular · 10 ciudades con menor índice de mortalidad</h2>
          <p class="card-subtitulo">Participación de las diez ciudades con la tasa bruta de mortalidad
          más baja (defunciones por 100.000 habitantes), con población mínima de 50.000 habitantes.</p>
        </div>
        <div class="card-cuerpo">{div(fig_pie, "pie")}</div>
        <div class="nota-fuente">Tasa bruta de mortalidad = muertes del municipio ÷ población proyectada
        2019 × 100.000. Fuente: DANE, EEVV 2019 y proyecciones CNPV 2018.</div>
      </section>

      <section class="card col-6">
        <div class="card-cabecera">
          <h2 class="card-titulo">Tabla · las 10 principales causas de muerte</h2>
          <p class="card-subtitulo">Códigos CIE-10, nombre oficial de la causa y total de defunciones,
          ordenados de mayor a menor.</p>
        </div>
        <div class="card-cuerpo">
          <div class="dash-table-container">
            <table class="tabla">
              <thead><tr><th>Código CIE-10</th><th>Causa de muerte</th><th>Categoría lista 105 Colombia</th>
              <th class="num">Muertes</th><th class="num">% del total</th></tr></thead>
              <tbody>{filas}</tbody>
            </table>
          </div>
        </div>
        <div class="nota-fuente">Causa básica de defunción según la CIE-10 OPS/OMS versión 2019 (DANE).</div>
      </section>

      <section class="card col-12">
        <div class="card-cabecera">
          <h2 class="card-titulo">Gráfico de barras apiladas · muertes por sexo y departamento</h2>
          <p class="card-subtitulo">Comparación de las defunciones de hombres y mujeres en cada uno de
          los 32 departamentos y Bogotá D.C.</p>
        </div>
        <div class="card-cuerpo">{div(fig_sexo, "sexo")}</div>
        <div class="nota-fuente">Fuente: DANE, EEVV 2019. Cifras absolutas de defunciones no fetales.</div>
      </section>

      <section class="card col-12">
        <div class="card-cabecera">
          <h2 class="card-titulo">Histograma · distribución de muertes por ciclo de vida (GRUPO_EDAD1)</h2>
          <p class="card-subtitulo">Agrupación de la variable GRUPO_EDAD1 en los once rangos de la
          tabla de referencia, para leer el patrón de mortalidad a lo largo del ciclo de vida.</p>
        </div>
        <div class="card-cuerpo">{div(fig_edad, "edad")}</div>
        <div class="nota-fuente">Fuente: DANE, EEVV 2019. Rangos: neonatal, infantil, primera infancia,
        niñez, adolescencia, juventud, adultez temprana, adultez intermedia, vejez, longevidad y edad
        desconocida.</div>
      </section>
    </div>
  </main>

  <footer class="footer">
    <div class="footer-col">
      <strong>Fuentes</strong>
      <ul>
        <li>DANE, Estadísticas Vitales 2019 (defunciones no fetales), microdatos catálogo 696.</li>
        <li>DANE, CIE-10 OPS/OMS versión 2019 y listas 105 Colombia / 6/67 OPS.</li>
        <li>DANE, DIVIPOLA (datos abiertos) y proyecciones de población municipal CNPV 2018.</li>
      </ul>
    </div>
    <div class="footer-col">
      <strong>Notas metodológicas</strong>
      <ul>
        <li>La defunción se asigna al departamento y municipio donde ocurrió (lugar de ocurrencia).</li>
        <li>Tasa bruta de mortalidad = muertes ÷ población proyectada 2019 × 100.000 habitantes.</li>
        <li>Homicidio = lista 105 Colombia, categoría 101 (CIE-10 X85–Y09, Y87.1).</li>
        <li>Los totales pueden variar levemente frente a publicaciones del DANE por ajustes de cobertura.</li>
      </ul>
    </div>
    <div class="footer-col">
      <strong>Proyecto</strong>
      <p>Actividad 4 · Aplicación web interactiva para el análisis de mortalidad en Colombia.</p>
      <p>Desarrollado con Python, Dash y Plotly. Datos abiertos del DANE.</p>
    </div>
  </footer>
</div>
<style>
.tabla {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
.tabla th {{ background: {NAVY}; color: #fff; text-align: left; padding: 9px 12px; font-weight: 600; }}
.tabla td {{ padding: 9px 12px; border-bottom: 1px solid #e6ebf0; vertical-align: top; }}
.tabla tbody tr:nth-child(odd) {{ background: #f7f9fb; }}
.tabla .num {{ text-align: right; white-space: nowrap; }}
.tabla .cod {{ font-weight: 600; color: {NAVY}; white-space: nowrap; }}
.tabla .c105 {{ color: #5b6b7c; }}
</style>
</body>
</html>
"""

(DESTINO / "index.html").write_text(html_doc, encoding="utf-8")
print(f"OK -> {DESTINO / 'index.html'} ({(DESTINO / 'index.html').stat().st_size / 1e6:.2f} MB)")

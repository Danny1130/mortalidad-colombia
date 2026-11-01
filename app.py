"""
Aplicación web interactiva para el análisis de mortalidad en Colombia (2019).

Dash + Plotly sobre los microdatos de defunciones no fetales EEVV 2019 (DANE).

Ejecución local:
    python app.py
Producción (PaaS):
    gunicorn app:server -b 0.0.0.0:$PORT
"""

from __future__ import annotations

import io
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dash_table, dcc, html, no_update

import datos

# --------------------------------------------------------------------------------------
# Paleta y ajustes generales
# --------------------------------------------------------------------------------------
NAVY = "#0d2340"
NAVY_SOFT = "#24476f"
GOLD = "#f2b134"
TEAL = "#1b7f79"
ROJO = "#b3261e"
GRIS = "#5b6b7c"
GRIS_SUAVE = "#eef2f6"
PALETA_SEXO = {"Hombres": "#1f4e79", "Mujeres": "#d1495b", "Sexo no especificado": "#9aa5b1"}

d = datos.datos()

app = Dash(
    __name__,
    title="Mortalidad en Colombia 2019",
    update_title="Actualizando…",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server

# --------------------------------------------------------------------------------------
# Piezas reutilizables
# --------------------------------------------------------------------------------------
def kpi_card(titulo, valor_id, nota=""):
    return html.Div(
        [
            html.Div(titulo.upper(), className="kpi-titulo"),
            html.Div(id=valor_id, className="kpi-valor"),
            html.Div(nota, className="kpi-nota"),
        ],
        className="kpi",
    )


def tarjeta(titulo, subtitulo, cuerpo, extra=None, clase="card col-6"):
    return html.Section(
        [
            html.Div(
                [
                    html.H2(titulo, className="card-titulo"),
                    html.P(subtitulo, className="card-subtitulo"),
                ],
                className="card-cabecera",
            ),
            html.Div(cuerpo, className="card-cuerpo"),
            extra if extra else None,
        ],
        className=clase,
    )


def pie_nota(texto):
    return html.Div(texto, className="nota-fuente")


def _estilo(fig, titulo=None, altura=None, leyenda=None):
    m = fig.layout.margin
    margenes = dict(l=10, r=10, t=30 if titulo else 10, b=10)
    if not all(v is None for v in (m.l, m.r, m.t, m.b)):
        margenes = dict(l=m.l, r=m.r, t=m.t, b=m.b)
    fig.update_layout(
        template="plotly_white",
        font=dict(family="Inter, Segoe UI, system-ui, sans-serif", size=13, color="#1f2d3d"),
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=margenes,
        hoverlabel=dict(font_size=13),
        legend=leyenda or dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    if titulo:
        fig.update_layout(title=dict(text=titulo, x=0.01, xanchor="left", font=dict(size=16, color=NAVY)))
    if altura:
        fig.update_layout(height=altura)
    return fig


# --------------------------------------------------------------------------------------
# Filtros
# --------------------------------------------------------------------------------------
opciones_depto = [
    {"label": f"{r.NOM_DPTO.title()} ({r.COD_DPTO})", "value": r.COD_DPTO}
    for r in d["departamentos"].itertuples()
]
opciones_edad = [{"label": f"{cat} · {ran}", "value": cat} for _, cat, ran in datos.GRUPOS_EDAD]

barra_filtros = html.Div(
    [
        html.Div(
            [
                html.Label("Departamento", htmlFor="f-depto"),
                dcc.Dropdown(
                    id="f-depto",
                    options=opciones_depto,
                    value=[],
                    multi=True,
                    placeholder="Todos los departamentos (32 + Bogotá D.C.)",
                    className="dropdown",
                ),
            ],
            className="filtro",
        ),
        html.Div(
            [
                html.Label("Sexo", htmlFor="f-sexo"),
                dcc.RadioItems(
                    id="f-sexo",
                    options=[
                        {"label": "Todos", "value": "Todos"},
                        {"label": "Hombres", "value": "Hombres"},
                        {"label": "Mujeres", "value": "Mujeres"},
                    ],
                    value="Todos",
                    inline=True,
                    className="radio",
                ),
            ],
            className="filtro",
        ),
        html.Div(
            [
                html.Label("Ciclo de vida (GRUPO_EDAD1)", htmlFor="f-edad"),
                dcc.Dropdown(
                    id="f-edad",
                    options=opciones_edad,
                    value=[],
                    multi=True,
                    placeholder="Todos los grupos de edad",
                    className="dropdown",
                ),
            ],
            className="filtro filtro-ancho",
        ),
        html.Div(
            [
                html.Button("Restablecer filtros", id="btn-reset", n_clicks=0, className="btn-reset"),
                html.Button("Descargar CSV", id="btn-descargar", n_clicks=0, className="btn-descargar"),
                dcc.Download(id="descarga"),
            ],
            className="filtro acciones",
        ),
    ],
    className="barra-filtros",
)

# --------------------------------------------------------------------------------------
# Indicadores (KPI)
# --------------------------------------------------------------------------------------
kpis = html.Div(
    [
        kpi_card("Muertes registradas", "kpi-total", "defunciones no fetales EEVV 2019"),
        kpi_card("Participación del filtro", "kpi-share", "sobre el total nacional"),
        kpi_card("Promedio diario", "kpi-diario", "muertes / día (365 días)"),
        kpi_card("Mes con más muertes", "kpi-pico", "mes de mayor número de muertes en 2019"),
        kpi_card("Tasa bruta del ámbito", "kpi-tasa", "muertes por 100.000 habitantes"),
    ],
    className="kpis",
)

# --------------------------------------------------------------------------------------
# Gráficos
# --------------------------------------------------------------------------------------
g_mapa = dcc.Graph(id="g-mapa", config={"displayModeBar": True, "displaylogo": False})
g_mes = dcc.Graph(id="g-mes", config={"displayModeBar": False})
g_ciudad = dcc.Graph(id="g-ciudad", config={"displayModeBar": False})
g_pie = dcc.Graph(id="g-pie", config={"displayModeBar": False})
g_sexo = dcc.Graph(id="g-sexo", config={"displayModeBar": False})
g_edad = dcc.Graph(id="g-edad", config={"displayModeBar": False})

tabla_causas = dash_table.DataTable(
    id="t-causas",
    columns=[
        {"name": "Código CIE-10", "id": "codigo", "type": "text"},
        {"name": "Causa de muerte", "id": "causa", "type": "text"},
        {"name": "Categoría lista 105 Colombia", "id": "causa105", "type": "text"},
        {"name": "Muertes", "id": "muertes", "type": "numeric"},
        {"name": "% del total", "id": "participacion", "type": "numeric"},
    ],
    data=[],
    sort_action="native",
    page_size=10,
    style_as_list_view=True,
    style_cell={
        "fontFamily": "Inter, Segoe UI, system-ui, sans-serif",
        "fontSize": "13px",
        "textAlign": "left",
        "padding": "9px 12px",
        "border": "1px solid #e6ebf0",
        "maxWidth": "460px",
        "whiteSpace": "normal",
    },
    style_header={
        "backgroundColor": NAVY,
        "color": "white",
        "fontWeight": "600",
        "border": "none",
        "textAlign": "left",
    },
    style_data_conditional=[
        {"if": {"row_index": "odd"}, "backgroundColor": "#f7f9fb"},
        {"if": {"column_id": "muertes"}, "textAlign": "right"},
        {"if": {"column_id": "participacion"}, "textAlign": "right", "format": {"specifier": ".2f"}},
    ],
    export_format="csv",
)

# --------------------------------------------------------------------------------------
# Composición de la página
# --------------------------------------------------------------------------------------
app.layout = html.Div(
    [
        html.Header(
            [
                html.Div(
                    [
                        html.Div("DANE · Estadísticas Vitales 2019", className="kicker"),
                        html.H1("Mortalidad en Colombia, 2019"),
                        html.P(
                            "Tablero interactivo de análisis de las 244.355 defunciones no fetales "
                            "registradas en el país, con lectura territorial, demográfica y por causa "
                            "de muerte.",
                            className="subtitulo",
                        ),
                    ],
                    className="header-texto",
                ),
                html.Div(
                    [
                        html.Div("244.355", className="header-dato-num"),
                        html.Div("defunciones no fetales", className="header-dato-lab"),
                        html.Div("32", className="header-dato-num"),
                        html.Div("departamentos + Bogotá D.C.", className="header-dato-lab"),
                        html.Div("12", className="header-dato-num"),
                        html.Div("meses analizados", className="header-dato-lab"),
                    ],
                    className="header-datos",
                ),
            ],
            className="header",
        ),
        html.Main(
            [
                html.Section(
                    [
                        html.H2("Filtros de exploración", className="seccion-titulo"),
                        barra_filtros,
                        html.Div(id="aviso-seleccion", className="aviso"),
                    ],
                    className="bloque",
                ),
                kpis,
                html.Div(
                    [
                        tarjeta(
                            "Mapa coroplético · muertes por departamento",
                            "Distribución del total de defunciones según el departamento donde ocurrió la defunción. "
                            "Haga clic en un departamento para filtrar el tablero.",
                            g_mapa,
                            extra=html.Div(
                                [
                                    dcc.RadioItems(
                                        id="f-mapa",
                                        options=[
                                            {"label": "Total de muertes", "value": "muertes"},
                                            {"label": "Tasa por 100.000 habitantes", "value": "tasa"},
                                        ],
                                        value="muertes",
                                        inline=True,
                                        className="radio radio-compacto",
                                    ),
                                    pie_nota(
                                        "Fuente: DANE, EEVV 2019 (catálogo 696). Población: proyecciones "
                                        "municipales CNPV 2018 (DANE)."
                                    ),
                                ],
                                className="card-pie",
                            ),
                            clase="card col-12",
                        ),
                        tarjeta(
                            "Gráfico de líneas · muertes por mes",
                            "Evolución mensual de las defunciones durante 2019: permite ver la estacionalidad "
                            "y los picos de mortalidad del año.",
                            g_mes,
                            extra=pie_nota("Fuente: DANE, EEVV 2019. Cada punto representa el total de muertes del mes."),
                            clase="card col-6",
                        ),
                        tarjeta(
                            "Gráfico de barras · las 5 ciudades más violentas",
                            "Defunciones por agresión (homicidio) en las cinco ciudades con mayor "
                            "número de casos registrados en 2019.",
                            g_ciudad,
                            extra=html.Div(
                                [
                                    html.Div(
                                        [
                                            dcc.Dropdown(
                                                id="f-homicidio",
                                                options=[
                                                    {"label": "Homicidios (lista 105 Colombia, cat. 101)", "value": "101"},
                                                    {"label": "Homicidios con arma de fuego (X93–X95)", "value": "arma"},
                                                ],
                                                value="101",
                                                clearable=False,
                                                className="dropdown dropdown-compacto",
                                            ),
                                            dcc.RadioItems(
                                                id="f-ciudad-medida",
                                                options=[
                                                    {"label": "Número de muertes", "value": "numero"},
                                                    {"label": "Tasa por 100.000 hab.", "value": "tasa"},
                                                ],
                                                value="numero",
                                                inline=True,
                                                className="radio radio-compacto",
                                            ),
                                        ],
                                        className="controles-fila",
                                    ),
                                    pie_nota(
                                        "Códigos de la ficha técnica: X95 (agresión con disparo de armas de fuego) "
                                        "y casos no especificados. Fuente: DANE, EEVV 2019."
                                    ),
                                ],
                                className="card-pie",
                            ),
                            clase="card col-6",
                        ),
                        tarjeta(
                            "Gráfico circular · 10 ciudades con menor índice de mortalidad",
                            "Participación de las diez ciudades con la tasa bruta de mortalidad más baja "
                            "(defunciones por 100.000 habitantes), con el detalle de muertes y población en el hover.",
                            g_pie,
                            extra=html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Label("Población mínima de la ciudad", htmlFor="f-umbral"),
                                            dcc.Dropdown(
                                                id="f-umbral",
                                                options=[
                                                    {"label": "Sin filtro", "value": "0"},
                                                    {"label": "10.000 habitantes", "value": "10000"},
                                                    {"label": "50.000 habitantes", "value": "50000"},
                                                    {"label": "100.000 habitantes", "value": "100000"},
                                                ],
                                                value="50000",
                                                clearable=False,
                                                className="dropdown dropdown-compacto",
                                            ),
                                        ],
                                        className="control-simple",
                                    ),
                                    pie_nota(
                                        "Tasa bruta de mortalidad = muertes del municipio ÷ población proyectada 2019 × 100.000. "
                                        "El umbral evita que el resultado dependa de municipios con muy pocos habitantes y de muertes aisladas."
                                    ),
                                ],
                                className="card-pie",
                            ),
                            clase="card col-6",
                        ),
                        tarjeta(
                            "Tabla · las 10 principales causas de muerte",
                            "Códigos CIE-10, nombre oficial de la causa y total de defunciones, ordenados de mayor "
                            "a menor. La tabla es ordenable y exportable a CSV.",
                            tabla_causas,
                            extra=pie_nota(
                                "Causa básica de defunción según la CIE-10 OPS/OMS versión 2019; "
                                "se muestran los capítulos de 3 caracteres (DANE)."
                            ),
                            clase="card col-6",
                        ),
                        tarjeta(
                            "Gráfico de barras apiladas · muertes por sexo y departamento",
                            "Comparación de las defunciones de hombres y mujeres en cada uno de los 32 "
                            "departamentos y Bogotá D.C.",
                            g_sexo,
                            extra=pie_nota("Fuente: DANE, EEVV 2019. Cifras absolutas de defunciones no fetales."),
                            clase="card col-12",
                        ),
                        tarjeta(
                            "Histograma · distribución de muertes por ciclo de vida (GRUPO_EDAD1)",
                            "Agrupación de la variable GRUPO_EDAD1 en los once rangos de la tabla de referencia, "
                            "para leer el patrón de mortalidad a lo largo del ciclo de vida.",
                            g_edad,
                            extra=pie_nota(
                                "Fuente: DANE, EEVV 2019. Rangos: neonatal, infantil, primera infancia, niñez, "
                                "adolescencia, juventud, adultez temprana, adultez intermedia, vejez, longevidad y edad desconocida."
                            ),
                            clase="card col-12",
                        ),
                    ],
                    className="grid",
                ),
            ],
            className="contenido",
        ),
        html.Footer(
            [
                html.Div(
                    [
                        html.Strong("Fuentes"),
                        html.Ul(
                            [
                                html.Li("DANE, Estadísticas Vitales 2019 (defunciones no fetales), microdatos catálogo 696."),
                                html.Li("DANE, CIE-10 OPS/OMS versión 2019 y listas 105 Colombia / 6/67 OPS."),
                                html.Li("DANE, DIVIPOLA (datos abiertos) y proyecciones de población municipal CNPV 2018."),
                            ]
                        ),
                    ],
                    className="footer-col",
                ),
                html.Div(
                    [
                        html.Strong("Notas metodológicas"),
                        html.Ul(
                            [
                                html.Li("La defunción se asigna al departamento y municipio donde ocurrió (lugar de ocurrencia)."),
                                html.Li("Tasa bruta de mortalidad = muertes ÷ población proyectada 2019 × 100.000 habitantes."),
                                html.Li("Homicidio = lista 105 Colombia, categoría 101 «Agresiones (homicidios) y secuelas» (CIE-10 X85–Y09, Y87.1)."),
                                html.Li("Los totales pueden variar levemente frente a publicaciones del DANE por ajustes de cobertura y revisión."),
                            ]
                        ),
                    ],
                    className="footer-col",
                ),
                html.Div(
                    [
                        html.Strong("Proyecto"),
                        html.P("Actividad 4 · Aplicación web interactiva para el análisis de mortalidad en Colombia."),
                        html.P("Desarrollado con Python, Dash y Plotly. Datos abiertos del DANE."),
                    ],
                    className="footer-col",
                ),
            ],
            className="footer",
        ),
    ],
    className="app",
)


# --------------------------------------------------------------------------------------
# Callbacks
# --------------------------------------------------------------------------------------
def _fmt(n):
    return f"{n:,.0f}".replace(",", ".")


@app.callback(
    Output("kpi-total", "children"),
    Output("kpi-share", "children"),
    Output("kpi-diario", "children"),
    Output("kpi-pico", "children"),
    Output("kpi-tasa", "children"),
    Output("g-mapa", "figure"),
    Output("g-mes", "figure"),
    Output("g-ciudad", "figure"),
    Output("g-pie", "figure"),
    Output("t-causas", "data"),
    Output("g-sexo", "figure"),
    Output("g-edad", "figure"),
    Output("aviso-seleccion", "children"),
    Input("f-depto", "value"),
    Input("f-sexo", "value"),
    Input("f-edad", "value"),
    Input("f-mapa", "value"),
    Input("f-homicidio", "value"),
    Input("f-ciudad-medida", "value"),
    Input("f-umbral", "value"),
    Input("btn-reset", "n_clicks"),
    prevent_initial_call=False,
)
def actualizar(deptos, sexo, grupos, modo_mapa, modo_hom, medida_ciudad, umbral, n_reset):
    df = datos.aplicar_filtros(d, deptos, sexo, grupos)
    agg = datos.recalcular(df, d)
    total = len(df)
    total_nac = d["total_nacional"]

    # ---------------- KPI ----------------
    kpi_total = _fmt(total)
    kpi_share = f"{total / total_nac * 100:.1f}%" if total_nac else "–"
    kpi_diario = _fmt(total / 365)
    por_mes = agg["por_mes"]
    if len(por_mes):
        pico = por_mes.loc[por_mes["MUERTES"].idxmax()]
        kpi_pico = f"{pico['MES_NOMBRE']} · {_fmt(pico['MUERTES'])}"
    else:
        kpi_pico = "–"
    pob_filtrada = df.drop_duplicates(["COD_DPTO", "COD_MUNIC"])["POBLACION_2019"].sum()
    kpi_tasa = f"{total / pob_filtrada * 100_000:,.1f}".replace(",", ".") if pob_filtrada else "–"

    # ---------------- Mapa ----------------
    por_depto = agg["por_depto"].copy()
    if modo_mapa == "tasa":
        por_depto["COLOR"] = por_depto["TASA_100K"]
        color_label = "Tasa bruta (por 100.000 hab.)"
        escala = "YlOrRd"
    else:
        por_depto["COLOR"] = por_depto["MUERTES"]
        color_label = "Defunciones"
        escala = "YlOrRd"

    escala_nac = d["por_depto"]
    if modo_mapa == "tasa":
        zmin, zmax = float(escala_nac["TASA_100K"].min()), float(escala_nac["TASA_100K"].max())
    else:
        zmin, zmax = 0.0, float(escala_nac["MUERTES"].max())
    fig_mapa = go.Figure(
        go.Choropleth(
            geojson=d["geo"],
            locations=por_depto["COD_DPTO"].tolist(),
            z=por_depto["COLOR"].tolist(),
            zmin=zmin,
            zmax=zmax,
            featureidkey="properties.divipola_dep",
            colorscale="YlOrRd",
            marker_line_color="white",
            marker_line_width=0.7,
            colorbar=dict(
                title=dict(text=color_label, side="right", font=dict(size=12)),
                outlinewidth=0,
                tickfont=dict(size=11),
                len=0.75,
            ),
            customdata=list(
                zip(
                    por_depto["NOM_DPTO"].str.title(),
                    por_depto["MUERTES"].map(_fmt),
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
    fig_mapa.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=520,
    )
    fig_mapa = _estilo(fig_mapa)

    # ---------------- Línea mensual ----------------
    fig_mes = go.Figure()
    if len(por_mes):
        fig_mes.add_trace(
            go.Scatter(
                x=por_mes["MES_NOMBRE"],
                y=por_mes["MUERTES"],
                mode="lines+markers+text",
                line=dict(color=NAVY, width=3),
                marker=dict(size=9, color=GOLD, line=dict(color=NAVY, width=1.5)),
                text=[_fmt(v) for v in por_mes["MUERTES"]],
                textposition="top center",
                textfont=dict(size=10, color=GRIS),
                customdata=list(zip(por_mes["MUERTES"].map(_fmt),)),
                hovertemplate="<b>%{x}</b><br>Muertes: %{customdata[0]}<extra></extra>",
                name="Muertes",
            )
        )
        maximo = por_mes.loc[por_mes["MUERTES"].idxmax()]
        minimo = por_mes.loc[por_mes["MUERTES"].idxmin()]
        fig_mes.add_annotation(
            x=maximo["MES_NOMBRE"], y=maximo["MUERTES"], text="máximo", showarrow=False,
            yshift=28, font=dict(size=11, color=ROJO, weight="bold"),
        )
        fig_mes.add_annotation(
            x=minimo["MES_NOMBRE"], y=minimo["MUERTES"], text="mínimo", showarrow=False,
            yshift=-26, font=dict(size=11, color=TEAL, weight="bold"),
        )
    fig_mes.update_layout(
        xaxis=dict(title="Mes de la defunción", showgrid=False),
        yaxis=dict(title="Número de muertes", gridcolor=GRIS_SUAVE, rangemode="tozero"),
        showlegend=False,
        height=380,
    )
    fig_mes = _estilo(fig_mes)

    # ---------------- 5 ciudades más violentas ----------------
    ciudad = agg["ciudad"].copy()
    if modo_hom == "arma":
        col = "HOMICIDIOS_ARMA"
        etiqueta = "Homicidios con arma de fuego"
    else:
        col = "HOMICIDIOS"
        etiqueta = "Homicidios"
    if medida_ciudad == "tasa":
        valor = "TASA_HOMICIDIO_100K"
        eje = "Tasa de homicidios por 100.000 habitantes"
    else:
        valor = col
        eje = "Número de muertes por agresión"

    if len(ciudad):
        top5 = ciudad.sort_values(valor, ascending=False).head(5).copy()
        top5["NOM_MUNIC_T"] = top5["NOM_MUNIC"].str.title()
        top5 = top5.sort_values(valor)
        if medida_ciudad == "tasa":
            top5["ETIQUETA"] = top5["NOM_MUNIC_T"] + " · " + top5[valor].map(lambda v: f"{v:,.1f}".replace(",", "."))
        else:
            top5["ETIQUETA"] = top5["NOM_MUNIC_T"] + " · " + top5[valor].map(_fmt)
        top5["F_MUERTES"] = top5["MUERTES"].map(_fmt)
        top5["F_POBLACION"] = top5["POBLACION"].map(_fmt)
        top5["F_TASA_HOM"] = top5["TASA_HOMICIDIO_100K"].map(lambda v: f"{v:,.1f}".replace(",", "."))
        top5["F_VALOR"] = top5[valor].map(
            lambda v: f"{v:,.1f}".replace(",", ".") if medida_ciudad == "tasa" else _fmt(v)
        )
        fig_ciudad = px.bar(
            top5,
            x=valor,
            y="NOM_MUNIC_T",
            orientation="h",
            color=valor,
            color_continuous_scale=[[0, "#e9a09a"], [1, "#8c1d18"]],
            labels={valor: eje, "NOM_MUNIC_T": ""},
            custom_data=["F_MUERTES", "F_POBLACION", "F_TASA_HOM", "F_VALOR"],
        )
        fig_ciudad.update_traces(
            marker_line_width=0,
            text=top5["ETIQUETA"],
            textposition="outside",
            textfont=dict(size=11, color=NAVY),
            cliponaxis=False,
            hovertemplate=(
                "<b>%{y}</b><br>" + etiqueta + ": %{customdata[3]}<br>"
                "Total de muertes: %{customdata[0]}<br>"
                "Población 2019: %{customdata[1]}<br>"
                "Tasa de homicidios por 100.000 hab.: %{customdata[2]}<extra></extra>"
            ),
        )
        fig_ciudad.update_layout(
            xaxis=dict(title=eje, gridcolor=GRIS_SUAVE, rangemode="tozero",
                       range=[0, float(top5[valor].max()) * 1.32]),
            yaxis=dict(title="", tickfont=dict(size=12)),
            coloraxis_showscale=False,
            showlegend=False,
            height=380,
            margin=dict(l=10, r=150, t=30, b=10),
        )
        fig_ciudad = _estilo(fig_ciudad)

    # ---------------- Circular: 10 ciudades con menor índice ----------------
    umbral = int(umbral or 0)
    cities = agg["ciudad"]
    if len(cities):
        if umbral > 0:
            cities = cities[cities["POBLACION"] >= umbral]
        bajo = cities.sort_values("TASA_100K").head(10).copy()
        bajo = bajo.sort_values("TASA_100K", ascending=False)
        fig_pie = go.Figure(
            go.Pie(
                labels=bajo["NOM_MUNIC"].str.title(),
                values=bajo["TASA_100K"],
                hole=0.45,
                sort=False,
                direction="clockwise",
                marker=dict(
                    colors=["#0d2340", "#1b4d6e", "#2a6f97", "#40916c", "#52b788",
                            "#74c69d", "#95d5b2", "#b7e4c7", "#d8f3dc", "#bde0fe"][: len(bajo)],
                    line=dict(color="white", width=1.5),
                ),
                customdata=list(
                    zip(
                        bajo["MUERTES"].map(_fmt),
                        bajo["POBLACION"].map(_fmt),
                        bajo["TASA_100K"].map(lambda v: f"{v:,.1f}".replace(",", ".")),
                    )
                ),
                hovertemplate=(
                    "<b>%{label}</b><br>Tasa bruta de mortalidad: %{customdata[2]} por 100.000 hab.<br>"
                    "Defunciones: %{customdata[0]}<br>Población 2019: %{customdata[1]}<extra></extra>"
                ),
                domain=dict(x=[0.07, 0.93], y=[0.12, 0.96]),
                textinfo="label+percent",
                textposition="outside",
                textfont=dict(size=11, color=NAVY),
                insidetextorientation="radial",
            )
        )
        fig_pie.update_layout(
            height=560,
            margin=dict(l=40, r=40, t=40, b=150),
            uniformtext_minsize=9,
        )
        fig_pie = _estilo(
            fig_pie,
            leyenda=dict(orientation="h", yanchor="top", y=-0.02, xanchor="center", x=0.5,
                         font=dict(size=10), title_text=""),
        )

    # ---------------- Tabla de causas ----------------
    pc = agg["por_causa"].head(10).copy()
    total_causas = pc["MUERTES"].sum() or 1
    filas = [
        {
            "codigo": r.CAUSA_3,
            "causa": r.NOMBRE_CAUSA,
            "causa105": r.NOMBRE_CAUSA_105,
            "muertes": int(r.MUERTES),
            "participacion": round(r.MUERTES / total * 100, 2),
        }
        for r in pc.itertuples()
    ]

    # ---------------- Barras apiladas por sexo ----------------
    sd = agg["sexo_depto"].copy()
    if len(sd):
        sd["TOTAL"] = sd[[c for c in sd.columns if c in PALETA_SEXO]].sum(axis=1)
        sd = sd.sort_values("TOTAL", ascending=True)
        sexo_cols = [c for c in sd.columns if c in PALETA_SEXO]
        registros = []
        for fila in sd.to_dict("records"):
            for col in sexo_cols:
                registros.append(
                    {
                        "COD_DPTO": fila["COD_DPTO"],
                        "NOM_DPTO": fila["NOM_DPTO"],
                        "Sexo": col,
                        "MUERTES": fila[col],
                        "F_MUERTES": _fmt(fila[col]),
                    }
                )
        sd_long = pd.DataFrame(registros)
        fig_sexo = px.bar(
            sd_long,
            x="MUERTES",
            y="NOM_DPTO",
            color="Sexo",
            orientation="h",
            barmode="stack",
            color_discrete_map=PALETA_SEXO,
            labels={"NOM_DPTO": "", "MUERTES": "Defunciones"},
            category_orders={"NOM_DPTO": sd["NOM_DPTO"].tolist()},
        )
        fig_sexo.update_traces(
            marker_line_width=0,
            customdata=["F_MUERTES"],
            hovertemplate="<b>%{y}</b><br>%{fullData.name}: %{customdata[0]}<extra></extra>",
        )
        fig_sexo.update_layout(
            xaxis=dict(title="Defunciones", gridcolor=GRIS_SUAVE),
            yaxis=dict(title="", tickfont=dict(size=11), categoryorder="array"),
            barmode="stack",
            height=760,
            margin=dict(l=10, r=20, t=30, b=10),
            legend=dict(title_text="", orientation="h", yanchor="bottom", y=1.01, x=0),
        )
        fig_sexo = _estilo(fig_sexo)

    # ---------------- Histograma por ciclo de vida ----------------
    pe = agg["por_edad"].copy()
    if len(pe):
        resumen = (
            pe.groupby(["CATEGORIA_EDAD", "RANGO_EDAD", "ORDEN"], as_index=False)["MUERTES"].sum()
            .sort_values("ORDEN")
        )
        resumen["ETIQUETA"] = (
            resumen["CATEGORIA_EDAD"] + " (" + resumen["RANGO_EDAD"] + ")"
        )
        resumen["PORC"] = resumen["MUERTES"] / total * 100 if total else 0
        resumen["F_MUERTES"] = resumen["MUERTES"].map(_fmt)
        resumen["F_PORC"] = resumen["PORC"].map(lambda v: f"{v:,.2f}%".replace(",", "."))
        fig_edad = px.bar(
            resumen,
            x="ETIQUETA",
            y="MUERTES",
            color="MUERTES",
            color_continuous_scale=[[0, "#dbeafe"], [0.5, NAVY_SOFT], [1, NAVY]],
            labels={"ETIQUETA": "Grupo de edad (GRUPO_EDAD1)", "MUERTES": "Defunciones"},
            custom_data=["F_MUERTES", "F_PORC"],
        )
        fig_edad.update_traces(
            text=[f"{_fmt(v)}" for v in resumen["MUERTES"]],
            textposition="outside",
            textfont=dict(size=11, color=NAVY),
            marker_line_width=0,
            cliponaxis=False,
            hovertemplate=(
                "<b>%{x}</b><br>Defunciones: %{customdata[0]}<br>Participación: %{customdata[1]}<extra></extra>"
            ),
        )
        fig_edad.update_layout(
            xaxis=dict(title="", tickangle=-20, tickfont=dict(size=11)),
            yaxis=dict(title="Defunciones", gridcolor=GRIS_SUAVE, rangemode="tozero"),
            coloraxis_showscale=False,
            height=420,
            margin=dict(l=10, r=20, t=30, b=10),
        )
        fig_edad = _estilo(fig_edad)

    # ---------------- Aviso y descarga ----------------
    if deptos:
        nombres = ", ".join(
            sorted(
                d["departamentos"].set_index("COD_DPTO").loc[list(deptos), "NOM_DPTO"].str.title().tolist()
            )
        )
        aviso = f"Vista filtrada por departamento: {nombres}. Use «Restablecer filtros» para volver a todo el país."
    else:
        aviso = "Mostrando el total nacional. Haga clic en un departamento del mapa para filtrar."

    return (
        kpi_total, kpi_share, kpi_diario, kpi_pico, kpi_tasa,
        fig_mapa, fig_mes, fig_ciudad, fig_pie, filas,
        fig_sexo, fig_edad, aviso,
    )


@app.callback(
    Output("f-depto", "value"),
    Input("g-mapa", "clickData"),
    prevent_initial_call=True,
)
def seleccionar_departamento(click):
    if not click or not click.get("points"):
        return no_update
    loc = click["points"][0].get("location")
    if loc is None:
        return no_update
    return [str(loc).zfill(2)]


@app.callback(
    Output("f-depto", "value", allow_duplicate=True),
    Output("f-sexo", "value", allow_duplicate=True),
    Output("f-edad", "value", allow_duplicate=True),
    Output("f-mapa", "value", allow_duplicate=True),
    Output("f-homicidio", "value", allow_duplicate=True),
    Output("f-ciudad-medida", "value", allow_duplicate=True),
    Output("f-umbral", "value", allow_duplicate=True),
    Input("btn-reset", "n_clicks"),
    prevent_initial_call=True,
)
def restablecer(_):
    return [], "Todos", [], "muertes", "101", "numero", "50000"


@app.callback(
    Output("descarga", "data", allow_duplicate=True),
    Input("btn-descargar", "n_clicks"),
    State("f-depto", "value"),
    State("f-sexo", "value"),
    State("f-edad", "value"),
    prevent_initial_call=True,
)
def descargar_csv(n, deptos, sexo, grupos):
    if not n:
        return no_update
    df = datos.aplicar_filtros(d, deptos, sexo, grupos)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    import base64
    return dict(content=base64.b64encode(buf.getvalue().encode("utf-8")).decode())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)

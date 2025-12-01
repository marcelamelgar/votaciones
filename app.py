#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import tempfile

import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="Visualización de Resultados",
    layout="wide",
)

st.markdown("""
<style>

:root {
    --main-color: #1a4ba3;        /* azul profesional */
    --main-light: #e9f0fb;        /* azul muy claro */
    --text-dark: #1d1d1d;
    --text-light: #5c5c5c;
    --border-soft: #d9d9d9;
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ----- TITULOS ----- */
h1 {
    color: var(--main-color) !important;
    font-weight: 800 !important;
    letter-spacing: -0.5px;
}

h2, h3 {
    color: var(--text-dark) !important;
    font-weight: 700 !important;
}

h4, h5 {
    color: var(--text-light) !important;
}

/* ----- TARJETAS DE MÉTRICA ----- */

.metric-card {
    padding: 1.2rem;
    border-radius: 14px;
    border: 1px solid var(--border-soft);      /* gris suave */
    background-color: #ffffff;                 /* fondo blanco */
    box-shadow: 0px 3px 10px rgba(0,0,0,0.07); /* sombra */
    text-align: center;
}

.metric-title {
    font-size: 0.95rem;
    color: var(--main-color);                  /* azul profesional */
    font-weight: 600;
}

.metric-value {
    font-size: 2.2rem;
    font-weight: 800;
    color: var(--text-dark);                   /* gris oscuro */
    margin-top: -8px;
}

/* ----- DIVIDER ----- */
.divider {
    border-bottom: 2px solid var(--border-soft);
    margin: 1.3rem 0 1.3rem 0;
}

/* ----- WIDGETS (select, multiselect, slider…) ----- */
.stSelectbox > div > div,
.stMultiSelect > div > div {
    border: 1px solid var(--main-color) !important;
    border-radius: 10px !important;
}

.st-bf {
    color: var(--main-color) !important;
}

/* ----- TABLA ----- */
[data-testid="stDataFrame"] thead tr th {
    background-color: var(--main-light) !important;
    color: var(--main-color) !important;
    font-weight: 700 !important;
}

/* ----- BOTONES DE FILTRO EN MULTISELECT ----- */
.stMultiSelect [data-baseweb="tag"] {
    background-color: var(--main-light) !important;
    color: var(--main-color) !important;
    border-radius: 6px;
}

/* ----- TOOLBAR PLOTLY ----- */
.plotly .modebar-group * {
    color: var(--main-color) !important;
}

/* Remove Streamlit footer */
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


ESTADOS = ["A FAVOR", "EN CONTRA", "AUSENTE", "LICENCIA"]
EXCEL_6433 = "analisis_votaciones.xlsx"
EXCEL_6625 = "analisis_votaciones_presupuesto.xlsx"

# ============ Funciones comunes ============

def normalizar_estado(s):
    s = str(s).strip().upper()
    s = s.replace("Á", "A")
    for e in ESTADOS:
        if s == e:
            return e
    return s

def normalizar_bloque(s):
    s = str(s)
    s = " ".join(s.split())   # colapsa espacios internos
    s = s.strip().upper()
    return s

def agregar_categoria_cambio(df):
    if "categoria_cambio" in df.columns:
        return df
    def clasificar_cambio(row):
        v1 = row["voto_1"]
        v2 = row["voto_2"]
        if v1 == v2:
            return "Se mantiene"
        if (v1 == "A FAVOR" and v2 == "EN CONTRA") or (v1 == "EN CONTRA" and v2 == "A FAVOR"):
            return "Cambia opinión Favor/Contra"
        if v1 in ["AUSENTE", "LICENCIA"] and v2 in ["A FAVOR", "EN CONTRA"]:
            return "Se activa (no votaba → vota)"
        if v1 in ["A FAVOR", "EN CONTRA"] and v2 in ["AUSENTE", "LICENCIA"]:
            return "Se desactiva (votaba → no vota)"
        if v1 in ["AUSENTE", "LICENCIA"] and v2 in ["AUSENTE", "LICENCIA"]:
            return "Cambia tipo de no voto"
        return "Otro cambio"
    df["categoria_cambio"] = df.apply(clasificar_cambio, axis=1)
    return df

def calcular_kpis_basicos(df):
    total_iguales = (df["voto_1"] == df["voto_2"]).sum()
    favor_a_contra = ((df["voto_1"] == "A FAVOR") & (df["voto_2"] == "EN CONTRA")).sum()
    contra_a_favor = ((df["voto_1"] == "EN CONTRA") & (df["voto_2"] == "A FAVOR")).sum()
    se_desactivan = (
        df["voto_1"].isin(["A FAVOR", "EN CONTRA"]) &
        df["voto_2"].isin(["AUSENTE", "LICENCIA"])
    ).sum()
    se_activan = (
        df["voto_1"].isin(["AUSENTE", "LICENCIA"]) &
        df["voto_2"].isin(["A FAVOR", "EN CONTRA"])
    ).sum()
    return total_iguales, favor_a_contra, contra_a_favor, se_desactivan, se_activan

def conteos_por_estado(df):
    favor_1   = (df["voto_1"] == "A FAVOR").sum()
    contra_1  = (df["voto_1"] == "EN CONTRA").sum()
    aus_1     = (df["voto_1"] == "AUSENTE").sum()
    lic_1     = (df["voto_1"] == "LICENCIA").sum()

    favor_2   = (df["voto_2"] == "A FAVOR").sum()
    contra_2  = (df["voto_2"] == "EN CONTRA").sum()
    aus_2     = (df["voto_2"] == "AUSENTE").sum()
    lic_2     = (df["voto_2"] == "LICENCIA").sum()

    return (favor_1, contra_1, aus_1, lic_1,
            favor_2, contra_2, aus_2, lic_2)

def resultado_global(favor_2, contra_2):
    if favor_2 > contra_2:
        return "APROBADO", "#d5f5dd", "#1a7a33"
    elif contra_2 > favor_2:
        return "NO APROBADO", "#f8d6d6", "#b32121"
    else:
        return "EMPATE", "#e2e2e2", "#444444"

# === Helper para guardar archivos subidos ===
def save_uploaded_file(uploaded_file, prefix="file_"):
    suffix = ""
    if "." in uploaded_file.name:
        suffix = "." + uploaded_file.name.split(".")[-1]
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return path

# === Placeholder para tus scripts de Markov / PDFs ===
def run_markov_pipeline(pdf1_path, id1, pdf2_path, id2):
    output_excel = "analisis_votaciones.xlsx"
    return output_excel

# ============ Sidebar ============

with st.sidebar:
    st.title("Visualización de Resultados")
    seccion = st.radio(
        "Comportamiento en Votaciones",
        ["6433 - Participación de CACIF en la Comisión de Infraestructura ANADIE",
         "6625 - Aprobación de Presupuesto"],
        index=0
    )
    st.markdown("---")

# ======================================================
#  SECCIÓN 6433 – 1ª vs 2ª vuelta participación CACIF
# ======================================================
# ======================================================
#  SECCIÓN 6433 – 1ª vs 2ª vuelta participación CACIF
# ======================================================
if seccion.startswith("6433"):

    # === Cargar datos ===
    merged = pd.read_excel(EXCEL_6433, sheet_name="Votos_unidos")
    merged.columns = [c.strip() for c in merged.columns]

    merged["voto_1"] = merged["voto_1"].map(normalizar_estado)
    merged["voto_2"] = merged["voto_2"].map(normalizar_estado)
    merged["bloque_norm"] = merged["bloque_1"].map(normalizar_bloque)
    merged = agregar_categoria_cambio(merged)

    # Conteos
    (favor_1, contra_1, aus_1, lic_1,
     favor_2, contra_2, aus_2, lic_2) = conteos_por_estado(merged)

    total_iguales, favor_a_contra, contra_a_favor, se_desactivan, se_activan = calcular_kpis_basicos(merged)
    resultado_texto, bg_color, fg_color = resultado_global(favor_2, contra_2)

    # === Main ===
    st.title("Votaciones Iniciativa 6466")

    st.subheader("Resumen de votos por vuelta")

    # Primera vuelta
    st.markdown("### Primera vuelta")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">A FAVOR (1ª)</div>
            <div class="metric-value">{favor_1}</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">EN CONTRA (1ª)</div>
            <div class="metric-value">{contra_1}</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">AUSENTE (1ª)</div>
            <div class="metric-value">{aus_1}</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">LICENCIA (1ª)</div>
            <div class="metric-value">{lic_1}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Segunda vuelta
    st.markdown("### Segunda vuelta")
    d1, d2, d3, d4 = st.columns(4)

    with d1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">A FAVOR (2ª)</div>
            <div class="metric-value">{favor_2}</div>
        </div>
        """, unsafe_allow_html=True)

    with d2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">EN CONTRA (2ª)</div>
            <div class="metric-value">{contra_2}</div>
        </div>
        """, unsafe_allow_html=True)

    with d3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">AUSENTE (2ª)</div>
            <div class="metric-value">{aus_2}</div>
        </div>
        """, unsafe_allow_html=True)

    with d4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">LICENCIA (2ª)</div>
            <div class="metric-value">{lic_2}</div>
        </div>
        """, unsafe_allow_html=True)

    # === Nuevo Banner SIN números ===
    st.markdown(
        f"""
        <div style="
            margin-top: 1rem;
            margin-bottom: 0.8rem;
            padding: 1rem 1.5rem;
            border-radius: 0.6rem;
            background-color: {bg_color};
            color: {fg_color};
            text-align: center;
            font-size: 1.3rem;
            font-weight: 700;">
            Resultado 2ª vuelta: {resultado_texto}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # === NUEVAS TARJETAS: A FAVOR / EN CONTRA CACIF EN 2ª VUELTA ===
    t1, t2 = st.columns(2)

    with t1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">EN CONTRA del CACIF (2ª)</div>
            <div class="metric-value">{favor_2}</div>
        </div>
        """, unsafe_allow_html=True)

    with t2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">A FAVOR del CACIF (2ª)</div>
            <div class="metric-value">{contra_2}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # KPIs comportamiento
    st.subheader("Comportamiento entre 1ª y 2ª vuelta")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Misma votación", total_iguales)
    col2.metric("A FAVOR → EN CONTRA", favor_a_contra)
    col3.metric("EN CONTRA → A FAVOR", contra_a_favor)
    col4.metric("Se desactivaron (votaban → no)", se_desactivan)
    col5.metric("Se activaron (no votaban → votan)", se_activan)

    st.markdown("---")

    # BLOQUES
    st.subheader("Votaciones por bloque")

    bloques = ["TODOS"] + sorted(merged["bloque_norm"].dropna().unique())
    bloque_sel = st.selectbox("Selecciona un bloque", bloques)

    df_b = merged if bloque_sel == "TODOS" else merged[merged["bloque_norm"] == bloque_sel]

    mat_bloque = (
        df_b.groupby(["voto_1", "voto_2"])
        .size()
        .unstack(fill_value=0)
        .reindex(index=ESTADOS, columns=ESTADOS, fill_value=0)
    )

    fig_heat = px.imshow(
        mat_bloque,
        text_auto=True,
        labels=dict(x="Voto 2ª vuelta", y="Voto 1ª vuelta", color="Conteo"),
        x=mat_bloque.columns,
        y=mat_bloque.index,
        title=f"Transiciones de voto - Bloque {bloque_sel}",
    )

    st.plotly_chart(fig_heat, use_container_width=True)

    st.markdown(f"### Detalle de diputados del bloque {bloque_sel}")

    f1, f2 = st.columns([2, 1])
    with f1:
        tipo_cambio_bloque = st.multiselect(
            "Filtrar por tipo de comportamiento",
            sorted(df_b["categoria_cambio"].unique()),
            default=sorted(df_b["categoria_cambio"].unique()),
        )
    with f2:
        voto2_sel = st.selectbox("Filtrar por voto 2ª vuelta", ["Todos"] + ESTADOS)

    df_detalle = df_b[df_b["categoria_cambio"].isin(tipo_cambio_bloque)]
    if voto2_sel != "Todos":
        df_detalle = df_detalle[df_detalle["voto_2"] == voto2_sel]

    df_detalle = df_detalle.rename(columns={
        "nombre": "Nombre",
        "bloque_1": "Bloque",
        "voto_1": "Voto 1ª vuelta",
        "voto_2": "Voto 2ª vuelta",
        "categoria_cambio": "Categoría de Cambio",
    })

    st.dataframe(
        df_detalle[["Nombre", "Bloque", "Voto 1ª vuelta", "Voto 2ª vuelta", "Categoría de Cambio"]]
        .sort_values(["Bloque", "Nombre"]),
        use_container_width=True
    )

    st.markdown("---")

    # =======================
    #  Gráfico de barras por bloque - todos los cambios
    # =======================

    st.subheader("Cambios de voto por bloque - Todos los bloques")

    resumen_bloques = (
        merged
        .groupby(["bloque_norm", "categoria_cambio"])
        .size()
        .reset_index(name="Diputados")
    )

    # 👉 Renombrar columnas para que el tooltip/leyenda se vean bonitos
    resumen_bloques = resumen_bloques.rename(columns={
        "bloque_norm": "Bloque",
        "categoria_cambio": "Categoría de Cambio",
    })

    fig_bar = px.bar(
        resumen_bloques,
        x="Bloque",
        y="Diputados",
        color="Categoría de Cambio",
        title="Cambios de voto por bloque - Todos los bloques",
        labels={
            "Bloque": "Bloque",
            "Diputados": "Diputados",
            "Categoría de Cambio": "Categoría de Cambio",
        },
    )

    # ordenar bloques de mayor a menor total de diputados
    fig_bar.update_layout(
        xaxis_tickangle=-45,
        xaxis=dict(categoryorder="total descending"),
        height=700,
        margin=dict(t=60),
    )

    st.plotly_chart(fig_bar, use_container_width=True)


    # =======================
    #  Gráfica stacked: se mantienen A FAVOR / EN CONTRA por bloque
    # =======================

    st.subheader("Diputados que mantuvieron su voto (A FAVOR / EN CONTRA) por bloque")

    df_mantienen = merged[
        (merged["voto_1"] == merged["voto_2"]) &
        (merged["voto_1"].isin(["A FAVOR", "EN CONTRA"]))
    ].copy()

    if df_mantienen.empty:
        st.info("No hay diputados que se mantuvieran A FAVOR o EN CONTRA en ambas vueltas.")
    else:
        resumen_mantienen = (
            df_mantienen
            .groupby(["bloque_norm", "voto_2"])
            .size()
            .reset_index(name="Diputados")
            .rename(columns={
                "bloque_norm": "Bloque",
                "voto_2": "Voto"
            })
        )

        # ▶️ Etiquetas más bonitas para la leyenda y el tooltip
        voto_labels = {
            "A FAVOR": "A favor",
            "EN CONTRA": "En contra",
        }
        resumen_mantienen["Sentido de voto"] = resumen_mantienen["Voto"].map(voto_labels)

        fig_mant = px.bar(
            resumen_mantienen,
            x="Bloque",
            y="Diputados",
            color="Sentido de voto",
            title="Diputados que mantuvieron el mismo sentido de voto por bloque",
            labels={
                "Bloque": "Bloque",
                "Diputados": "Diputados",
                "Sentido de voto": "Sentido de voto",
            },
            color_discrete_map={
                "En contra": "#e74c3c",   # rojo
                "A favor": "#27ae60",     # verde
            },
        )

        fig_mant.update_layout(
            barmode="stack",
            xaxis_tickangle=-45,
            xaxis=dict(categoryorder="total descending"),
            height=650,
            margin=dict(t=60),
        )

        st.plotly_chart(fig_mant, use_container_width=True)



# ======================================================
#  SECCIÓN 6625 – 2ª vuelta CACIF vs Aprobación Presupuesto
# ======================================================
elif seccion.startswith("6625"):
    # === Cargar datos ===
    merged = pd.read_excel(EXCEL_6625, sheet_name="Votos_unidos")
    merged.columns = [c.strip() for c in merged.columns]

    merged["voto_1"] = merged["voto_1"].map(normalizar_estado)
    merged["voto_2"] = merged["voto_2"].map(normalizar_estado)
    merged["bloque_norm"] = merged["bloque_1"].map(normalizar_bloque)
    merged = agregar_categoria_cambio(merged)

    (favor_1, contra_1, aus_1, lic_1,
     favor_2, contra_2, aus_2, lic_2) = conteos_por_estado(merged)

    total_iguales, favor_a_contra, contra_a_favor, se_desactivan, se_activan = calcular_kpis_basicos(merged)
    resultado_texto, bg_color, fg_color = resultado_global(favor_2, contra_2)

    # === Main ===
    st.title("2ª vuelta 6433 vs Aprobación de Presupuesto - 6625")

    # ---------- Resumen por "vuelta"/evento ----------
    st.subheader("Resumen de votos por tema")

    # 2ª vuelta participación CACIF (voto_1)
    st.markdown("### 2ª vuelta participación CACIF")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">A FAVOR (CACIF 2ª)</div>
            <div class="metric-value">{favor_1}</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">EN CONTRA (CACIF 2ª)</div>
            <div class="metric-value">{contra_1}</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">AUSENTE (CACIF 2ª)</div>
            <div class="metric-value">{aus_1}</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">LICENCIA (CACIF 2ª)</div>
            <div class="metric-value">{lic_1}</div>
        </div>
        """, unsafe_allow_html=True)

    # División visual
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Aprobación de Presupuesto (voto_2)
    st.markdown("### Aprobación de presupuesto")
    d1, d2, d3, d4 = st.columns(4)

    with d1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">A FAVOR (Presupuesto)</div>
            <div class="metric-value">{favor_2}</div>
        </div>
        """, unsafe_allow_html=True)

    with d2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">EN CONTRA (Presupuesto)</div>
            <div class="metric-value">{contra_2}</div>
        </div>
        """, unsafe_allow_html=True)

    with d3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">AUSENTE (Presupuesto)</div>
            <div class="metric-value">{aus_2}</div>
        </div>
        """, unsafe_allow_html=True)

    with d4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">LICENCIA (Presupuesto)</div>
            <div class="metric-value">{lic_2}</div>
        </div>
        """, unsafe_allow_html=True)

    # Banner de resultado global (Presupuesto)
    st.markdown(
        f"""
        <div style="
            margin-top: 1rem;
            margin-bottom: 1.5rem;
            padding: 1rem 1.5rem;
            border-radius: 0.6rem;
            background-color: {bg_color};
            color: {fg_color};
            text-align: center;
            font-size: 1.3rem;
            font-weight: 700;">
            Resultado aprobación de presupuesto: {resultado_texto}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # NUEVOS CUADROS: A favor / En contra del CACIF (2ª)
    res1, res2 = st.columns(2)

    with res1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">A FAVOR del Presupuesto - EN CONTRA de CACIF</div>
            <div class="metric-value">{favor_2}</div>
        </div>
        """, unsafe_allow_html=True)

    with res2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">EN CONTRA del Presupuesto - A FAVOR de CACIF</div>
            <div class="metric-value">{contra_2}</div>
        </div>
        """, unsafe_allow_html=True)

    # ---------- KPIs de comportamiento entre CACIF 2ª vs Presupuesto ----------
    st.subheader("Comportamiento entre 2ª vuelta CACIF y aprobación de presupuesto")

    col1, col2, col3, col4, col5 = st.columns(5)

    # Métrica normal
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">
                Mismo sentido <br>de voto
            </div>
            <div class="metric-value">{total_iguales}</div>
        </div>
        """, unsafe_allow_html=True)
    #col1.metric("Mismo sentido de voto", total_iguales)

    # Métrica 2 con título en dos líneas
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">
                CACIF 2ª A FAVOR →<br>Presupuesto EN CONTRA
            </div>
            <div class="metric-value">{favor_a_contra}</div>
        </div>
        """, unsafe_allow_html=True)

    # Métrica 3 con título en dos líneas
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">
                CACIF 2ª EN CONTRA →<br>Presupuesto A FAVOR
            </div>
            <div class="metric-value">{contra_a_favor}</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">
                Se desactivan (votaban → no votan)
            </div>
            <div class="metric-value">{se_desactivan}</div>
        </div>
        """, unsafe_allow_html=True)

    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">
                Se activan (no votaban → votan)
            </div>
            <div class="metric-value">{se_activan}</div>
        </div>
        """, unsafe_allow_html=True)

    # Las otras dos siguen igual con st.metric
    ##col4.metric("Se desactivan (votaban → no)", se_desactivan)
    #col5.metric("Se activan (no votaban → votan)", se_activan)


    st.markdown("---")

    # =======================
    #  Transiciones por bloque
    # =======================

    st.subheader("Comparativo por bloque (CACIF 2ª vs Presupuesto)")

    bloques = sorted(merged["bloque_norm"].dropna().unique())
    bloques = ["TODOS"] + bloques

    bloque_sel = st.selectbox("Selecciona un bloque", options=bloques)

    # Data filtrada por bloque (para heatmap + tabla)
    if bloque_sel == "TODOS":
        df_b = merged.copy()
    else:
        df_b = merged[merged["bloque_norm"] == bloque_sel].copy()

    # --- Heatmap ---
    mat_bloque = (
        df_b
        .groupby(["voto_1", "voto_2"])
        .size()
        .unstack(fill_value=0)
        .reindex(index=ESTADOS, columns=ESTADOS, fill_value=0)
    )

    titulo_bloque = "TODOS" if bloque_sel == "TODOS" else bloque_sel

    fig_heat = px.imshow(
        mat_bloque,
        text_auto=True,
        labels=dict(
            x="Voto en aprobación de presupuesto",
            y="Voto en 2ª vuelta CACIF",
            color="Conteo"
        ),
        x=mat_bloque.columns,
        y=mat_bloque.index,
        title=f"Transiciones de sentido de voto - Bloque {titulo_bloque}",
    )
    st.plotly_chart(fig_heat, use_container_width=True)

    # --- Tabla de detalle (mismo filtro de bloque) ---
    st.markdown(f"### Detalle de diputados del bloque {titulo_bloque}")

    fcol1, fcol2 = st.columns([2, 1])

    with fcol1:
        tipo_cambio_bloque = st.multiselect(
            "Filtrar por tipo de comportamiento",
            options=sorted(df_b["categoria_cambio"].unique()),
            default=sorted(df_b["categoria_cambio"].unique())
        )

    with fcol2:
        opciones_voto2 = ["Todos"] + ESTADOS
        voto2_sel = st.selectbox(
            "Filtrar por voto en presupuesto",
            options=opciones_voto2,
            index=0
        )

    df_detalle = df_b[df_b["categoria_cambio"].isin(tipo_cambio_bloque)].copy()

    if voto2_sel != "Todos":
        df_detalle = df_detalle[df_detalle["voto_2"] == voto2_sel]

    df_detalle = df_detalle.rename(columns={
        "nombre": "Nombre",
        "bloque_1": "Bloque",
        "voto_1": "Voto 2ª CACIF",
        "voto_2": "Voto Presupuesto",
        "categoria_cambio": "Categoría de Cambio",
    })

    df_detalle = df_detalle[
        ["Nombre", "Bloque", "Voto 2ª CACIF", "Voto Presupuesto", "Categoría de Cambio"]
    ].sort_values(["Bloque", "Nombre"])

    st.dataframe(df_detalle, use_container_width=True)

    st.markdown("---")

    # =======================
    #  Gráfico de barras por bloque - todos los cambios
    # =======================

    st.subheader("Cambios de sentido de voto por bloque")

    resumen_bloques = (
        merged
        .groupby(["bloque_norm", "categoria_cambio"])
        .size()
        .reset_index(name="Diputados")
        .rename(columns={
            "bloque_norm": "Bloque",
            "categoria_cambio": "Categoría de Cambio"
        })
    )

    fig_bar = px.bar(
        resumen_bloques,
        x="Bloque",
        y="Diputados",
        color="Categoría de Cambio",
        title="Cambios de sentido de voto por bloque",
        labels={"Bloque": "Bloque", "Diputados": "Diputados"},
    )

    fig_bar.update_layout(
        xaxis_tickangle=-45,
        xaxis=dict(categoryorder="total descending"),
        height=700,
        margin=dict(t=60),
    )

    st.plotly_chart(fig_bar, use_container_width=True)

    # =======================
    #  Gráfica stacked: mismo sentido A FAVOR / EN CONTRA por bloque
    # =======================

    st.subheader("Diputados que mantienen el mismo sentido (A FAVOR / EN CONTRA) en ambos temas")

    df_mantienen = merged[
        (merged["voto_1"] == merged["voto_2"]) &
        (merged["voto_1"].isin(["A FAVOR", "EN CONTRA"]))
    ].copy()

    if df_mantienen.empty:
        st.info("No hay diputados que mantuvieran A FAVOR o EN CONTRA en ambos temas.")
    else:
        resumen_mantienen = (
            df_mantienen
            .groupby(["bloque_norm", "voto_2"])
            .size()
            .reset_index(name="Diputados")
            .rename(columns={
                "bloque_norm": "Bloque",
                "voto_2": "Voto"
            })
        )

        fig_mant = px.bar(
            resumen_mantienen,
            x="Bloque",
            y="Diputados",
            color="Voto",
            title="Diputados que mantienen el mismo sentido (CACIF 2ª vs Presupuesto)",
            labels={"Bloque": "Bloque", "Diputados": "Diputados", "Voto": "Voto"},
            color_discrete_map={
                "EN CONTRA": "#e74c3c",  # rojo
                "A FAVOR": "#27ae60"     # verde
            },
        )

        fig_mant.update_layout(
            barmode="stack",
            xaxis_tickangle=-45,
            xaxis=dict(categoryorder="total descending"),
            height=650,
            margin=dict(t=60),
        )

        st.plotly_chart(fig_mant, use_container_width=True)

# ======================================================
#  SECCIÓN 3 – Solo carga (contenido principal)
# (ahora mismo no se usa porque el radio no tiene la opción)
# ======================================================
else:
    st.title("Carga de archivos de votaciones")
    st.markdown("""
    Usa el panel de la izquierda para cargar los **dos PDFs** que quieres comparar,
    asignarles un identificador y generar el Excel de entrada para el dashboard.  
    Puedes reutilizar esta opción cada vez que tengas nuevas votaciones.
    """)

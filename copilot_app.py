import streamlit as st
import pandas as pd
import plotly.express as px
import re
import math

st.set_page_config(page_title="Copilot Planeación", layout="wide")

st.title("📦 Copilot de Planeación de Demanda")

archivo = "FORMATO PEDIDOS CARGA SECA.xlsm"

# ------------------------------------------------
# CARGA DATOS
# ------------------------------------------------

@st.cache_data(ttl=300)
def cargar_datos():

    df = pd.read_excel(
        archivo,
        sheet_name="MONTAJE",
        header=3
    )

    # limpiar nombres columnas
    df.columns = df.columns.astype(str).str.strip()

    # eliminar columnas vacías Excel
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    # eliminar columnas nan
    df = df.loc[:, df.columns != "nan"]

    # eliminar columnas duplicadas
    df = df.loc[:, ~df.columns.duplicated()]

    df = df.reset_index(drop=True)

    return df


df = cargar_datos()

# ------------------------------------------------
# LIMPIEZA
# ------------------------------------------------

df["Vig"] = df["Vig"].astype(str).str.strip().str.upper()
df = df[df["Vig"] != "NO"]

# ------------------------------------------------
# INVENTARIO TOTAL
# ------------------------------------------------

if "Transito" in df.columns:
    df["Inventario total"] = df["Inv 11 Mar"] + df["Transito"]
else:
    df["Inventario total"] = df["Inv 11 Mar"]

# ------------------------------------------------
# DEMANDA DIARIA
# ------------------------------------------------

df["Demanda diaria"] = df["Prom Pond"] / 7

# ------------------------------------------------
# COBERTURA
# ------------------------------------------------

df["Cob"] = (
    df["Inventario total"] /
    df["Demanda diaria"]
).replace([float("inf")],0).fillna(0).round(1)

# ------------------------------------------------
# CLASIFICACIÓN COBERTURA
# ------------------------------------------------

def clasificar(c):

    if c < 3:
        return "QUIEBRE"
    elif c < 10:
        return "PELIGRO"
    elif c > 30:
        return "SOBRESTOCK"
    else:
        return "SALUDABLE"


df["Estado"] = df["Cob"].apply(clasificar)

# ------------------------------------------------
# FILTROS
# ------------------------------------------------

st.sidebar.header("Filtros")

distrito = st.sidebar.multiselect(
    "Distrito",
    sorted(df["Distrito"].dropna().unique())
)

pdv = st.sidebar.multiselect(
    "PDV",
    sorted(df["PDV"].dropna().unique())
)

familia = None
planeador = None

if "Familia" in df.columns:

    familia = st.sidebar.multiselect(
        "Familia",
        sorted(df["Familia"].dropna().unique())
    )

if "Planeador" in df.columns:

    planeador = st.sidebar.multiselect(
        "Planeador",
        sorted(df["Planeador"].dropna().unique())
    )

df_filtro = df.copy()

if distrito:
    df_filtro = df_filtro[df_filtro["Distrito"].isin(distrito)]

if pdv:
    df_filtro = df_filtro[df_filtro["PDV"].isin(pdv)]

if familia:
    df_filtro = df_filtro[df_filtro["Familia"].isin(familia)]

if planeador:
    df_filtro = df_filtro[df_filtro["Planeador"].isin(planeador)]

# ------------------------------------------------
# KPIs
# ------------------------------------------------

inventario_total = round(df_filtro["Inventario total"].sum(),0)
demanda_prom = round(df_filtro["Prom Pond"].mean(),1)
cobertura_red = round(df_filtro["Cob"].median(),1)

quiebres = df_filtro[df_filtro["Estado"] == "QUIEBRE"]

st.subheader("Indicadores de la red")

col1,col2,col3,col4 = st.columns(4)

col1.metric("Inventario total",inventario_total)
col2.metric("Demanda semanal promedio",demanda_prom)
col3.metric("Cobertura red (días)",cobertura_red)
col4.metric("Materiales en quiebre",len(quiebres))

# ------------------------------------------------
# TABS
# ------------------------------------------------

tab1,tab2,tab3,tab4,tab5 = st.tabs([
"Dashboard",
"Riesgos",
"Sobrestock",
"Copilot",
"Pedido sugerido"
])

# ------------------------------------------------
# DASHBOARD
# ------------------------------------------------

with tab1:

    cobertura = (
        df_filtro
        .groupby("Distrito")["Cob"]
        .median()
        .reset_index()
    )

    fig = px.bar(
        cobertura,
        x="Distrito",
        y="Cob",
        title="Cobertura mediana por distrito"
    )

    st.plotly_chart(fig,use_container_width=True)

# ------------------------------------------------
# RIESGOS
# ------------------------------------------------

with tab2:

    st.subheader("Resumen de riesgo")

    riesgo = (
        df_filtro
        .groupby(["Distrito","Estado"])
        .size()
        .reset_index(name="Materiales")
    )

    total_distrito = (
        df_filtro
        .groupby("Distrito")
        .size()
        .reset_index(name="Total")
    )

    riesgo = riesgo.merge(total_distrito)

    riesgo["Porcentaje"] = (
        riesgo["Materiales"] /
        riesgo["Total"] * 100
    ).round(1)

    riesgo = riesgo.sort_values("Porcentaje",ascending=False)

    st.dataframe(riesgo)

    st.subheader("Detalle materiales en riesgo")

    detalle = df_filtro[
        df_filtro["Estado"].isin(["QUIEBRE","PELIGRO"])
    ]

    st.dataframe(detalle)

# ------------------------------------------------
# SOBRESTOCK
# ------------------------------------------------

with tab3:

    st.subheader("Resumen sobrestock")

    sobre = df_filtro[df_filtro["Estado"] == "SOBRESTOCK"]

    resumen = (
        sobre.groupby("Distrito")
        .size()
        .reset_index(name="Materiales sobrestock")
    )

    st.dataframe(resumen)

    st.subheader("Detalle sobrestock")

    st.dataframe(sobre)

# ------------------------------------------------
# COPILOT
# ------------------------------------------------

with tab4:

    pregunta = st.text_input("Ejemplo: inventario material 3500000072 BTA 89")

    if pregunta:

        pregunta = pregunta.lower()

        material = re.findall(r"\d{6,}",pregunta)
        material = material[0] if material else None

        pdv = re.findall(r"\d{2,}",pregunta)
        pdv = pdv[-1] if len(pdv)>1 else None

        datos = df_filtro.copy()

        if material:

            datos = datos[
                datos["Material"].astype(str)==material
            ]

        if pdv:

            datos = datos[
                datos["PDV"].astype(str).str.contains(pdv)
            ]

        st.dataframe(datos.head(50))
        st.write("Mostrando primeros 50 resultados")

# ------------------------------------------------
# PEDIDO SUGERIDO
# ------------------------------------------------

with tab5:

    cobertura_objetivo = st.number_input(
        "Cobertura objetivo",
        value=10
    )

    df_calc = df_filtro.copy()

    df_calc["Stock objetivo"] = (
        df_calc["Demanda diaria"] *
        cobertura_objetivo
    )

    df_calc["Necesidad"] = (
        df_calc["Stock objetivo"] -
        df_calc["Inventario total"]
    )

    df_calc["Necesidad"] = df_calc["Necesidad"].apply(lambda x:max(x,0))

    col_conv = None

    for c in df_calc.columns:
        if c.lower().strip() == "conv":
            col_conv = c

    if col_conv:

        df_calc["Pedido sugerido"] = df_calc.apply(
            lambda x:
            math.ceil(x["Necesidad"]/x[col_conv]) * x[col_conv]
            if x["Necesidad"]>0 else 0,
            axis=1
        )

    else:

        df_calc["Pedido sugerido"] = df_calc["Necesidad"]

    df_calc["Inventario futuro"] = (
        df_calc["Inventario total"] +
        df_calc["Pedido sugerido"]
    )

    df_calc["Cobertura futura"] = (
        df_calc["Inventario futuro"] /
        df_calc["Demanda diaria"]
    ).replace([float("inf")],0).fillna(0).round(1)

    df_calc["Necesidad"] = df_calc["Necesidad"].round(0)
    df_calc["Pedido sugerido"] = df_calc["Pedido sugerido"].round(0)
    df_calc["Inventario futuro"] = df_calc["Inventario futuro"].round(0)

    st.dataframe(df_calc)

    st.download_button(
        "Descargar pedido sugerido",
        df_calc.to_csv(index=False),
        "pedido_sugerido.csv"
    )

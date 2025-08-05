import streamlit as st
import pandas as pd

# -----------------------------
# 1. Cargar archivo Excel
# -----------------------------
@st.cache_data
def load_data():
    xls = pd.ExcelFile("MATRIZ RENTABILIDAD.xlsx")
    soja = pd.read_excel(xls, sheet_name='RENTABILIDAD SOJA')
    maiz = pd.read_excel(xls, sheet_name='RENTABILIDAD MAIZ')
    return soja, maiz

soja_df, maiz_df = load_data()

# -----------------------------
# 2. Sidebar: selección de cultivo
# -----------------------------
st.sidebar.title("Parámetros de Cálculo")
cultivo = st.sidebar.selectbox("Seleccionar cultivo:", ["Soja", "Maíz"])
df = soja_df.copy() if cultivo == "Soja" else maiz_df.copy()

# -----------------------------
# 3. Inputs de producción
# -----------------------------
st.sidebar.subheader("Producción")
precio = st.sidebar.number_input("Precio esperado (USD/TN)", value=300.0, step=5.0)
rinde = st.sidebar.number_input("Rinde esperado (Quintales/Ha)", value=30.0, step=1.0)
hectareas = st.sidebar.number_input("Hectáreas sembradas", value=100, step=10)

# -----------------------------
# 4. Inputs de costos
# -----------------------------
st.sidebar.subheader("Costos (USD/Ha)")
costo_insumos = st.sidebar.number_input("Insumos", value=450.0, step=10.0)
costo_labores = st.sidebar.number_input("Labores", value=150.0, step=10.0)
costo_alquiler = st.sidebar.number_input("Alquiler", value=200.0, step=10.0)
costo_admin = st.sidebar.number_input("Administración", value=50.0, step=5.0)
costo_seguros = st.sidebar.number_input("Seguros/Otros", value=20.0, step=5.0)

costo_total_ha = costo_insumos + costo_labores + costo_alquiler + costo_admin + costo_seguros

# -----------------------------
# 5. Cálculo de resultados
# -----------------------------
produccion_tn = (rinde * 0.1) * hectareas
ingreso_total = produccion_tn * precio
costo_total = hectareas * costo_total_ha
rentabilidad_total_usd = ingreso_total - costo_total
rentabilidad_pct = (rentabilidad_total_usd / costo_total) * 100 if costo_total != 0 else 0

# -----------------------------
# 6. Mostrar resultados
# -----------------------------
st.title("📊 Calculadora de Rentabilidad Agrícola")
st.markdown(f"### Cultivo seleccionado: **{cultivo}**")

col1, col2 = st.columns(2)
col1.metric("Rentabilidad total (USD)", f"{rentabilidad_total_usd:,.2f}")
col2.metric("Rentabilidad (%)", f"{rentabilidad_pct:,.2f}%")

# -----------------------------
# 7. Desglose de costos
# -----------------------------
st.markdown("### 💰 Desglose de Costos por Hectárea")
costos_df = pd.DataFrame({
    "Concepto": ["Insumos", "Labores", "Alquiler", "Administración", "Seguros/Otros", "Total"],
    "USD/Ha": [costo_insumos, costo_labores, costo_alquiler, costo_admin, costo_seguros, costo_total_ha]
})
st.dataframe(costos_df.style.format({"USD/Ha": "{:.2f}"}))

# -----------------------------
# 8. Tabla de sensibilidad (%)
# -----------------------------
st.subheader("📈 Sensibilidad de Rentabilidad (Precio vs Rinde)")

precio_range = [precio * x for x in [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]]
rinde_range = [rinde * x for x in [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]]

data = []
for r in rinde_range:
    row = []
    for p in precio_range:
        prod = (r * 0.1) * hectareas
        ingreso = prod * p
        rentab_pct = ((ingreso - costo_total) / costo_total) * 100 if costo_total != 0 else 0
        row.append(rentab_pct)
    data.append(row)

sens_df = pd.DataFrame(
    data,
    index=[f"{r:.1f}" for r in rinde_range],
    columns=[f"{int(p)}" for p in precio_range]
)
sens_df.index.name = "Rinde (qq/Ha) ↓"
sens_df.columns.name = "Precio (USD/TN) →"

def color_rentabilidad(val):
    try:
        val = float(val)
        return "background-color: #d9ead3; color: black;" if val > 0 else "background-color: #f4cccc; color: black;"
    except:
        return "background-color: #d9d9d9; color: black; font-weight: bold;"

st.dataframe(
    sens_df.style.applymap(color_rentabilidad)
    .format(lambda x: f"{x:,.1f}%" if isinstance(x, (int, float)) else x)
)



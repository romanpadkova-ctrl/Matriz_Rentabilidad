import streamlit as st
import pandas as pd
import numpy as np
from datetime import date

st.set_page_config(page_title="Suite Comercial", page_icon="📊", layout="wide")

# =========================
# Utilidades de formato
# =========================
def fmt_ars(x):
    """Formatea 1234567.89 -> 1.234.567,89"""
    try:
        s = f"{float(x):,.2f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return x

def unique_str_labels(vals, fmt_func):
    """
    Devuelve etiquetas string únicas, agregando un 'zero-width space' a duplicados.
    Visualmente quedan iguales; internamente son distintas y evitan el crash del Styler.
    """
    labels = [fmt_func(v) for v in vals]
    seen = {}
    out = []
    for lab in labels:
        if lab in seen:
            seen[lab] += 1
            out.append(lab + "\u200B" * seen[lab])  # agrega espacios invisibles
        else:
            seen[lab] = 0
            out.append(lab)
    return out

# =========================
# Selector principal
# =========================
st.sidebar.title("Suite Comercial")
herramienta = st.sidebar.radio(
    "Elegí una herramienta:",
    ["🏠 Home", "📊 Matriz de rentabilidad", "📄💵 Simulador de cheques"],
    index=0
)

# =========================
# CSS básico para “cards”
# =========================
st.markdown("""
<style>
.card {border-radius:16px; padding:18px 16px; background:#111418; border:1px solid #2a2f36;}
.card h3 {margin:0 0 6px 0; font-size:0.95rem; font-weight:600; color:#9fb3c8; display:flex; gap:6px; align-items:center;}
.card .value {font-size:1.6rem; font-weight:700; color:#e6eef7;}
.help {cursor:help; border-bottom:1px dotted #7f8b98;}
.costs {font-size:0.98rem; line-height:1.55;}
.costs .title {font-weight:800; letter-spacing:.5px; font-size:1.05rem; margin:6px 0;}
.costs .row {display:flex; justify-content:space-between; padding:6px 0;}
.costs .row span:first-child {color:#c9d6e2;}
.costs .total {border-top:1px solid #2a2f36; margin-top:8px; padding-top:10px; font-weight:800;}
.hero {border-radius:18px; padding:20px; background:#0e1116; border:1px solid #2a2f36;}
</style>
""", unsafe_allow_html=True)

# =========================
# 🏠 HOME
# =========================
if herramienta == "🏠 Home":
    st.title("🏠 Bienvenido a la Suite Comercial")
    st.markdown("""
    Esta **Suite Comercial** reúne herramientas simples y prácticas para tu gestión diaria,
    ayudándote a **simular escenarios** y **decidir** con mejor información.
    
    **Herramientas disponibles:**
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Matriz de rentabilidad")
        st.markdown("""
        Te da un **pantallazo visual** de cómo vienen los números de tu negocio: márgenes, equilibrio y escenarios posibles.  
        Úsala como **brújula** para fijar objetivos y definir la **estrategia comercial** (cuándo fijar, a qué precios y con qué rinde).
        """)
        st.info("Usá el menú lateral para entrar a *Matriz de rentabilidad*.")

    with col2:
        st.subheader("📄💵 Simulador de cheques")
        st.markdown("""
        Simulá el **neto a recibir** por el descuento de un cheque o el **nominal requerido**
        para alcanzar un neto objetivo. Elegí **base 360/365**, cargá **TNA**, **vencimiento**
        y **comisión**.
        """)
        st.info("Usá el menú lateral para entrar a *Simulador de cheques*.")

# =========================================================
# 📊 MATRIZ DE RENTABILIDAD (versión final con definiciones)
# =========================================================
elif herramienta == "📊 Matriz de rentabilidad":
    st.title("🌾 Matriz de Rentabilidad")

    # ------- Sidebar parámetros -------
    st.sidebar.subheader("Producción")
    cultivo = st.sidebar.selectbox("Cultivo", ["Soja", "Maíz"])
    precio = st.sidebar.number_input("Precio esperado (USD/TN)", value=300.0, step=5.0, format="%.2f")
    rinde = st.sidebar.number_input("Rinde esperado (qq/ha)", value=30.0, step=1.0, format="%.2f")
    hectareas = st.sidebar.number_input("Hectáreas", value=100, step=10, format="%d")

    st.sidebar.markdown("---")
    st.sidebar.subheader("INSUMOS")
    ins_agro = st.sidebar.number_input("Agroquímicos (USD/ha)", value=220.0, step=10.0, min_value=0.0, format="%.2f")
    ins_semillas = st.sidebar.number_input("Semillas (USD/ha)", value=130.0, step=10.0, min_value=0.0, format="%.2f")
    ins_fert = st.sidebar.number_input("Fertilizantes (USD/ha)", value=150.0, step=10.0, min_value=0.0, format="%.2f")

    st.sidebar.subheader("LABORES")
    lab_fumi = st.sidebar.number_input("Fumigación (USD/ha)", value=40.0, step=5.0, min_value=0.0, format="%.2f")
    lab_siembra = st.sidebar.number_input("Siembra (USD/ha)", value=60.0, step=5.0, min_value=0.0, format="%.2f")
    lab_cosecha = st.sidebar.number_input("Cosecha (USD/ha)", value=80.0, step=5.0, min_value=0.0, format="%.2f")

    st.sidebar.subheader("ALQUILER")
    alq_qq_ha = st.sidebar.number_input("Alquiler (qq/ha)", value=10.0, step=0.5, min_value=0.0, format="%.2f")
    precio_soja_alq = st.sidebar.number_input("Precio ref. soja alquiler (USD/TN)", value=300.0, step=5.0, min_value=0.0, format="%.2f")

    st.sidebar.subheader("COMERCIALIZACIÓN")
    gtos_comerc_tn = st.sidebar.number_input("Gastos comerciales (USD/TN)", value=35.0, step=1.0, min_value=0.0, format="%.2f")

    st.sidebar.subheader("OTROS")
    costo_admin = st.sidebar.number_input("Administración (USD/ha)", value=50.0, step=5.0, min_value=0.0, format="%.2f")
    costo_seguros = st.sidebar.number_input("Seguros / Otros (USD/ha)", value=20.0, step=5.0, min_value=0.0, format="%.2f")

    # ------- Cálculos (según definiciones acordadas) -------
    ton_ha = rinde * 0.1                               # qq/ha -> tn/ha
    ingreso_bruto_ha = ton_ha * precio                 # USD/ha
    ingreso_total = ingreso_bruto_ha * hectareas       # USD totales

    insumos_ha = ins_agro + ins_semillas + ins_fert
    labores_ha = lab_fumi + lab_siembra + lab_cosecha
    otros_ha = costo_admin + costo_seguros

    # Costo de cultivo (SIN alquiler ni gastos comerciales)
    costo_cultivo_ha = insumos_ha + labores_ha + otros_ha

    # Gastos comerciales (USD/ha) a partir de USD/TN
    gtos_comerc_ha = gtos_comerc_tn * ton_ha

    # Alquiler en USD/ha
    alq_tn_ha = alq_qq_ha * 0.1
    alq_usd_ha = alq_tn_ha * precio_soja_alq

    # Inversión = costo de cultivo + gastos comerciales (sin alquiler)
    inversion_ha = costo_cultivo_ha + gtos_comerc_ha

    # Costo total completo = costo de cultivo + gtos comerciales + alquiler
    costo_total_ha = inversion_ha + alq_usd_ha
    costo_total = costo_total_ha * hectareas

    # Márgenes
    margen_bruto_ha = ingreso_bruto_ha - costo_cultivo_ha
    margen_neto_ha = ingreso_bruto_ha - costo_total_ha

    # Rentabilidad sobre costo total
    rentabilidad_pct = (margen_neto_ha / costo_total_ha * 100) if costo_total_ha > 0 else 0.0

    # Break-evens usando costo total
    precio_equilibrio = (costo_total_ha / ton_ha) if ton_ha > 0 else 0.0
    rinde_equilibrio = (costo_total_ha / precio) / 0.1 if precio > 0 else 0.0  # qq/ha

    # ------- Cards -------
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"""<div class="card"><h3>Margen Bruto <span class="help" title="Ingreso bruto – costo de cultivo (sin alquiler ni gastos comerciales).">ℹ️</span></h3>
            <div class="value">{fmt_ars(margen_bruto_ha)} USD/ha</div></div>""",
            unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            f"""<div class="card"><h3>Margen Neto <span class="help" title="Ingreso bruto – (costo de cultivo + gastos comerciales + alquiler).">ℹ️</span></h3>
            <div class="value">{fmt_ars(margen_neto_ha)} USD/ha</div></div>""",
            unsafe_allow_html=True
        )
    with c3:
        st.markdown(
            f"""<div class="card"><h3>Rentabilidad <span class="help" title="(Margen neto / costo total) × 100, donde costo total = costo de cultivo + gastos comerciales + alquiler.">ℹ️</span></h3>
            <div class="value">{rentabilidad_pct:,.2f}%</div></div>""",
            unsafe_allow_html=True
        )
    with c4:
        st.markdown(
            f"""<div class="card"><h3>Inversión <span class="help" title="Costo de cultivo + gastos comerciales (sin alquiler).">ℹ️</span></h3>
            <div class="value">{fmt_ars(inversion_ha)} USD/ha</div></div>""",
            unsafe_allow_html=True
        )

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.markdown(
            f"""<div class="card"><h3>Precio de Equilibrio <span class="help" title="Costo total / tn por ha.">ℹ️</span></h3>
            <div class="value">{fmt_ars(precio_equilibrio)} USD/t</div></div>""",
            unsafe_allow_html=True
        )
    with c6:
        st.markdown(
            f"""<div class="card"><h3>Rinde de Equilibrio <span class="help" title="Costo total / precio, expresado en qq/ha.">ℹ️</span></h3>
            <div class="value">{rinde_equilibrio:,.2f} qq/ha</div></div>""",
            unsafe_allow_html=True
        )
    with c7:
        st.markdown(
            f"""<div class="card"><h3>Ingreso Total <span class="help" title="Ingreso bruto (USD/ha) × hectáreas.">ℹ️</span></h3>
            <div class="value">{fmt_ars(ingreso_total)} USD</div></div>""",
            unsafe_allow_html=True
        )
    with c8:
        st.markdown(
            f"""<div class="card"><h3>Costo de Cultivo <span class="help" title="Costos directos: Insumos + Labores + Admin/Seguros. Sin alquiler ni gastos comerciales.">ℹ️</span></h3>
            <div class="value">{fmt_ars(costo_cultivo_ha)} USD/ha</div></div>""",
            unsafe_allow_html=True
        )

    # ------- Desglose (lista limpia) -------
    st.markdown("### Desglose de Costos")
    st.markdown(f"""
    <div class="costs">
      <div class="title">INSUMOS</div>
      <div class="row"><span>Agroquímicos</span><span>{fmt_ars(ins_agro)} USD/ha</span></div>
      <div class="row"><span>Semillas</span><span>{fmt_ars(ins_semillas)} USD/ha</span></div>
      <div class="row"><span>Fertilizantes</span><span>{fmt_ars(ins_fert)} USD/ha</span></div>

      <div class="title" style="margin-top:10px;">LABORES</div>
      <div class="row"><span>Fumigación</span><span>{fmt_ars(lab_fumi)} USD/ha</span></div>
      <div class="row"><span>Siembra</span><span>{fmt_ars(lab_siembra)} USD/ha</span></div>
      <div class="row"><span>Cosecha</span><span>{fmt_ars(lab_cosecha)} USD/ha</span></div>

      <div class="title" style="margin-top:10px;">COMERCIALIZACIÓN</div>
      <div class="row"><span>Gastos comerciales</span><span>{fmt_ars(gtos_comerc_ha)} USD/ha <span style="opacity:.7">(= {fmt_ars(gtos_comerc_tn)} USD/TN × {ton_ha:.2f} tn/ha)</span></span></div>

      <div class="title" style="margin-top:10px;">ALQUILER</div>
      <div class="row"><span>Alquiler</span><span>{alq_qq_ha:,.2f} qq/ha</span></div>
      <div class="row"><span>Precio ref. soja alquiler</span><span>{fmt_ars(precio_soja_alq)} USD/t</span></div>
      <div class="row"><span>Alquiler (USD/ha)</span><span>{fmt_ars(alq_usd_ha)} USD/ha</span></div>

      <div class="row total"><span>Costo de cultivo (sin GC ni alquiler)</span><span>{fmt_ars(costo_cultivo_ha)} USD/ha</span></div>
      <div class="row"><span>Inversión (costo cultivo + GC)</span><span>{fmt_ars(inversion_ha)} USD/ha</span></div>
      <div class="row"><span>Costo total (incluye alquiler)</span><span>{fmt_ars(costo_total_ha)} USD/ha</span></div>
    </div>
    """, unsafe_allow_html=True)

    # ======= SENSIBILIDAD con escalas personalizables =======
    if "sens_step_rinde" not in st.session_state:
        st.session_state.sens_step_rinde = 2.0     # qq por paso
    if "sens_step_precio" not in st.session_state:
        st.session_state.sens_step_precio = 5.0    # USD/t por paso
    if "sens_pasos" not in st.session_state:
        st.session_state.sens_pasos = 5            # pasos por lado

    step_r = float(st.session_state.sens_step_rinde)
    step_p = float(st.session_state.sens_step_precio)
    pasos  = int(st.session_state.sens_pasos)

    rindes_vals = [max(0.0, rinde + k*step_r) for k in range(-pasos, pasos+1)]
    precios_vals = [max(0.0, precio + k*step_p) for k in range(-pasos, pasos+1)]

    st.markdown("### 📈 Sensibilidad de Rentabilidad (Precio × Rinde)")
    tabla = []
    for r_ in rindes_vals:
        fila = []
        prod_tn_ha = r_ * 0.1
        for p_ in precios_vals:
            ingreso_ha_s = prod_tn_ha * p_
            margen_neto_ha_s = ingreso_ha_s - costo_total_ha
            rentab_pct_s = (margen_neto_ha_s / costo_total_ha * 100) if costo_total_ha > 0 else 0.0
            fila.append(rentab_pct_s)
        tabla.append(fila)

    # Etiquetas únicas (invisiblemente únicas) para evitar crash si se repiten por redondeo/recorte a 0
    idx_labels = unique_str_labels(rindes_vals, lambda v: f"{v:,.1f}")
    col_labels = unique_str_labels(precios_vals, lambda v: f"{v:,.2f}")

    sens_df = pd.DataFrame(tabla, index=idx_labels, columns=col_labels)
    sens_df.index.name = "Rinde (qq/ha) ↓"
    sens_df.columns.name = "Precio (USD/TN) →"

    def colorize(df: pd.DataFrame):
        arr = df.to_numpy(dtype=float)
        styles = np.empty(arr.shape, dtype=object)
        mask = arr >= 0
        styles[mask] = "background-color:#1e3b2c;color:#e6f4ea;"
        styles[~mask] = "background-color:#3a1e1e;color:#fdebea;"
        return pd.DataFrame(styles, index=df.index, columns=df.columns)

    st.dataframe(
        sens_df.style.apply(colorize, axis=None).format("{:.1f}%"),
        height=420, use_container_width=True
    )

    # Controles de escala
    st.markdown("#### ⚙️ Escalas de la sensibilidad")
    e1, e2, e3 = st.columns(3)
    with e1:
        new_step_r = st.number_input("Escala rinde (qq por paso)", value=step_r, step=0.5, min_value=0.1, format="%.2f")
    with e2:
        new_step_p = st.number_input("Escala precio (USD/t por paso)", value=step_p, step=1.0, min_value=0.5, format="%.2f")
    with e3:
        new_pasos = st.number_input("Pasos por lado", value=pasos, min_value=1, max_value=25, step=1)

    if st.button("Aplicar escalas", type="primary"):
        st.session_state.sens_step_rinde = float(new_step_r)
        st.session_state.sens_step_precio = float(new_step_p)
        st.session_state.sens_pasos = int(new_pasos)
        st.rerun()

    st.caption("Definiciones: Margen Bruto = Ingreso bruto – Costo de cultivo (sin alquiler ni gastos comerciales). "
               "Margen Neto = Ingreso bruto – (Costo de cultivo + Gastos comerciales + Alquiler). "
               "Inversión = Costo de cultivo + Gastos comerciales. "
               "Costo total = Costo de cultivo + Gastos comerciales + Alquiler.")

# =========================================================
# 📄💵 SIMULADOR DE CHEQUES (tu versión final)
# =========================================================
else:
    st.title("📄💵 Simulador de descuento de cheques")

    top1, top2, top3 = st.columns(3)
    with top1:
        fecha_operacion = st.date_input("📅 Fecha de operación", value=date.today(), format="DD/MM/YYYY")
    with top2:
        comision_pct = st.number_input("Comisión / gastos (% sobre nominal)", value=0.00, step=0.10, format="%.2f")
    with top3:
        base_dias = st.selectbox("Base de días", ["360", "365"], index=0)

    st.markdown("### Datos del cheque")
    c1, c2, c3 = st.columns(3)
    with c1:
        venc = st.date_input("Vencimiento", value=date.today(), format="DD/MM/YYYY")
    with c2:
        tna = st.number_input("TNA (% nominal anual)", value=45.00, step=0.10, format="%.2f")
    with c3:
        importe = st.number_input("Importe del cheque ($)", value=100000.00, step=1000.00, format="%.2f")

    dias = max((pd.to_datetime(venc) - pd.to_datetime(fecha_operacion)).days, 0)
    st.caption(f"Días hasta vencimiento: **{dias}** (se calcula automáticamente)")

    st.divider()

    modo_inverso = st.toggle("🧮 Calcular por neto objetivo (modo inverso)")

    base = 360 if base_dias == "360" else 365
    r_periodo = (tna / 100.0) * (dias / base)  # tasa del período por TNA

    if not modo_inverso:
        st.subheader("▶️ Modo directo: Neto disponible")
        neto = importe * max(0.0, 1.0 - r_periodo) * (1.0 - comision_pct/100.0)
        tasa_directa_total = (r_periodo + comision_pct/100.0) * 100.0

        m1, m2, m3 = st.columns(3)
        m1.metric("💵 Importe nominal", f"${fmt_ars(importe)}")
        m2.metric("✅ Neto disponible", f"${fmt_ars(neto)}")
        m3.metric("📈 TNA", f"{tna:,.2f}%")

        cA, cB = st.columns(2)
        cA.metric("🧮 Tasa directa total (período)", f"{tasa_directa_total:,.2f}%")
        cB.metric("📅 Período (días)", f"{dias}")

        st.caption("• Neto = Importe × (1 − TNA × días/base) × (1 − comisión).  • Tasa directa total = (TNA × días/base + comisión).")

    else:
        st.subheader("▶️ Modo inverso: Nominal requerido para un neto objetivo")
        neto_obj = st.number_input("Neto objetivo ($)", value=100000.00, step=1000.00, format="%.2f")

        denom = (1.0 - r_periodo) * (1.0 - comision_pct/100.0)
        if denom <= 0:
            st.error("Con esos parámetros el neto no es alcanzable (tasa y/o comisión demasiado altas o plazo muy largo).")
        else:
            nominal_req = neto_obj / denom
            tasa_directa_total = (r_periodo + comision_pct/100.0) * 100.0

            m1, m2, m3 = st.columns(3)
            m1.metric("🎯 Neto objetivo", f"${fmt_ars(neto_obj)}")
            m2.metric("🧾 Nominal requerido", f"${fmt_ars(nominal_req)}")
            m3.metric("📈 TNA", f"{tna:,.2f}%")

            cA, cB = st.columns(2)
            cA.metric("🧮 Tasa directa total (período)", f"{tasa_directa_total:,.2f}%")
            cB.metric("📅 Período (días)", f"{dias}")

            st.caption("• Nominal = Neto / [(1 − TNA × días/base) × (1 − comisión)].  • Tasa directa total = (TNA × días/base + comisión).")

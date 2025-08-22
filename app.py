import os
import io
import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime, timezone

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

def num_input_blank(label, placeholder="", key=None, help=None, parent=st):
    """
    Text input que permite vacío y formato AR (puntos miles, coma decimal).
    Devuelve float o None.
    """
    s = parent.text_input(label, value="", placeholder=placeholder, key=key, help=help)
    if s.strip() == "":
        return None
    try:
        s_norm = s.replace(".", "").replace(",", ".")
        return float(s_norm)
    except ValueError:
        parent.warning(f"“{label}” no es un número válido.")
        return None

def unique_str_labels(vals, fmt_func):
    """
    Etiquetas string únicas (agrega zero-width spaces a duplicados)
    para que el Styler no crashee si hay columnas/filas repetidas.
    """
    labels = [fmt_func(v) for v in vals]
    seen = {}
    out = []
    for lab in labels:
        if lab in seen:
            seen[lab] += 1
            out.append(lab + "\u200B" * seen[lab])
        else:
            seen[lab] = 0
            out.append(lab)
    return out

# =========================
# DB helpers (Postgres con fallback a CSV)
# =========================
def get_db_conn():
    """Devuelve conexión psycopg2 o None si no hay DATABASE_URL."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return None
    try:
        import psycopg2
        conn = psycopg2.connect(url)
        return conn
    except Exception as e:
        st.warning(f"No pude conectar a Postgres ({e}). Uso CSV local.")
        return None

def init_db(conn):
    """Crea tabla si no existe."""
    if conn is None:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
              id SERIAL PRIMARY KEY,
              ts TIMESTAMPTZ NOT NULL,
              cultivo TEXT,
              acopio TEXT,
              cliente TEXT,
              comercial TEXT,
              producto TEXT,
              posicion TEXT,
              precio_objetivo NUMERIC,
              precio_spot NUMERIC,
              rinde NUMERIC,
              hectareas NUMERIC
            );
            """)
            conn.commit()
    except Exception as e:
        st.warning(f"No pude inicializar la tabla en Postgres: {e}")

def save_alert(payload: dict):
    """
    Guarda en Postgres si hay DB; si no, en CSV local 'alerts.csv'.
    """
    conn = get_db_conn()
    if conn:
        try:
            init_db(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO alerts
                       (ts, cultivo, acopio, cliente, comercial, producto, posicion,
                        precio_objetivo, precio_spot, rinde, hectareas)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       RETURNING id;""",
                    (
                        payload["ts"], payload["cultivo"], payload["acopio"],
                        payload["cliente"], payload["comercial"], payload["producto"],
                        payload["posicion"], payload["precio_objetivo"],
                        payload["precio_spot"], payload["rinde"], payload["hectareas"]
                    )
                )
                _new_id = cur.fetchone()[0]
                conn.commit()
            conn.close()
            return ("db", None)
        except Exception as e:
            try:
                conn.close()
            except:
                pass
            return ("db_error", str(e))

    # Fallback CSV
    try:
        df_row = pd.DataFrame([payload])
        csv_path = "alerts.csv"
        if os.path.exists(csv_path):
            df_old = pd.read_csv(csv_path)
            # emular ID autoincremental simple para CSV
            next_id = (df_old.get("id").max() + 1) if "id" in df_old.columns and not df_old.empty else 1
            df_row.insert(0, "id", next_id)
            df = pd.concat([df_old, df_row], ignore_index=True)
        else:
            df_row.insert(0, "id", 1)
            df = df_row
        df.to_csv(csv_path, index=False)
        return ("csv", csv_path)
    except Exception as e:
        return ("csv_error", str(e))

def load_alerts():
    """
    Carga alertas desde Postgres o CSV. Devuelve (origen, df) donde origen ∈ {"db","csv"}.
    """
    conn = get_db_conn()
    if conn:
        try:
            init_db(conn)
            df = pd.read_sql_query("SELECT * FROM alerts ORDER BY id DESC;", conn)
            conn.close()
            return ("db", df)
        except Exception as e:
            try:
                conn.close()
            except:
                pass
            st.warning(f"No pude leer Postgres ({e}). Intento CSV.")
    # CSV
    csv_path = "alerts.csv"
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        return ("csv", df)
    return ("csv", pd.DataFrame())

def delete_alerts_by_ids(id_list):
    """
    Borra por IDs (lista de ints). Soporta Postgres y CSV.
    """
    if not id_list:
        return ("none", 0, None)

    conn = get_db_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM alerts WHERE id = ANY(%s);", (id_list,))
                deleted = cur.rowcount
                conn.commit()
            conn.close()
            return ("db", deleted, None)
        except Exception as e:
            try:
                conn.close()
            except:
                pass
            return ("db_error", 0, str(e))

    # CSV
    try:
        csv_path = "alerts.csv"
        if not os.path.exists(csv_path):
            return ("csv", 0, None)
        df = pd.read_csv(csv_path)
        if "id" not in df.columns or df.empty:
            return ("csv", 0, None)
        before = len(df)
        df = df[~df["id"].isin(id_list)]
        after = len(df)
        deleted = before - after
        df.to_csv(csv_path, index=False)
        return ("csv", deleted, None)
    except Exception as e:
        return ("csv_error", 0, str(e))

# =========================
# Selector principal
# =========================
st.sidebar.title("Suite Comercial")
herramienta = st.sidebar.radio(
    "Elegí una herramienta:",
    ["🏠 Home", "📊 Matriz de rentabilidad", "📄💵 Simulador de cheques", "🛒🌱 Financiación de insumos (ARS)"],
    index=0
)

# =========================
# CSS
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
.small {opacity:.75; font-size:.9rem}
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

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("📊 Matriz de rentabilidad")
        st.markdown("""
        Te da un **pantallazo visual** de cómo vienen los números de tu negocio: márgenes, equilibrio y escenarios posibles.  
        Úsala como **brújula** para fijar objetivos y definir la **estrategia comercial** (cuándo fijar, a qué precios y con qué rinde).
        """)
        st.info("Usá el menú lateral para entrar a *Matriz de rentabilidad*.")

    with c2:
        st.subheader("📄💵 Simulador de cheques")
        st.markdown("""
        Simulá el **neto a recibir** por el descuento de un cheque o el **nominal requerido**
        para alcanzar un neto objetivo. Elegí **base 360/365**, cargá **TNA**, **vencimiento**
        y **comisión**.
        """)
        st.info("Usá el menú lateral para entrar a *Simulador de cheques*.")

    st.markdown("---")
    st.subheader("🛒🌱 Financiación de insumos (ARS)")
    st.markdown("""
    Calculá rápido una **compra de insumos financiada**: partís de un monto en USD, aplicás una **tasa en USD** por meses,
    y lo convertís a **pesos** con un **tipo de cambio futuro**.  
    Te devuelve la **tasa implícita de pesificación (TNA)** y la **tasa real del negocio del período** (con su **TNA** equivalente).
    """)
    st.info("Usá el menú lateral para entrar a *Financiación de insumos (ARS)*.")

    # ---------- Admin oculto ----------
    st.markdown("---")
    with st.expander("🔐 Admin"):
        admin_pin_env = os.environ.get("ADMIN_PIN", "").strip()
        pin_in = st.text_input("PIN de administrador", type="password")
        if admin_pin_env and pin_in == admin_pin_env:
            st.success("Acceso concedido.")
            origen, df_alertas = load_alerts()
            st.caption(f"Origen de datos: **{origen}**")

            # Mostrar resumen
            if df_alertas is not None and not df_alertas.empty:
                st.markdown("**Vista rápida de alertas (últimas 200):**")
                st.dataframe(df_alertas.head(200))

                # --- Botón Descargar Excel (FIX TZ) ---
                if st.button("⬇️ Descargar alertas en Excel"):
                    # FIX universal: quitar tz antes de exportar para evitar crash en Excel
                    if "ts" in df_alertas.columns:
                        df_alertas["ts"] = pd.to_datetime(
                            df_alertas["ts"], errors="coerce", utc=True
                        ).dt.tz_localize(None)

                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                        df_alertas.to_excel(writer, index=False, sheet_name="alertas")
                    st.download_button(
                        label="Descargar archivo .xlsx",
                        data=buffer.getvalue(),
                        file_name=f"alertas_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )

                # --- Borrado por ID(s) ---
                st.markdown("### 🗑️ Borrar alertas por ID")
                ids_str = st.text_input("IDs a borrar (separados por coma)", placeholder="Ej: 12, 15, 19")
                if st.button("Borrar seleccionadas"):
                    try:
                        id_list = [int(x.strip()) for x in ids_str.split(",") if x.strip().isdigit()]
                    except:
                        id_list = []
                    if not id_list:
                        st.warning("Ingresá al menos un ID válido.")
                    else:
                        where, deleted, err = delete_alerts_by_ids(id_list)
                        if err:
                            st.error(f"Error al borrar: {err}")
                        else:
                            st.success(f"Eliminadas {deleted} alerta(s) en {where}. Volvé a abrir el Admin para refrescar la vista.")
            else:
                st.info("No hay alertas cargadas todavía.")
        else:
            if pin_in:
                st.error("PIN incorrecto.")

# =========================================================
# 📊 MATRIZ DE RENTABILIDAD
# =========================================================
elif herramienta == "📊 Matriz de rentabilidad":
    ICONO_CULTIVO = {"Soja": "🌱", "Maíz": "🌽", "Trigo": "🌾"}

    st.sidebar.subheader("Producción")
    cultivo  = st.sidebar.selectbox("Cultivo", ["Soja", "Maíz", "Trigo"])
    precio   = num_input_blank("Precio esperado (USD/TN)", placeholder="Ej: 300,00", key="m_precio", parent=st.sidebar)
    rinde    = num_input_blank("Rinde esperado (qq/ha)",    placeholder="Ej: 30,0",   key="m_rinde",  parent=st.sidebar)
    hectareas= num_input_blank("Hectáreas",                 placeholder="Ej: 100",    key="m_hect",   parent=st.sidebar)

    st.sidebar.markdown("---")
    st.sidebar.subheader("INSUMOS")
    ins_agro     = num_input_blank("Agroquímicos (USD/ha)",  placeholder="Ej: 220", key="m_ins_agro", parent=st.sidebar)
    ins_semillas = num_input_blank("Semillas (USD/ha)",      placeholder="Ej: 130", key="m_ins_sem",  parent=st.sidebar)
    ins_fert     = num_input_blank("Fertilizantes (USD/ha)", placeholder="Ej: 150", key="m_ins_fert", parent=st.sidebar)

    st.sidebar.subheader("LABORES")
    lab_fumi    = num_input_blank("Fumigación (USD/ha)", placeholder="Ej: 40", key="m_lab_fumi", parent=st.sidebar)
    lab_siembra = num_input_blank("Siembra (USD/ha)",    placeholder="Ej: 60", key="m_lab_siem", parent=st.sidebar)
    lab_cosecha = num_input_blank("Cosecha (USD/ha)",    placeholder="Ej: 80", key="m_lab_cose", parent=st.sidebar)

    st.sidebar.subheader("ALQUILER")
    alq_qq_ha       = num_input_blank("Alquiler (qq/ha)",                   placeholder="Ej: 10",  key="m_alq_qq", parent=st.sidebar)
    precio_soja_alq = num_input_blank("Precio ref. soja alquiler (USD/TN)", placeholder="Ej: 300", key="m_alq_tc", parent=st.sidebar)

    st.sidebar.subheader("COMERCIALIZACIÓN")
    gtos_comerc_tn = num_input_blank("Gastos comerciales (USD/TN)", placeholder="Ej: 35", key="m_gc_tn", parent=st.sidebar)

    st.sidebar.subheader("OTROS")
    costo_admin   = num_input_blank("Administración (USD/ha)",  placeholder="Ej: 50", key="m_admin",  parent=st.sidebar)
    costo_seguros = num_input_blank("Seguros / Otros (USD/ha)", placeholder="Ej: 20", key="m_seguros",parent=st.sidebar)

    st.title(f"{ICONO_CULTIVO.get(cultivo, '🌾')} Matriz de Rentabilidad")

    required = [precio, rinde, hectareas,
                ins_agro, ins_semillas, ins_fert,
                lab_fumi, lab_siembra, lab_cosecha,
                alq_qq_ha, precio_soja_alq,
                gtos_comerc_tn, costo_admin, costo_seguros]
    if any(v is None for v in required):
        st.info("➡️ Completá los campos en la barra lateral para ver los resultados.")
        st.stop()

    # Cálculos básicos
    ton_ha = rinde * 0.1
    ingreso_bruto_ha = ton_ha * precio
    ingreso_total = ingreso_bruto_ha * hectareas

    insumos_ha = ins_agro + ins_semillas + ins_fert
    labores_ha = lab_fumi + lab_siembra + lab_cosecha
    otros_ha = costo_admin + costo_seguros
    costo_cultivo_ha = insumos_ha + labores_ha + otros_ha

    gtos_comerc_ha = gtos_comerc_tn * ton_ha
    alq_tn_ha = alq_qq_ha * 0.1
    alq_usd_ha = alq_tn_ha * precio_soja_alq

    inversion_ha = costo_cultivo_ha + gtos_comerc_ha
    costo_total_ha = inversion_ha + alq_usd_ha
    costo_total = costo_total_ha * hectareas

    margen_bruto_ha = ingreso_bruto_ha - costo_cultivo_ha
    margen_neto_ha = ingreso_bruto_ha - costo_total_ha
    rentabilidad_pct = (margen_neto_ha / costo_total_ha * 100) if costo_total_ha > 0 else 0.0

    precio_equilibrio = (costo_total_ha / ton_ha) if ton_ha > 0 else 0.0
    rinde_equilibrio = (costo_total_ha / precio) / 0.1 if precio > 0 else 0.0

    # Cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="card"><h3>Margen Bruto <span class="help" title="Ingreso bruto – costo de cultivo (sin alquiler ni gastos comerciales).">ℹ️</span></h3>
        <div class="value">{fmt_ars(margen_bruto_ha)} USD/ha</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="card"><h3>Margen Neto <span class="help" title="Ingreso bruto – (costo de cultivo + gastos comerciales + alquiler).">ℹ️</span></h3>
        <div class="value">{fmt_ars(margen_neto_ha)} USD/ha</div></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="card"><h3>Rentabilidad <span class="help" title="(Margen neto / costo total) × 100.">ℹ️</span></h3>
        <div class="value">{rentabilidad_pct:,.2f}%</div></div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class="card"><h3>Inversión <span class="help" title="Costo de cultivo + gastos comerciales (sin alquiler).">ℹ️</span></h3>
        <div class="value">{fmt_ars(inversion_ha)} USD/ha</div></div>""", unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.markdown(f"""<div class="card"><h3>Precio de Equilibrio <span class="help" title="Costo total / tn por ha.">ℹ️</span></h3>
        <div class="value">{fmt_ars(precio_equilibrio)} USD/t</div></div>""", unsafe_allow_html=True)
    with c6:
        st.markdown(f"""<div class="card"><h3>Rinde de Equilibrio <span class="help" title="Costo total / precio, en qq/ha.">ℹ️</span></h3>
        <div class="value">{rinde_equilibrio:,.2f} qq/ha</div></div>""", unsafe_allow_html=True)
    with c7:
        st.markdown(f"""<div class="card"><h3>Ingreso Total <span class="help" title="Ingreso bruto (USD/ha) × hectáreas.">ℹ️</span></h3>
        <div class="value">{fmt_ars(ingreso_total)} USD</div></div>""", unsafe_allow_html=True)
    with c8:
        st.markdown(f"""<div class="card"><h3>Costo de Cultivo <span class="help" title="Insumos + Labores + Admin/Seguros (sin alquiler ni GC).">ℹ️</span></h3>
        <div class="value">{fmt_ars(costo_cultivo_ha)} USD/ha</div></div>""", unsafe_allow_html=True)

    # ====== Formulario de Alertas ======
    st.markdown("### 📬 Enviar alerta comercial")
    with st.form("form_alerta"):
        a1, a2, a3 = st.columns(3)
        with a1:
            acopio   = st.text_input("Acopio", placeholder="Ej: Acopio SA")
        with a2:
            cliente  = st.text_input("Cliente", placeholder="Ej: Campo Los Álamos")
        with a3:
            comercial = st.text_input("Comercial", placeholder="Ej: Juan Pérez")

        b1, b2, b3 = st.columns(3)
        with b1:
            producto = st.text_input("Producto", placeholder="Ej: Soja Mayo")
        with b2:
            posicion = st.text_input("Posición", placeholder="Ej: Mayo 25 / Disp.")
        with b3:
            precio_obj = num_input_blank("Precio objetivo (USD/TN)", placeholder="Ej: 310,00", key="alert_precio", parent=st)

        enviado = st.form_submit_button("Guardar alerta")

    if enviado:
        if not all([acopio.strip(), cliente.strip(), comercial.strip(), producto.strip(), posicion.strip()]) or precio_obj is None:
            st.error("Completá todos los campos del formulario de alerta.")
        else:
            payload = {
                # guardamos con tz (UTC) para consistencia; al exportar quitamos tz
                "ts": datetime.now(timezone.utc).isoformat(),
                "cultivo": cultivo,
                "acopio": acopio.strip(),
                "cliente": cliente.strip(),
                "comercial": comercial.strip(),
                "producto": producto.strip(),
                "posicion": posicion.strip(),
                "precio_objetivo": float(precio_obj),
                "precio_spot": float(precio),
                "rinde": float(rinde),
                "hectareas": float(hectareas),
            }
            where, info = save_alert(payload)
            if where == "db":
                st.success("✅ Alerta guardada en Postgres.")
            elif where == "csv":
                st.success(f"✅ Alerta guardada en CSV local ({info}).")
            else:
                st.error(f"❌ No pude guardar la alerta ({info}).")

    # ====== Sensibilidad ======
    if "sens_step_rinde" not in st.session_state:
        st.session_state.sens_step_rinde = 2.0
    if "sens_step_precio" not in st.session_state:
        st.session_state.sens_step_precio = 5.0
    if "sens_pasos" not in st.session_state:
        st.session_state.sens_pasos = 5

    step_r = float(st.session_state.sens_step_rinde)
    step_p = float(st.session_state.sens_step_precio)
    pasos  = int(st.session_state.sens_pasos)

    rindes_vals  = [max(0.0, rinde  + k*step_r) for k in range(-pasos, pasos+1)]
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

    idx_labels = unique_str_labels(rindes_vals,  lambda v: f"{v:,.1f}")
    col_labels = unique_str_labels(precios_vals, lambda v: f"{v:,.2f}")

    sens_df = pd.DataFrame(tabla, index=idx_labels, columns=col_labels)
    sens_df.index.name = "Rinde (qq/ha) ↓"
    sens_df.columns.name = "Precio (USD/TN) →"

    def colorize(df: pd.DataFrame):
        arr = df.to_numpy(dtype=float)
        styles = np.empty(arr.shape, dtype=object)
        mask = arr >= 0
        styles[mask]  = "background-color:#1e3b2c;color:#e6f4ea;"
        styles[~mask] = "background-color:#3a1e1e;color:#fdebea;"
        return pd.DataFrame(styles, index=df.index, columns=df.columns)

    st.dataframe(
        sens_df.style.apply(colorize, axis=None).format("{:.1f}%"),
        height=420, use_container_width=True
    )

    st.markdown("#### ⚙️ Escalas de la sensibilidad")
    e1, e2, e3 = st.columns(3)
    with e1:
        new_step_r = st.number_input("Escala rinde (qq por paso)", value=step_r, step=0.5, min_value=0.1, format="%.2f")
    with e2:
        new_step_p = st.number_input("Escala precio (USD/t por paso)", value=step_p, step=1.0, min_value=0.5, format="%.2f")
    with e3:
        new_pasos = st.number_input("Pasos por lado", value=pasos, min_value=1, max_value=25, step=1)

    if st.button("Aplicar escalas", type="primary"):
        st.session_state.sens_step_rinde  = float(new_step_r)
        st.session_state.sens_step_precio = float(new_step_p)
        st.session_state.sens_pasos       = int(new_pasos)
        st.rerun()

    st.caption("Definiciones: Margen Bruto = Ingreso bruto – Costo de cultivo (sin alquiler ni gastos comerciales). "
               "Margen Neto = Ingreso bruto – (Costo de cultivo + Gastos comerciales + Alquiler). "
               "Inversión = Costo de cultivo + Gastos comerciales. "
               "Costo total = Costo de cultivo + Gastos comerciales + Alquiler.")

# =========================================================
# 📄💵 SIMULADOR DE CHEQUES
# =========================================================
elif herramienta == "📄💵 Simulador de cheques":
    st.title("📄💵 Simulador de descuento de cheques")

    top1, top2, top3 = st.columns(3)
    with top1:
        fecha_operacion = st.date_input("📅 Fecha de operación", value=date.today(), format="DD/MM/YYYY")
    with top2:
        comision_pct = num_input_blank("Comisión / gastos (% sobre nominal)", placeholder="Ej: 3,50", key="ch_com", parent=st)
    with top3:
        base_dias = st.selectbox("Base de días", ["360", "365"], index=1)

    st.markdown("### Datos del cheque")
    c1, c2, c3 = st.columns(3)
    with c1:
        venc = st.date_input("Vencimiento", value=date.today(), format="DD/MM/YYYY")
    with c2:
        tna = num_input_blank("TNA (% nominal anual)", placeholder="Ej: 45,00", key="ch_tna", parent=st)
    with c3:
        importe = num_input_blank("Importe del cheque ($)", placeholder="Ej: 1.000.000", key="ch_imp", parent=st)

    dias = max((pd.to_datetime(venc) - pd.to_datetime(fecha_operacion)).days, 0)
    st.caption(f"Días hasta vencimiento: **{dias}** (se calcula automáticamente)")
    st.divider()

    if tna is None or importe is None or comision_pct is None:
        st.info("➡️ Completá TNA, Comisión e Importe para calcular.")
        st.stop()

    modo_inverso = st.toggle("🧮 Calcular por neto objetivo (modo inverso)")
    base = 360 if base_dias == "360" else 365
    r_periodo = (tna / 100.0) * (dias / base)

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
        neto_obj = num_input_blank("Neto objetivo ($)", placeholder="Ej: 1.000.000", key="ch_neto_obj", parent=st)
        if neto_obj is None:
            st.info("Ingresá el Neto objetivo para calcular.")
            st.stop()
        denom = (1.0 - r_periodo) * (1.0 - comision_pct/100.0)
        if denom <= 0:
            st.error("Con esos parámetros el neto no es alcanzable.")
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
            st.caption("• Nominal = Neto / [(1 − TNA × días/base) × (1 − comisión)].")

# =========================================================
# 🛒🌱 FINANCIACIÓN DE INSUMOS (ARS)
# =========================================================
else:
    st.title("🛒🌱 Financiación de insumos (ARS)")

    # Inputs (por fechas, sin toggle)
    t1, t2, t3 = st.columns(3)
    with t1:
        usd_inicial = num_input_blank("Monto inicial (USD)", placeholder="Ej: 50.000", key="fi_usd_ini", parent=st)
    with t2:
        tna_usd_mensual = num_input_blank("Tasa de financiación en USD (mensual, %)", placeholder="Ej: 0,70", key="fi_tna_m", parent=st)
    with t3:
        fecha_inicio = st.date_input("Fecha inicio", value=date.today(), format="DD/MM/YYYY")
        fecha_venc   = st.date_input("Fecha vencimiento", value=date.today(), format="DD/MM/YYYY")

    t4, t5 = st.columns(2)
    with t4:
        tc_spot = num_input_blank("Tipo de cambio SPOT (hoy)", placeholder="Ej: 1.308,33", key="fi_tc_spot", parent=st)
    with t5:
        tc_futuro = num_input_blank("Tipo de cambio FUTURO (vencimiento)", placeholder="Ej: 1.665,66", key="fi_tc_fut", parent=st)

    # Meses desde fechas
    dias = max((pd.to_datetime(fecha_venc) - pd.to_datetime(fecha_inicio)).days, 0)
    meses_calc = round(dias / 30, 1) if dias > 0 else 0
    st.caption(f"Meses estimados por fechas: **{meses_calc}** (días={dias})")

    if any(v is None for v in [usd_inicial, tna_usd_mensual, tc_spot, tc_futuro]) or meses_calc <= 0:
        st.info("➡️ Completá: Monto USD, Tasa mensual USD, TC spot, TC futuro y un período válido (fechas con meses>0).")
        st.stop()

    # Cálculos
    r_m_usd = tna_usd_mensual / 100.0
    monto_final_usd = usd_inicial * ((1 + r_m_usd) ** meses_calc)

    monto_inicial_ars = usd_inicial * tc_spot
    monto_final_ars = monto_final_usd * tc_futuro

    r_m_pesif = (tc_futuro / tc_spot) ** (1/meses_calc) - 1
    tna_pesif = (1 + r_m_pesif) ** 12 - 1

    tasa_real_periodo = (monto_final_ars / monto_inicial_ars) - 1 if monto_inicial_ars > 0 else 0.0
    tna_equiv_total   = (1 + tasa_real_periodo) ** (12/meses_calc) - 1

    # Tarjetas
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f"""<div class="card"><h3>Monto final (USD) <span class="help" title="Monto inicial USD capitalizado por la tasa mensual en USD durante el período.">ℹ️</span></h3>
            <div class="value">{fmt_ars(monto_final_usd)} USD</div></div>""",
            unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            f"""<div class="card"><h3>Monto final (ARS) <span class="help" title="Monto final USD × TC futuro.">ℹ️</span></h3>
            <div class="value">${fmt_ars(monto_final_ars)}</div></div>""",
            unsafe_allow_html=True
        )

    c3, c4 = st.columns(2)
    with c3:
        # TNA principal grande + detalle del período
        st.markdown(
            f"""<div class="card"><h3>TNA del negocio completo <span class="help" title="TNA equivalente de todo el negocio (financiación en USD + pesificación) para el período analizado.">ℹ️</span></h3>
            <div class="value">{tna_equiv_total*100:,.2f}%</div>
            <div class="small">Tasa real del período: {tasa_real_periodo*100:,.2f}%</div></div>""",
            unsafe_allow_html=True
        )
    with c4:
        st.markdown(
            f"""<div class="card"><h3>Tasa implícita de pesificación (TNA) <span class="help" title="Equivalente anual del movimiento del tipo de cambio (TC futuro / TC spot) en el período.">ℹ️</span></h3>
            <div class="value">{tna_pesif*100:,.2f}%</div></div>""",
            unsafe_allow_html=True
        )

    # Detalle
    st.markdown("### Detalle")
    d1, d2 = st.columns(2)

    with d1:
        st.markdown("**Financiación en USD**")
        st.markdown(f"""
- Monto inicial: **{fmt_ars(usd_inicial)} USD**
- Tasa mensual USD: **{tna_usd_mensual:,.2f}%**
- Meses: **{meses_calc}**
- Monto final USD (compuesto): **{fmt_ars(monto_final_usd)} USD**
""")
        st.markdown(
            '<span class="small">Fórmula: MontoUSD_f = MontoUSD_0 × (1 + r_mensual)^(meses)</span>',
            unsafe_allow_html=True
        )

    with d2:
        st.markdown("**Pesificación**")
        st.markdown(f"""
- TC Spot: **${fmt_ars(tc_spot)}**
- TC Futuro: **${fmt_ars(tc_futuro)}**
- Monto inicial en pesos: **${fmt_ars(monto_inicial_ars)}**
- Monto final en pesos: **${fmt_ars(monto_final_ars)}**
""")
        st.markdown(
            '<span class="small">Tasa real período = (MontoARS_f / MontoARS_0) − 1. &nbsp;•&nbsp; TNA real = (1 + tasa_período)^(12/meses) − 1. &nbsp;•&nbsp; TNA pesificación = ((TC_futuro/TC_spot)^(1/meses))^12 − 1.</span>',
            unsafe_allow_html=True
        )

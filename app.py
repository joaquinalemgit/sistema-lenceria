import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

st.set_page_config(page_title="Gestión Lencería", layout="wide")

def get_db_connection():
    conn = sqlite3.connect('lenceria_master.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos (codigo TEXT PRIMARY KEY, descripcion TEXT, proveedor TEXT, precio_costo REAL, precio_venta REAL, stock_actual INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, metodo_pago TEXT, total REAL)''')
    # Tabla nueva para historial de cierres
    cursor.execute('''CREATE TABLE IF NOT EXISTS cierres_caja (fecha_cierre DATE PRIMARY KEY, total_efectivo REAL, total_mp REAL, total_transferencia REAL, total_tarjeta REAL, total_general REAL)''')
    conn.commit()
    conn.close()

init_db()

# Logo y Título
col_l1, col_l2 = st.columns([1, 4])
with col_l1:
    try: st.image("logo.jpg", width=120)
    except: st.write("") 
with col_l2:
    st.title("Sistema de Gestión")
    st.subheader("Abril Lencería & Blanquería")

tab_pos, tab_catalogo, tab_caja = st.tabs(["💳 Registrar Venta", "📦 Catálogo", "💰 Cierre de Caja"])

# ... (Lógica de tab_pos y tab_catalogo se mantiene igual que antes) ...

with tab_caja:
    st.header("Gestión de Caja")
    opcion = st.radio("Acción:", ["Realizar Cierre Diario", "Ver Reportes"], horizontal=True)
    
    conn = get_db_connection()
    if opcion == "Realizar Cierre Diario":
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        ventas_hoy = pd.read_sql_query(f"SELECT * FROM ventas WHERE fecha LIKE '{fecha_hoy}%'", conn)
        
        if not ventas_hoy.empty:
            st.write(f"### Cierre para hoy: {fecha_hoy}")
            # Calcular totales por método
            efectivo = ventas_hoy[ventas_hoy['metodo_pago'] == 'Efectivo']['total'].sum()
            mp = ventas_hoy[ventas_hoy['metodo_pago'] == 'Mercado Pago']['total'].sum()
            transf = ventas_hoy[ventas_hoy['metodo_pago'] == 'Transferencia']['total'].sum()
            tarjeta = ventas_hoy[ventas_hoy['metodo_pago'] == 'Debito/Credito']['total'].sum()
            total_gral = ventas_hoy['total'].sum()
            
            st.metric("Total General", f"${total_gral:,.2f}")
            
            if st.button("✅ Confirmar Cierre Diario"):
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO cierres_caja VALUES (?,?,?,?,?,?)", 
                                   (fecha_hoy, efectivo, mp, transf, tarjeta, total_gral))
                    conn.commit()
                    st.success("Caja cerrada correctamente")
                except:
                    st.error("Ya existe un cierre para hoy.")
        else:
            st.info("No hay ventas hoy para cerrar.")
            
    else:
        st.subheader("Reportes Históricos")
        df_cierres = pd.read_sql_query("SELECT * FROM cierres_caja", conn)
        if not df_cierres.empty:
            df_cierres['fecha_cierre'] = pd.to_datetime(df_cierres['fecha_cierre'])
            tipo_reporte = st.selectbox("Ver por:", ["Diario", "Mensual", "Anual"])
            
            if tipo_reporte == "Mensual":
                df_cierres = df_cierres.groupby(df_cierres['fecha_cierre'].dt.to_period('M')).sum()
            elif tipo_reporte == "Anual":
                df_cierres = df_cierres.groupby(df_cierres['fecha_cierre'].dt.to_period('Y')).sum()
            
            st.dataframe(df_cierres, use_container_width=True)
            st.line_chart(df_cierres['total_general'])
        else:
            st.warning("Aún no hay cierres registrados.")
    conn.close()
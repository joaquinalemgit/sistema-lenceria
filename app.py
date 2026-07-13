import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from fpdf import FPDF
import plotly.express as px
import os

# Configuración inicial
st.set_page_config(page_title="Gestión Lencería", layout="wide")

# Configuración de logo
col_l1, col_l2 = st.columns([1, 4])
with col_l1:
    if os.path.exists("logo.jpg"):
        st.image("logo.jpg", width=120)
    else:
        st.write("Logo no disponible") 
with col_l2:
    st.title("Sistema de Gestión")
    st.subheader("Abril Lencería & Blanquería")

def get_db_connection():
    conn = sqlite3.connect('lenceria_master_v3.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos 
                      (codigo TEXT PRIMARY KEY, descripcion TEXT, marca TEXT, categoria TEXT, subcategoria TEXT, 
                       precio_costo REAL, precio_venta REAL, stock_actual INTEGER, unidades_paquete INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS ventas 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, metodo_pago TEXT, total REAL, nota TEXT)''')
    # Tabla para medios de pago
    cursor.execute('''CREATE TABLE IF NOT EXISTS medios_pago 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, recargo_descuento REAL)''')
    # Insertar por defecto si está vacía
    cursor.execute("INSERT OR IGNORE INTO medios_pago (nombre, recargo_descuento) VALUES ('Efectivo', 0)")
    conn.commit()
    conn.close()

init_db()

tab_pos, tab_catalogo, tab_pagos, tab_excel, tab_informes, tab_caja = st.tabs(["💳 Registrar Venta", "📦 Catálogo", "💳 Medios de Pago", "📊 Importar Excel", "📈 Informes", "💰 Cierre de Caja"])

with tab_pos:
    st.header("Registrar Venta")
    conn = get_db_connection()
    df_prods = pd.read_sql_query("SELECT * FROM productos", conn)
    df_pagos = pd.read_sql_query("SELECT * FROM medios_pago", conn)
    conn.close()

    if 'carrito' not in st.session_state: st.session_state.carrito = []

    col_fil1, col_fil2, col_fil3 = st.columns(3)
    with col_fil1:
        cat_sel = st.selectbox("Categoría", ["-- Todas --"] + sorted([c for c in df_prods['categoria'].unique() if pd.notna(c)]))
    with col_fil2:
        subcat_sel = st.selectbox("Subcategoría", ["-- Todas --"] + sorted([s for s in df_prods['subcategoria'].unique() if pd.notna(s)]))
    with col_fil3:
        df_f = df_prods
        if cat_sel != "-- Todas --": df_f = df_f[df_f['categoria'] == cat_sel]
        if subcat_sel != "-- Todas --": df_f = df_f[df_f['subcategoria'] == subcat_sel]
        opciones = df_f.apply(lambda r: f"{r['codigo']} - {r['descripcion']} (${r['precio_venta']})", axis=1).tolist()
        prod_sel = st.selectbox("Seleccionar Producto", options=["-- Seleccionar --"] + opciones)

    cant = st.number_input("Cantidad", min_value=1, value=1)
    if st.button("🛒 Agregar al Carrito"):
        if prod_sel != "-- Seleccionar --":
            cod = prod_sel.split(" - ")[0]
            prod = df_prods[df_prods['codigo'] == cod].iloc[0]
            if cant <= prod['stock_actual']:
                st.session_state.carrito.append({"id_item": datetime.now().timestamp(), "codigo": cod, "desc": prod['descripcion'], "precio": prod['precio_venta'], "cant": cant})
                st.rerun()

    st.subheader("Carrito")
    if st.session_state.carrito:
        total_base = sum(item['precio'] * item['cant'] for item in st.session_state.carrito)
        metodo_seleccionado = st.selectbox("Método de Pago", df_pagos['nombre'].tolist())
        ajuste_pago = df_pagos[df_pagos['nombre'] == metodo_seleccionado]['recargo_descuento'].iloc[0]
        
        st.write(f"Aplicando ajuste por {metodo_seleccionado}: {ajuste_pago}%")
        total_final = total_base * (1 + ajuste_pago/100)
        st.markdown(f"### Total Final: **${total_final:,.2f}**")
        
        if st.button("✅ Confirmar Venta"):
            conn = get_db_connection()
            c = conn.cursor()
            for item in st.session_state.carrito:
                c.execute("UPDATE productos SET stock_actual = stock_actual - ? WHERE codigo = ?", (item['cant'], item['codigo']))
            c.execute("INSERT INTO ventas (fecha, total, metodo_pago) VALUES (?, ?, ?)", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), total_final, metodo_seleccionado))
            conn.commit()
            conn.close()
            st.session_state.carrito = []
            st.success("Venta registrada")
            st.rerun()

with tab_catalogo:
    st.header("📦 Catálogo y Edición")
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM productos", conn)
    conn.close()
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    if st.button("💾 Guardar Cambios Catálogo"):
        conn = get_db_connection()
        edited_df.to_sql('productos', conn, if_exists='replace', index=False)
        conn.close()
        st.success("Catálogo guardado")

with tab_pagos:
    st.header("💳 Administración de Medios de Pago")
    conn = get_db_connection()
    
    # Botón para borrar todo
    if st.button("⚠️ Eliminar TODOS los medios de pago"):
        c = conn.cursor()
        c.execute("DELETE FROM medios_pago")
        conn.commit()
        st.warning("Todos los medios de pago han sido eliminados.")
        st.rerun()

    df_pagos = pd.read_sql_query("SELECT * FROM medios_pago", conn)
    
    edited_pagos = st.data_editor(df_pagos, num_rows="dynamic", use_container_width=True)
    if st.button("💾 Guardar Medios de Pago"):
        edited_pagos.to_sql('medios_pago', conn, if_exists='replace', index=False)
        st.success("Medios de pago actualizados")
    conn.close()

with tab_excel:
    st.header("📊 Importar Excel")
    archivo_ex = st.file_uploader("Subir archivo", type=["xlsx", "csv"])
    if archivo_ex:
        df_import = pd.read_excel(archivo_ex) if archivo_ex.name.endswith('.xlsx') else pd.read_csv(archivo_ex)
        cols = df_import.columns.tolist()
        c_cod = st.selectbox("Código", cols)
        c_desc = st.selectbox("Descripción", cols)
        c_marca = st.selectbox("Marca", cols)
        c_cat = st.selectbox("Categoría", cols)
        c_sub = st.selectbox("Sub-Categoría", cols)
        c_costo = st.selectbox("Costo", cols)
        c_margen = st.selectbox("Margen %", cols)
        
        if st.button("🚀 Importar"):
            conn = get_db_connection()
            cursor = conn.cursor()
            for _, row in df_import.iterrows():
                costo = float(row[c_costo])
                venta = costo * (1 + float(row[c_margen])/100)
                cursor.execute("INSERT OR REPLACE INTO productos VALUES (?,?,?,?,?,?,?,?,?)", 
                               (str(row[c_cod]), str(row[c_desc]), str(row[c_marca]), str(row[c_cat]), str(row[c_sub]), costo, venta, 1, 1))
            conn.commit()
            conn.close()
            st.success("Importación finalizada")

with tab_informes:
    st.header("📈 Informes")
    conn = get_db_connection()
    df_v = pd.read_sql_query("SELECT * FROM ventas", conn)
    conn.close()
    if not df_v.empty:
        df_v['fecha'] = pd.to_datetime(df_v['fecha'])
        st.line_chart(df_v.groupby(df_v['fecha'].dt.date)['total'].sum())

with tab_caja:
    st.header("💰 Cierre de Caja")
    conn = get_db_connection()
    df_v = pd.read_sql_query("SELECT * FROM ventas", conn)
    conn.close()
    fecha = st.date_input("Fecha", datetime.now().date())
    st.dataframe(df_v[pd.to_datetime(df_v['fecha']).dt.date == fecha])

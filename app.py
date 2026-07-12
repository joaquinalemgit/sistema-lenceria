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
        st.write("Logo no encontrado") 
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
                       precio_costo REAL, precio_venta REAL, stock_actual INTEGER, unidades_paquete INTEGER DEFAULT 1)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS ventas 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, metodo_pago TEXT, total REAL, nota TEXT)''')
    
    # Parches de seguridad para columnas nuevas
    cols = ['subcategoria', 'unidades_paquete', 'nota']
    for col in cols:
        try:
            if col == 'nota': cursor.execute(f"ALTER TABLE ventas ADD COLUMN {col} TEXT")
            elif col == 'subcategoria': cursor.execute(f"ALTER TABLE productos ADD COLUMN {col} TEXT")
            elif col == 'unidades_paquete': cursor.execute(f"ALTER TABLE productos ADD COLUMN {col} INTEGER DEFAULT 1")
        except: pass
        
    conn.commit()
    conn.close()

init_db()

tab_pos, tab_catalogo, tab_excel, tab_informes, tab_caja = st.tabs(["💳 Registrar Venta", "📦 Catálogo", "📊 Importar Excel", "📈 Informes", "💰 Cierre de Caja"])

with tab_pos:
    st.header("Registrar Venta")
    conn = get_db_connection()
    df_prods = pd.read_sql_query("SELECT * FROM productos", conn)
    conn.close()

    if 'carrito' not in st.session_state: st.session_state.carrito = []

    col1, col2 = st.columns([1, 1])
    with col1:
        marca_sel = st.selectbox("1. Filtrar por Marca", options=["-- Todas --"] + sorted([m for m in df_prods['marca'].unique() if pd.notna(m)]))
        df_filtrado = df_prods[df_prods['marca'] == marca_sel] if marca_sel != "-- Todas --" else df_prods
        opciones = df_filtrado.apply(lambda r: f"{r['codigo']} - {r['descripcion']} (Stock: {r['stock_actual']})", axis=1).tolist()
        prod_sel = st.selectbox("2. Seleccionar Producto", options=["-- Seleccionar --"] + opciones)
        cant = st.number_input("Cantidad", min_value=1, value=1)
        
        if st.button("🛒 Agregar al Carrito"):
            if prod_sel != "-- Seleccionar --":
                cod = prod_sel.split(" - ")[0]
                prod = df_prods[df_prods['codigo'] == cod].iloc[0]
                if cant <= prod['stock_actual']:
                    st.session_state.carrito.append({"id_item": datetime.now().timestamp(), "codigo": cod, "desc": prod['descripcion'], "precio": prod['precio_venta'], "cant": cant})
                    st.rerun()
                else: st.error("Stock insuficiente")

    with col2:
        st.subheader("Carrito de Venta")
        total_base = 0
        if st.session_state.carrito:
            for i, item in enumerate(st.session_state.carrito):
                cols = st.columns([3, 1, 1])
                cols[0].write(f"{item['desc']} (x{item['cant']})")
                cols[1].write(f"${item['precio']*item['cant']:.2f}")
                if cols[2].button("❌", key=f"del_{item['id_item']}"):
                    st.session_state.carrito.pop(i)
                    st.rerun()
                total_base += item['precio'] * item['cant']
            
            st.divider()
            desc = st.number_input("Descuento (%)", min_value=0, max_value=100, value=0)
            nota = st.text_input("📝 Nota para el ticket")
            total_final = total_base * (1 - desc/100)
            st.markdown(f"### Total: **${total_final:,.2f}**")
            metodo = st.radio("Método de Pago", ("Efectivo", "Mercado Pago", "Transferencia", "Debito/Credito"), horizontal=True)
            
            if st.button("✅ Confirmar Venta"):
                pdf = FPDF()
                pdf.add_page()
                if os.path.exists("logo.jpg"): pdf.image("logo.jpg", 80, 10, 50)
                pdf.ln(40)
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(200, 10, "Ticket de Venta", ln=True, align='C')
                pdf.set_font("Arial", size=12)
                for item in st.session_state.carrito:
                    pdf.cell(200, 8, f"{item['desc']} x{item['cant']} : ${item['precio']*item['cant']:.2f}", ln=True)
                pdf.cell(200, 10, f"Total Final: ${total_final:.2f}", ln=True)
                if nota:
                    pdf.set_font("Arial", 'I', 10)
                    pdf.cell(200, 10, f"Nota: {nota}", ln=True)
                pdf.output("ticket.pdf")
                
                conn = get_db_connection()
                c = conn.cursor()
                for item in st.session_state.carrito:
                    c.execute("UPDATE productos SET stock_actual = stock_actual - ? WHERE codigo = ?", (item['cant'], item['codigo']))
                c.execute("INSERT INTO ventas (fecha, metodo_pago, total, nota) VALUES (?, ?, ?, ?)", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), metodo, total_final, nota))
                conn.commit()
                conn.close()
                st.session_state.carrito = []
                st.success("Venta registrada")
                with open("ticket.pdf", "rb") as f: st.download_button("📥 Descargar Ticket", f, "ticket.pdf")
                st.rerun()

with tab_catalogo:
    st.header("📦 Catálogo")
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM productos", conn)
    conn.close()
    busqueda = st.text_input("🔍 Buscar...")
    if busqueda: df = df[df.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)]
    st.dataframe(df, use_container_width=True)

with tab_excel:
    st.header("📊 Importar Excel")
    archivo_ex = st.file_uploader("Subir", type=["xlsx", "csv"])
    if archivo_ex:
        df_import = pd.read_excel(archivo_ex) if archivo_ex.name.endswith('.xlsx') else pd.read_csv(archivo_ex)
        cols = df_import.columns.tolist()
        c_marca = st.selectbox("Marca", cols)
        c_cod = st.selectbox("Código", cols)
        c_cat = st.selectbox("Categoría", cols)
        c_sub = st.selectbox("Sub-Categoría", cols)
        c_desc = st.selectbox("Descripción", cols)
        c_costo = st.selectbox("Costo Bulto", cols)
        c_unidades = st.selectbox("Unidades por Paquete", cols)
        c_margen = st.selectbox("Margen %", cols)
        
        if st.button("🚀 Importar"):
            conn = get_db_connection()
            for _, row in df_import.iterrows():
                u = float(row[c_unidades])
                costo_u = float(row[c_costo]) / u
                venta = costo_u * (1 + float(row[c_margen])/100)
                conn.execute("INSERT OR REPLACE INTO productos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                             (str(row[c_cod]), str(row[c_desc]), str(row[c_marca]), str(row[c_cat]), str(row[c_sub]), costo_u, venta, 0, u))
            conn.commit()
            conn.close()
            st.success("¡Importado!")

with tab_informes:
    st.header("📈 Informes")
    conn = get_db_connection()
    df_v = pd.read_sql_query("SELECT * FROM ventas", conn)
    df_p = pd.read_sql_query("SELECT * FROM productos", conn)
    conn.close()
    col1, col2 = st.columns(2)
    with col1:
        if not df_v.empty:
            df_v['fecha'] = pd.to_datetime(df_v['fecha'])
            resumen = df_v.groupby(df_v['fecha'].dt.date)['total'].sum().reset_index()
            st.plotly_chart(px.line(resumen, x='fecha', y='total', title="Ventas diarias"), use_container_width=True)
    with col2:
        if not df_p.empty:
            df_p['valor_inv'] = df_p['precio_costo'] * df_p['stock_actual']
            st.plotly_chart(px.pie(df_p, values='valor_inv', names='marca', title="Inversión por Marca"), use_container_width=True)

with tab_caja:
    st.header("💰 Cierre de Caja")
    conn = get_db_connection()
    df_v = pd.read_sql_query("SELECT * FROM ventas", conn)
    conn.close()
    fecha = st.date_input("Fecha", datetime.now().date())
    ventas_dia = df_v[pd.to_datetime(df_v['fecha']).dt.date == fecha]
    st.metric("Total del día", f"${ventas_dia['total'].sum():,.2f}")
    st.dataframe(ventas_dia)

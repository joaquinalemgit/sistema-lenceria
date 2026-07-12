import streamlit as st
import pandas as pd
import sqlite3
import google.generativeai as genai
import json
from pypdf import PdfReader
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
    conn.commit()
    conn.close()

init_db()

# Logo y Título
col_l1, col_l2 = st.columns([1, 4])
with col_l1:
    try:
        st.image("logo.jpg", width=120)
    except:
        st.write("") 
with col_l2:
    st.title("Sistema de Gestión")
    st.subheader("Abril Lencería & Blanquería")

tab_pos, tab_catalogo, tab_ia, tab_excel, tab_caja = st.tabs([
    "💳 Registrar Venta", 
    "📦 Catálogo", 
    "🤖 Carga PDF", 
    "📊 Importar Excel", 
    "💰 Cierre de Caja"
])

with tab_pos:
    st.header("Registrar Venta")
    conn = get_db_connection()
    df_prods = pd.read_sql_query("SELECT * FROM productos", conn)
    conn.close()

    if 'carrito' not in st.session_state:
        st.session_state.carrito = []

    col1, col2 = st.columns([1, 1])
    with col1:
        opciones_prod = df_prods.apply(lambda row: f"{row['codigo']} - {row['descripcion']} (${row['precio_venta']})", axis=1).tolist()
        prod_seleccionado = st.selectbox("Buscar Producto", options=["-- Seleccionar --"] + opciones_prod)
        cantidad = st.number_input("Cantidad", min_value=1, value=1)
        
        if st.button("🛒 Agregar al Ticket"):
            if prod_seleccionado != "-- Seleccionar --":
                codigo_sel = prod_seleccionado.split(" - ")[0]
                prod_data = df_prods[df_prods['codigo'] == codigo_sel].iloc[0]
                st.session_state.carrito.append({
                    "id": datetime.now().timestamp(),
                    "codigo": prod_data['codigo'],
                    "descripcion": prod_data['descripcion'],
                    "precio": prod_data['precio_venta'],
                    "cantidad": cantidad,
                    "subtotal": prod_data['precio_venta'] * cantidad
                })
                st.rerun()

    with col2:
        st.subheader("Ticket Actual")
        if st.session_state.carrito:
            for i, item in enumerate(st.session_state.carrito):
                cols = st.columns([3, 1, 1])
                cols[0].write(f"{item['descripcion']} (x{item['cantidad']})")
                cols[1].write(f"${item['subtotal']:.2f}")
                if cols[2].button("❌", key=f"del_{item['id']}"):
                    st.session_state.carrito.pop(i)
                    st.rerun()

            total = sum(item['subtotal'] for item in st.session_state.carrito)
            st.markdown(f"### Total: **${total:,.2f}**")
            
            metodo_pago = st.radio("Método de Pago", ("Efectivo", "Mercado Pago", "Transferencia", "Debito/Credito"), horizontal=True)
            
            if st.button("✅ Confirmar Venta"):
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO ventas (fecha, metodo_pago, total) VALUES (?, ?, ?)", 
                               (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), metodo_pago, total))
                
                remito = f"--- REMITO DE VENTA ---\nFecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
                for item in st.session_state.carrito:
                    cursor.execute("UPDATE productos SET stock_actual = stock_actual - ? WHERE codigo = ?", 
                                  (item['cantidad'], item['codigo']))
                    remito += f"- {item['descripcion']} (x{item['cantidad']}): ${item['subtotal']:.2f}\n"
                
                remito += f"\nTOTAL: ${total:,.2f}\nMétodo: {metodo_pago}\n------------------------"
                conn.commit()
                conn.close()
                
                st.success("Venta registrada con éxito")
                st.text_area("Copiar Remito:", value=remito, height=200)
                if st.button("Limpiar para nueva venta"):
                    st.session_state.carrito = []
                    st.rerun()
        else:
            st.info("El ticket está vacío.")

with tab_catalogo:
    st.header("Buscador de Productos")
    conn = get_db_connection()
    df_catalogo = pd.read_sql_query("SELECT * FROM productos", conn)
    conn.close()
    
    if not df_catalogo.empty:
        df_catalogo['precio_costo'] = pd.to_numeric(df_catalogo['precio_costo'], errors='coerce').fillna(0)
        df_catalogo['precio_venta'] = pd.to_numeric(df_catalogo['precio_venta'], errors='coerce').fillna(0)
        df_catalogo['stock_actual'] = pd.to_numeric(df_catalogo['stock_actual'], errors='coerce').fillna(0).astype(int)
        
        busqueda = st.text_input("🔍 Escribe para buscar...")
        if busqueda:
            df_catalogo = df_catalogo[df_catalogo['descripcion'].str.contains(busqueda, case=False, na=False) | df_catalogo['codigo'].str.contains(busqueda, case=False, na=False)]
        
        st.dataframe(df_catalogo, use_container_width=True, hide_index=True)

with tab_ia:
    st.header("Carga con IA")
    api_key_input = st.text_input("API Key Google Gemini:", type="password")
    archivo_pdf = st.file_uploader("Sube PDF", type="pdf")
    
    if st.button("🚀 Procesar PDF"):
        if archivo_pdf and api_key_input:
            reader = PdfReader(archivo_pdf)
            texto = "".join([page.extract_text() for page in reader.pages[:2]])
            genai.configure(api_key=api_key_input)
            model = genai.GenerativeModel('gemini-1.5-flash')
            resp = model.generate_content(f"Extrae productos de este texto: {texto}")
            st.write(resp.text)
        else:
            st.warning("Completa los campos")

with tab_excel:
    st.header("Importar Excel")
    archivo_excel = st.file_uploader("Sube archivo", type=["xlsx", "csv"])
    if archivo_excel:
        df = pd.read_excel(archivo_excel) if archivo_excel.name.endswith('xlsx') else pd.read_csv(archivo_excel)
        st.dataframe(df.head())
        if st.button("Guardar"):
            conn = get_db_connection()
            df.to_sql('productos', conn, if_exists='append', index=False)
            conn.close()
            st.success("Guardado")

with tab_caja:
    st.header("Cierre de Caja")
    conn = get_db_connection()
    df_ventas = pd.read_sql_query("SELECT * FROM ventas", conn)
    conn.close()
    st.dataframe(df_ventas)

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from fpdf import FPDF

# Configuración inicial
st.set_page_config(page_title="Gestión Lencería", layout="wide")

# Configuración de logo
col_l1, col_l2 = st.columns([1, 4])
with col_l1:
    try:
        st.image("logo.jpg", width=120)
    except:
        st.write("Logo no encontrado") 
with col_l2:
    st.title("Sistema de Gestión")
    st.subheader("Abril Lencería & Blanquería")

def get_db_connection():
    conn = sqlite3.connect('lenceria_master.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos (codigo TEXT PRIMARY KEY, descripcion TEXT, proveedor TEXT, precio_costo REAL, precio_venta REAL, stock_actual INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, metodo_pago TEXT, total REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS cierres_caja (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_cierre TEXT, total_ventas REAL)''')
    conn.commit()
    conn.close()

init_db()

tab_pos, tab_catalogo, tab_excel, tab_caja = st.tabs(["💳 Registrar Venta", "📦 Catálogo", "📊 Importar Excel", "💰 Cierre de Caja"])

with tab_pos:
    st.header("Registrar Venta")
    conn = get_db_connection()
    df_prods = pd.read_sql_query("SELECT * FROM productos", conn)
    conn.close()

    if 'carrito' not in st.session_state: st.session_state.carrito = []

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Agregar Producto")
        busq = st.text_input("Buscar producto por código o nombre...")
        df_filtrado = df_prods
        if busq:
            df_filtrado = df_prods[df_prods['descripcion'].str.contains(busq, case=False, na=False) | df_prods['codigo'].str.contains(busq, case=False, na=False)]
        
        opciones = df_filtrado.apply(lambda r: f"{r['codigo']} - {r['descripcion']} (Stock: {r['stock_actual']})", axis=1).tolist()
        prod_sel = st.selectbox("Seleccionar", options=["-- Seleccionar --"] + opciones)
        cant = st.number_input("Cantidad", min_value=1, value=1)
        
        if st.button("🛒 Agregar al Carrito"):
            if prod_sel != "-- Seleccionar --":
                cod = prod_sel.split(" - ")[0]
                prod = df_prods[df_prods['codigo'] == cod].iloc[0]
                if cant <= prod['stock_actual']:
                    st.session_state.carrito.append({"id_item": datetime.now().timestamp(), "codigo": cod, "desc": prod['descripcion'], "precio": prod['precio_venta'], "cant": cant})
                    st.rerun()
                else:
                    st.error("Stock insuficiente")

    with col2:
        st.subheader("Carrito de Venta")
        total_base = 0
        
        if st.session_state.carrito:
            for i, item in enumerate(st.session_state.carrito):
                cols = st.columns([3, 1, 1])
                cols[0].write(f"{item['desc']} (x{item['cant']})")
                cols[1].write(f"${item['precio']*item['cant']:.2f}")
                # Botón para eliminar el ítem específico
                if cols[2].button("❌", key=f"del_{item['id_item']}"):
                    st.session_state.carrito.pop(i)
                    st.rerun()
                total_base += item['precio'] * item['cant']
            
            st.divider()
            desc = st.number_input("Descuento (%)", min_value=0, max_value=100, value=0)
            total_final = total_base * (1 - desc/100)
            st.markdown(f"### Total: **${total_final:,.2f}**")
            
            # Selector de método de pago restaurado
            metodo_pago = st.radio("Método de Pago", ("Efectivo", "Mercado Pago", "Transferencia", "Debito/Credito"), horizontal=True)
            
            if st.button("✅ Confirmar y Descargar Ticket"):
                # Generación del PDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(200, 10, txt="Ticket de Venta - Abril Lenceria", ln=True, align='C')
                pdf.set_font("Arial", size=12)
                for item in st.session_state.carrito:
                    pdf.cell(200, 10, txt=f"{item['desc']} x{item['cant']} : ${item['precio']*item['cant']:.2f}", ln=True)
                pdf.cell(200, 10, txt=f"Descuento aplicado: {desc}%", ln=True)
                pdf.cell(200, 10, txt=f"Metodo de pago: {metodo_pago}", ln=True)
                pdf.cell(200, 10, txt=f"Total: ${total_final:.2f}", ln=True)
                pdf.output("ticket.pdf")
                
                # Inserción en base de datos
                conn = get_db_connection()
                c = conn.cursor()
                for item in st.session_state.carrito:
                    c.execute("UPDATE productos SET stock_actual = stock_actual - ? WHERE codigo = ?", (item['cant'], item['codigo']))
                # Registro con método de pago
                c.execute("INSERT INTO ventas (fecha, metodo_pago, total) VALUES (?, ?, ?)", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), metodo_pago, total_final))
                conn.commit()
                conn.close()
                st.session_state.carrito = []
                st.success("Venta confirmada y registrada en el sistema.")
                with open("ticket.pdf", "rb") as f:
                    st.download_button("📥 Descargar Ticket PDF", f, "ticket.pdf")
        else:
            st.info("El carrito está vacío. Agrega productos para comenzar.")

with tab_catalogo:
    st.header("Catálogo")
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM productos", conn)
    conn.close()
    busqueda = st.text_input("🔍 Buscar en catálogo...")
    if busqueda:
        df = df[df['descripcion'].str.contains(busqueda, case=False, na=False) | df['proveedor'].str.contains(busqueda, case=False, na=False)]
    st.dataframe(df, use_container_width=True)

with tab_excel:
    st.header("📊 Importar Excel")
    archivo_ex = st.file_uploader("Subir archivo", type=["xlsx", "xls"])
    if archivo_ex:
        df_import = pd.read_excel(archivo_ex)
        st.dataframe(df_import.head())
        col_c, col_d, col_p = st.columns(3)
        c_cod = col_c.selectbox("Columna Código", df_import.columns)
        c_desc = col_d.selectbox("Columna Descripción", df_import.columns)
        c_cost = col_p.selectbox("Columna Costo", df_import.columns)
        nombre_prov = st.text_input("Nombre Proveedor")
        margen = st.number_input("Margen (%)", value=70)
        if st.button("🚀 Guardar Importación"):
            conn = get_db_connection()
            c = conn.cursor()
            count = 0
            for _, row in df_import.iterrows():
                venta = float(row[c_cost]) * (1 + margen/100)
                c.execute("INSERT OR REPLACE INTO productos VALUES (?, ?, ?, ?, ?, ?)", (str(row[c_cod]), str(row[c_desc]), nombre_prov, float(row[c_cost]), venta, 0))
                count += 1
            conn.commit()
            conn.close()
            st.success(f"Procesados {count} productos.")
            st.rerun()

with tab_caja:
    st.header("💰 Cierre de Caja")
    conn = get_db_connection()
    df_v = pd.read_sql_query("SELECT * FROM ventas", conn)
    conn.close()
    st.write(df_v)

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
        
        # 1. Selector de Proveedor
        lista_proveedores = [p for p in df_prods['proveedor'].unique() if pd.notna(p) and p != ""]
        lista_proveedores.sort()
        prov_sel = st.selectbox("1. Filtrar por Proveedor", options=["-- Todos --"] + lista_proveedores)
        
        # Filtrar DataFrame según el proveedor elegido
        if prov_sel != "-- Todos --":
            df_filtrado = df_prods[df_prods['proveedor'] == prov_sel]
        else:
            df_filtrado = df_prods
            
        # 2. Selector de Producto (filtrado)
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
                if cols[2].button("❌", key=f"del_{item['id_item']}"):
                    st.session_state.carrito.pop(i)
                    st.rerun()
                total_base += item['precio'] * item['cant']
            
            st.divider()
            desc = st.number_input("Descuento (%)", min_value=0, max_value=100, value=0)
            total_final = total_base * (1 - desc/100)
            st.markdown(f"### Total: **${total_final:,.2f}**")
            
            # NUEVO: Opciones de métodos de pago actualizadas
            metodo_pago = st.radio("Método de Pago", ("Efectivo", "Mercado Pago", "Transferencia Santander", "Transferencia BERSA", "Debito", "Credito"), horizontal=True)
            
            # Lógica de la calculadora de vuelto para Efectivo
            if metodo_pago == "Efectivo":
                col_paga, col_vuelto = st.columns(2)
                with col_paga:
                    monto_abonado = st.number_input("Paga con ($):", min_value=0.0, value=float(total_final), step=100.0)
                with col_vuelto:
                    if monto_abonado >= total_final:
                        vuelto = monto_abonado - total_final
                        st.success(f"💵 Vuelto: **${vuelto:,.2f}**")
                    else:
                        st.error("Monto insuficiente")
            
            if st.button("✅ Confirmar y Descargar Ticket"):
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
                
                conn = get_db_connection()
                c = conn.cursor()
                for item in st.session_state.carrito:
                    c.execute("UPDATE productos SET stock_actual = stock_actual - ? WHERE codigo = ?", (item['cant'], item['codigo']))
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
    st.header("📦 Catálogo de Productos")
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM productos", conn)
    conn.close()

    col_cat1, col_cat2 = st.columns([2, 1])

    with col_cat1:
        st.subheader("Visualización y Búsqueda")
        busqueda = st.text_input("🔍 Buscar por descripción, código o proveedor...", key="search_cat")
        df_mostrar = df
        if busqueda:
            df_mostrar = df[df['descripcion'].str.contains(busqueda, case=False, na=False) | 
                            df['codigo'].str.contains(busqueda, case=False, na=False) | 
                            df['proveedor'].str.contains(busqueda, case=False, na=False)]
        st.dataframe(df_mostrar, use_container_width=True)

    with col_cat2:
        st.subheader("🔄 Actualizar Stock")
        if not df.empty:
            lista_productos = df.apply(lambda r: f"{r['codigo']} - {r['descripcion']} (Actual: {r['stock_actual']})", axis=1).tolist()
            prod_a_actualizar = st.selectbox("Selecciona un producto", options=["-- Seleccionar --"] + lista_productos)
            
            if prod_a_actualizar != "-- Seleccionar --":
                cod_prod = prod_a_actualizar.split(" - ")[0]
                stock_previo = int(df[df['codigo'] == cod_prod]['stock_actual'].values[0])
                
                nuevo_stock = st.number_input("Nuevo Stock Disponible", min_value=0, value=stock_previo, step=1)
                
                if st.button("💾 Guardar Nuevo Stock"):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE productos SET stock_actual = ? WHERE codigo = ?", (nuevo_stock, cod_prod))
                    conn.commit()
                    conn.close()
                    st.success(f"¡Hecho! El stock del código {cod_prod} ahora es {nuevo_stock}.")
                    st.rerun()
        else:
            st.info("No hay productos registrados en el catálogo.")

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
                try:
                    venta = float(row[c_cost]) * (1 + margen/100)
                    c.execute("INSERT OR REPLACE INTO productos VALUES (?, ?, ?, ?, ?, ?)", (str(row[c_cod]), str(row[c_desc]), nombre_prov, float(row[c_cost]), venta, 0))
                    count += 1
                except:
                    continue
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

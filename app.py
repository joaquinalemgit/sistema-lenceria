import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# Configuración inicial
st.set_page_config(page_title="Gestión Lencería", layout="wide")

# Configuración de logo
col_l1, col_l2 = st.columns([1, 4])
with col_l1:
    try:
        st.image("logo.jpg", width=120)
    except:
        st.write("") 
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

tab_pos, tab_catalogo, tab_ia, tab_excel, tab_caja = st.tabs(["💳 Registrar Venta", "📦 Catálogo", "🤖 Carga PDF", "📊 Importar Excel", "💰 Cierre de Caja"])

with tab_pos:
    st.header("Registrar Venta")
    conn = get_db_connection()
    df_prods = pd.read_sql_query("SELECT * FROM productos", conn)
    conn.close()

    if 'carrito' not in st.session_state: st.session_state.carrito = []

    col1, col2 = st.columns([1, 1])
    with col1:
        opciones_prod = df_prods.apply(lambda row: f"{row['codigo']} - {row['descripcion']} (${row['precio_venta']})", axis=1).tolist()
        prod_seleccionado = st.selectbox("Buscar Producto", options=["-- Seleccionar --"] + opciones_prod)
        cantidad = st.number_input("Cantidad", min_value=1, value=1)
        if st.button("🛒 Agregar al Ticket"):
            if prod_seleccionado != "-- Seleccionar --":
                codigo_sel = prod_seleccionado.split(" - ")[0]
                prod_data = df_prods[df_prods['codigo'] == codigo_sel].iloc[0]
                st.session_state.carrito.append({"id": datetime.now().timestamp(), "codigo": prod_data['codigo'], "descripcion": prod_data['descripcion'], "precio": prod_data['precio_venta'], "cantidad": cantidad, "subtotal": prod_data['precio_venta'] * cantidad})
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
                cursor.execute("INSERT INTO ventas (fecha, metodo_pago, total) VALUES (?, ?, ?)", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), metodo_pago, total))
                for item in st.session_state.carrito:
                    cursor.execute("UPDATE productos SET stock_actual = stock_actual - ? WHERE codigo = ?", (item['cantidad'], item['codigo']))
                conn.commit()
                conn.close()
                st.success("Venta registrada")
                st.session_state.carrito = []
                st.rerun()

with tab_catalogo:
    st.header("Catálogo")
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM productos", conn)
    conn.close()
    
    busqueda = st.text_input("🔍 Buscar por descripción, código o proveedor...")
    if busqueda:
        df = df[df['descripcion'].str.contains(busqueda, case=False, na=False) | 
                df['codigo'].str.contains(busqueda, case=False, na=False) | 
                df['proveedor'].str.contains(busqueda, case=False, na=False)]
    
    st.dataframe(df, use_container_width=True)

with tab_ia:
    st.header("Carga PDF con IA")
    archivo = st.file_uploader("Sube PDF del proveedor", type="pdf")
    if archivo: st.write("Procesando...")

with tab_excel:
    st.header("📊 Importar Excel con Preview y Proveedor")
    archivo_ex = st.file_uploader("Subir archivo Excel", type=["xlsx", "xls"])
    
    if archivo_ex:
        df_import = pd.read_excel(archivo_ex)
        st.write("Vista previa de los datos:")
        st.dataframe(df_import.head(5), use_container_width=True)
        
        st.subheader("Configuración de Mapeo")
        col_a, col_b, col_c = st.columns(3)
        col_codigo = col_a.selectbox("Columna de CÓDIGO", options=df_import.columns)
        col_desc = col_b.selectbox("Columna de DESCRIPCIÓN", options=df_import.columns)
        col_costo = col_c.selectbox("Columna de COSTO", options=df_import.columns)
        
        nombre_prov = st.text_input("Nombre del Proveedor", placeholder="Ej: Floyd, Silvana...")
        margen = st.number_input("Margen de Ganancia (%)", min_value=0, value=70)
        
        if st.button("🚀 Guardar Importación"):
            conn = get_db_connection()
            cursor = conn.cursor()
            count = 0
            for _, row in df_import.iterrows():
                try:
                    cod = str(row[col_codigo])
                    desc = str(row[col_desc])
                    costo = float(row[col_costo])
                    venta = costo * (1 + (margen / 100))
                    
                    cursor.execute('''INSERT OR REPLACE INTO productos 
                                     (codigo, descripcion, proveedor, precio_costo, precio_venta, stock_actual) 
                                     VALUES (?, ?, ?, ?, ?, ?)''', 
                                  (cod, desc, nombre_prov, costo, venta, 0))
                    count += 1
                except Exception as e:
                    continue
            conn.commit()
            conn.close()
            st.success(f"¡Éxito! Se procesaron {count} productos para el proveedor: {nombre_prov}")
            st.rerun()

with tab_caja:
    st.header("💰 Cierre de Caja y Reportes")
    conn = get_db_connection()
    df_ventas = pd.read_sql_query("SELECT * FROM ventas", conn)
    conn.close()
    df_ventas['fecha'] = pd.to_datetime(df_ventas['fecha'])
    
    tipo_reporte = st.selectbox("Ver reporte por:", ["Diario", "Mensual", "Anual"])
    if tipo_reporte == "Diario":
        st.write(df_ventas.groupby(df_ventas['fecha'].dt.date)['total'].sum())
    elif tipo_reporte == "Mensual":
        st.write(df_ventas.groupby(df_ventas['fecha'].dt.to_period('M'))['total'].sum())
    else:
        st.write(df_ventas.groupby(df_ventas['fecha'].dt.to_period('Y'))['total'].sum())

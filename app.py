import streamlit as st
import pandas as pd
import sqlite3
import google.generativeai as genai
import json
from pypdf import PdfReader
from datetime import datetime

# ... (después de todos los import)

# --- CONFIGURACIÓN DE LOGO ---
try:
    st.sidebar.image("logo.jpg", use_container_width=True)
except Exception as e:
    st.sidebar.title("Abril Lencería")
    st.sidebar.write("Comodidad y sensualidad a tu medida")

# ... (sigue con tu código original)

# Configuración inicial de la página
st.set_page_config(page_title="Gestión Lencería", layout="wide")

# Conexión a la base de datos
def get_db_connection():
    conn = sqlite3.connect('lenceria_master.db')
    conn.row_factory = sqlite3.Row
    return conn

# Crear tablas si no existen
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS productos (
        codigo TEXT PRIMARY KEY,
        descripcion TEXT,
        proveedor TEXT,
        precio_costo REAL,
        precio_venta REAL,
        stock_actual INTEGER
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ventas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        metodo_pago TEXT,
        total REAL
    )
    ''')
    conn.commit()
    conn.close()

init_db()

def motor_extraccion_ia(texto_pdf, api_key):
    try:
        genai.configure(api_key=api_key)
        modelo = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Eres un asistente de base de datos para una lencería. Analiza el siguiente texto de un PDF de proveedor.
        Devuelve estrictamente un arreglo JSON con las claves:
        - "codigo"
        - "descripcion"
        - "precio_costo" (numérico. Si el precio es por docena o pack, divídelo para dar el costo unitario)
        - "proveedor" (trata de deducirlo del texto)
        Solo devuelve el JSON puro, sin formatos adicionales.
        Texto: {texto_pdf[:4000]}
        """
        respuesta = modelo.generate_content(prompt)
        texto_limpio = respuesta.text.replace('```json', '').replace('```', '').strip()
        return json.loads(texto_limpio)
    except Exception as e:
        st.error(f"Error procesando con IA: {e}")
        return []

# --- LOGO Y TÍTULO INTEGRADOS ---
col1, col2 = st.columns([1, 4])
with col1:
    try:
        st.image("logo.jpg", width=120)
    except:
        st.write("") # Por si falta la imagen
with col2:
    st.title("Sistema de Gestión")
    st.subheader("Abril Lencería & Blanquería")
# --------------------------------

# Creamos las pestañas de navegación
tab_pos, tab_catalogo, tab_ia, tab_excel, tab_caja = st.tabs([
    "💳 Punto de Venta", 
    "📦 Catálogo & Buscador", 
    "🤖 Carga PDF (IA)", 
    "📊 Importar Excel/CSV", 
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
        # Buscador de productos
        opciones_prod = df_prods.apply(lambda row: f"{row['codigo']} - {row['descripcion']} (${row['precio_venta']})", axis=1).tolist()
        prod_seleccionado = st.selectbox("Buscar Producto", options=["-- Seleccionar --"] + opciones_prod)
        cantidad = st.number_input("Cantidad", min_value=1, value=1)
        
        if st.button("🛒 Agregar al Ticket"):
            if prod_seleccionado != "-- Seleccionar --":
                codigo_sel = prod_seleccionado.split(" - ")[0]
                prod_data = df_prods[df_prods['codigo'] == codigo_sel].iloc[0]
                # Agregamos con un ID único basado en el timestamp para evitar problemas al borrar
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
            # Iterar y mostrar filas con botón borrar
            for i, item in enumerate(st.session_state.carrito):
                cols = st.columns([3, 1, 1])
                cols[0].write(f"{item['descripcion']} (x{item['cantidad']})")
                cols[1].write(f"${item['subtotal']:.2f}")
                
                # Botón de eliminar fila específica
                if cols[2].button("❌", key=f"del_{item['id']}"):
                    st.session_state.carrito.pop(i)
                    st.rerun()

            # Totales
            total = sum(item['subtotal'] for item in st.session_state.carrito)
            st.markdown(f"### Total: **${total:,.2f}**")
            
            c1, c2 = st.columns(2)
            if c1.button("✅ Confirmar Venta"):
                st.success("Venta registrada exitosamente")
                st.session_state.carrito = []
                st.rerun()
            if c2.button("🗑️ Limpiar Venta"):
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
        # --- NUEVA LÓGICA DE LIMPIEZA ---
        # Aseguramos que los precios sean números y los textos sean cadenas
        df_catalogo['precio_costo'] = pd.to_numeric(df_catalogo['precio_costo'], errors='coerce').fillna(0)
        df_catalogo['precio_venta'] = pd.to_numeric(df_catalogo['precio_venta'], errors='coerce').fillna(0)
        df_catalogo['stock_actual'] = pd.to_numeric(df_catalogo['stock_actual'], errors='coerce').fillna(0).astype(int)
        # --------------------------------
        
        busqueda = st.text_input("🔍 Escribe para buscar por código o descripción...")
        if busqueda:
            df_catalogo = df_catalogo[
                df_catalogo['descripcion'].str.contains(busqueda, case=False, na=False) | 
                df_catalogo['codigo'].str.contains(busqueda, case=False, na=False)
            ]
        
        st.dataframe(df_catalogo, use_container_width=True, hide_index=True)

with tab_ia:
    st.header("Actualizar Precios con IA (PDFs Complejos)")
    st.write("Ideal para PDFs como Alcoyana, Coteminas, Alteza.")
    api_key_input = st.text_input("Tu Google Gemini API Key:", type="password")
    archivo_pdf = st.file_uploader("Sube el PDF del proveedor", type="pdf")
    
    if st.button("🚀 Extraer e Importar PDF", type="primary"):
        if archivo_pdf and api_key_input:
            with st.spinner('Procesando con IA...'):
                reader = PdfReader(archivo_pdf)
                texto = "".join([page.extract_text() + "\n" for page in reader.pages[:2]])
                datos_json = motor_extraccion_ia(texto, api_key_input)
                
                if datos_json:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    for prod in datos_json:
                        precio_venta = prod['precio_costo'] * 1.70 # Margen 70%
                        cursor.execute('''
                        INSERT OR REPLACE INTO productos (codigo, descripcion, proveedor, precio_costo, precio_venta, stock_actual)
                        VALUES (?, ?, ?, ?, ?, COALESCE((SELECT stock_actual FROM productos WHERE codigo = ?), 10))
                        ''', (prod['codigo'], prod['descripcion'], prod['proveedor'], prod['precio_costo'], precio_venta, prod['codigo']))
                    conn.commit()
                    conn.close()
                    st.success(f"¡Éxito! Se importaron {len(datos_json)} productos.")
                else:
                    st.error("Error al estructurar los datos.")
        else:
            st.error("Falta la API Key o el archivo PDF.")

with tab_excel:
    st.header("Importación Masiva desde Excel / CSV")
    st.write("Ideal para listas estructuradas como las de Floyd.")
    
    archivo_excel = st.file_uploader("Sube tu archivo (.csv o .xlsx)", type=["csv", "xlsx"])
    
    if archivo_excel:
        try:
            if archivo_excel.name.endswith('.csv'):
                df_import = pd.read_csv(archivo_excel, on_bad_lines='skip', engine='python')
            else:
                df_import = pd.read_excel(archivo_excel)
                
            st.write("### Vista previa del archivo:")
            st.dataframe(df_import.head(10))
            
            st.write("### Mapeo de Columnas")
            st.info("Selecciona qué columna del Excel corresponde a cada dato del sistema.")
            
            columnas_disp = ["-- Omitir --"] + list(df_import.columns)
            
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                col_codigo = st.selectbox("Columna de CÓDIGO", options=columnas_disp)
            with col_b:
                col_desc = st.selectbox("Columna de DESCRIPCIÓN", options=columnas_disp)
            with col_c:
                col_costo = st.selectbox("Columna de COSTO (Precio)", options=columnas_disp)
                
            nombre_proveedor = st.text_input("Nombre del Proveedor (Ej: Floyd):", value="Floyd")
            margen = st.number_input("Margen de Ganancia (%)", min_value=1, value=70)
            
            if st.button("💾 Iniciar Importación Masiva", type="primary"):
                if col_desc == "-- Omitir --" or col_costo == "-- Omitir --":
                    st.error("⚠️ Es obligatorio seleccionar al menos Descripción y Costo.")
                else:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    contador = 0
                    
                    for index, row in df_import.iterrows():
                        try:
                            if pd.isna(row[col_desc]) or pd.isna(row[col_costo]):
                                continue
                                
                            desc = str(row[col_desc])
                            costo_str = str(row[col_costo]).replace('$', '').replace(',', '').strip()
                            costo = float(costo_str)
                            
                            codigo = str(row[col_codigo]) if col_codigo != "-- Omitir --" and not pd.isna(row[col_codigo]) else f"GEN-{contador}"
                            precio_venta = costo * (1 + (margen/100))
                            
                            cursor.execute('''
                            INSERT OR REPLACE INTO productos (codigo, descripcion, proveedor, precio_costo, precio_venta, stock_actual)
                            VALUES (?, ?, ?, ?, ?, COALESCE((SELECT stock_actual FROM productos WHERE codigo = ?), 10))
                            ''', (codigo, desc, nombre_proveedor, costo, precio_venta, codigo))
                            contador += 1
                        except Exception as e:
                            pass 
                            
                    conn.commit()
                    conn.close()
                    st.success(f"¡Fantástico! Se importaron {contador} productos de {nombre_proveedor}.")
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")

with tab_caja:
    st.header("Cierre de Caja Diario")
    conn = get_db_connection()
    df_ventas = pd.read_sql_query("SELECT * FROM ventas", conn)
    conn.close()
    
    if not df_ventas.empty:
        df_ventas['fecha'] = pd.to_datetime(df_ventas['fecha'])
        ventas_hoy = df_ventas[df_ventas['fecha'].dt.date == datetime.now().date()]
        
        st.subheader(f"Ventas del día: {datetime.now().strftime('%d/%m/%Y')}")
        
        col_caja1, col_caja2, col_caja3 = st.columns(3)
        efectivo = ventas_hoy[ventas_hoy['metodo_pago'] == 'Efectivo']['total'].sum()
        tarjeta = ventas_hoy[ventas_hoy['metodo_pago'] == 'Tarjeta/Débito']['total'].sum()
        mp = ventas_hoy[ventas_hoy['metodo_pago'] == 'Mercado Pago']['total'].sum()
        
        col_caja1.metric("💵 Efectivo", f"${efectivo:,.2f}")
        col_caja2.metric("💳 Tarjeta", f"${tarjeta:,.2f}")
        col_caja3.metric("📱 Mercado Pago", f"${mp:,.2f}")
        
        st.markdown(f"### Total Recaudado Hoy: **${(efectivo + tarjeta + mp):,.2f}**")
        st.dataframe(ventas_hoy[['fecha', 'metodo_pago', 'total']], use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay ventas registradas.")

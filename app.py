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
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, metodo_pago TEXT, total REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS cierres_caja 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_cierre TEXT, total_ventas REAL)''')
    
    # Parche de seguridad 1: Agrega 'subcategoria' si no existe
    try:
        cursor.execute("ALTER TABLE productos ADD COLUMN subcategoria TEXT")
    except:
        pass
        
    # Parche de seguridad 2: Agrega 'unidades_paquete' si no existe
    try:
        cursor.execute("ALTER TABLE productos ADD COLUMN unidades_paquete INTEGER DEFAULT 1")
    except:
        pass
        
    conn.commit()
    conn.close()

init_db()

tab_pos, tab_catalogo, tab_excel, tab_caja = st.tabs(["💳 Registrar Venta", "📦 Catálogo", "📊 Importar Excel", "💰 Cierre de Caja"])

with tab_pos:
    st.header("Registrar Venta")
    conn = get_db_connection()
    df_prods = pd.read_sql_query("SELECT * FROM productos", conn)
    conn.close()

    if 'carrito' not in st.session_state: 
        st.session_state.carrito = []

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Agregar Producto")
        
        # 1. Selector de Marca
        lista_marcas = [m for m in df_prods['marca'].unique() if pd.notna(m) and m != ""]
        lista_marcas.sort()
        marca_sel = st.selectbox("1. Filtrar por Marca", options=["-- Todas --"] + lista_marcas)
        
        if marca_sel != "-- Todas --":
            df_filtrado = df_prods[df_prods['marca'] == marca_sel]
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
                    st.session_state.carrito.append({
                        "id_item": datetime.now().timestamp(), 
                        "codigo": cod, 
                        "desc": prod['descripcion'], 
                        "precio": prod['precio_venta'], 
                        "cant": cant
                    })
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
            
            metodo_pago = st.radio("Método de Pago", 
                                   ("Efectivo", "Mercado Pago", "Transferencia Santander", "Transferencia BERSA", "Debito", "Credito"), 
                                   horizontal=True)
            
            # Calculadora de vuelto para Efectivo
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
                c.execute("INSERT INTO ventas (fecha, metodo_pago, total) VALUES (?, ?, ?)", 
                          (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), metodo_pago, total_final))
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
        busqueda = st.text_input("🔍 Buscar por descripción, código, marca, categoría o sub-categoría...", key="search_cat")
        df_mostrar = df
        if busqueda:
            df_mostrar = df[df['descripcion'].str.contains(busqueda, case=False, na=False) | 
                            df['codigo'].str.contains(busqueda, case=False, na=False) | 
                            df['marca'].str.contains(busqueda, case=False, na=False) |
                            df['categoria'].str.contains(busqueda, case=False, na=False) |
                            df['subcategoria'].str.contains(busqueda, case=False, na=False)]
        
        # Mostramos las columnas relevantes en el catálogo para verificar los costos unitarios
        st.dataframe(df_mostrar[['codigo', 'descripcion', 'marca', 'precio_costo', 'precio_venta', 'stock_actual', 'unidades_paquete']], use_container_width=True)

    with col_cat2:
        st.subheader("🔄 Actualizar Stock Manual")
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
    st.header("📊 Importar Excel y Parametrizar")
    archivo_ex = st.file_uploader("Subir archivo de productos", type=["xlsx", "xls", "csv"])
    
    if archivo_ex:
        try:
            if archivo_ex.name.endswith('.csv'):
                df_import = pd.read_csv(archivo_ex)
            else:
                df_import = pd.read_excel(archivo_ex)
                
            st.write("👀 **Vista previa de los datos a importar:**")
            st.dataframe(df_import.head(5), use_container_width=True)
            
            st.divider()
            st.subheader("⚙️ Parametrización de Columnas")
            
            def autodetectar_columna(opciones, posibles_nombres):
                for i, col in enumerate(opciones):
                    if str(col).lower().strip() in posibles_nombres:
                        return i
                return 0

            cols = df_import.columns.tolist()
            
            # Fila 1 de configuraciones
            col1, col2, col3, col4 = st.columns(4)
            c_marca = col1.selectbox("🏢 Marca", cols, index=autodetectar_columna(cols, ['marca', 'proveedor', 'fabricante']))
            c_art = col2.selectbox("🏷️ Artículo (Código)", cols, index=autodetectar_columna(cols, ['articulo', 'art', 'codigo', 'cod', 'sku']))
            c_cat = col3.selectbox("📁 Categoría", cols, index=autodetectar_columna(cols, ['categoria', 'rubro', 'familia']))
            c_subcat = col4.selectbox("📂 Sub-Categoría", cols, index=autodetectar_columna(cols, ['subcategoria', 'sub-categoria', 'sub', 'subrubro']))
            
            # Fila 2 de configuraciones
            col5, col6, col7, col8 = st.columns(4)
            c_desc = col5.selectbox("📝 Descripción", cols, index=autodetectar_columna(cols, ['descripcion', 'producto', 'detalle', 'nombre']))
            c_precio = col6.selectbox("💲 Precio (Costo del Bulto/Paquete)", cols, index=autodetectar_columna(cols, ['precio', 'costo', 'valor']))
            c_cant = col7.selectbox("📦 Cantidad (Stock a ingresar)", cols, index=autodetectar_columna(cols, ['cantidad', 'cant', 'stock', 'unidades']))
            c_margen = col8.selectbox("📈 Margen (%)", cols, index=autodetectar_columna(cols, ['margen', 'ganancia', '%']))
            
            # Fila 3: Unidades por paquete
            col9, col10, col11, col12 = st.columns(4)
            c_unidades = col9.selectbox("📦 Unid. por Paquete (Divide Costo)", cols, index=autodetectar_columna(cols, ['unidades', 'docena', 'pack', 'cant_paquete']))
            
            st.divider()
            
            col_glob1, col_glob2 = st.columns(2)
            with col_glob1:
                usar_margen_global = st.checkbox("Ignorar columna de margen y usar un Margen Global")
                margen_global = 70.0
                if usar_margen_global:
                    margen_global = st.number_input("Margen Global a aplicar (%)", min_value=0.0, value=70.0)

            with col_glob2:
                # Muy útil si la lista de Excel no tiene columna de unidades y son todos de docena o unidad
                usar_unidades_global = st.checkbox("Ignorar columna de Unidades y usar un valor Global", value=True)
                unidades_global = 1
                if usar_unidades_global:
                    unidades_global = st.number_input("Unidades x Paquete (Ej: 12 para docena, 1 para unitario)", min_value=1, value=1)

            if st.button("🚀 Procesar e Importar al Catálogo"):
                conn = get_db_connection()
                cursor = conn.cursor()
                
                count = 0
                for _, row in df_import.iterrows():
                    try:
                        marca = str(row[c_marca])
                        codigo = str(row[c_art])
                        categoria = str(row[c_cat])
                        subcategoria = str(row[c_subcat])
                        desc = str(row[c_desc])
                        costo_total = float(row[c_precio])
                        stock = int(row[c_cant])
                        
                        # Determinar Margen
                        m = margen_global if usar_margen_global else float(row[c_margen])
                        
                        # Determinar Costo Unitario
                        if usar_unidades_global:
                            unidades = unidades_global
                        else:
                            try:
                                unidades = int(row[c_unidades])
                                if unidades <= 0: unidades = 1
                            except:
                                unidades = 1
                                
                        costo_unitario = costo_total / unidades
                        venta = costo_unitario * (1 + (m / 100))
                        
                        cursor.execute('''INSERT OR REPLACE INTO productos 
                                         (codigo, descripcion, marca, categoria, subcategoria, precio_costo, precio_venta, stock_actual, unidades_paquete) 
                                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                                      (codigo, desc, marca, categoria, subcategoria, costo_unitario, venta, stock, unidades))
                        count += 1
                    except Exception as e:
                        continue
                        
                conn.commit()
                conn.close()
                st.success(f"✅ ¡Éxito! Se procesaron e importaron {count} productos correctamente.")
                st.rerun()
                
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")
    else:
        st.info("Por favor, sube un archivo Excel o CSV para comenzar.")

with tab_caja:
    st.header("💰 Cierre de Caja Diario")
    conn = get_db_connection()
    df_v = pd.read_sql_query("SELECT * FROM ventas", conn)
    conn.close()

    if not df_v.empty:
        df_v['fecha_dt'] = pd.to_datetime(df_v['fecha'])
        df_v['solo_fecha'] = df_v['fecha_dt'].dt.date
        
        col_filtro, _ = st.columns([1, 2])
        with col_filtro:
            fecha_seleccionada = st.date_input("📅 Selecciona la fecha de cierre:", datetime.now().date())
        
        ventas_dia = df_v[df_v['solo_fecha'] == fecha_seleccionada]
        
        if not ventas_dia.empty:
            total_dia = ventas_dia['total'].sum()
            
            st.markdown(f"### 💵 Total de Ventas del Día: **${total_dia:,.2f}**")
            st.divider()
            
            st.subheader("📊 Desglose por Método de Pago")
            desglose = ventas_dia.groupby('metodo_pago')['total'].sum().reset_index()
            
            columnas = st.columns(len(desglose))
            for i, row in enumerate(desglose.itertuples()):
                columnas[i].metric(label=row.metodo_pago, value=f"${row.total:,.2f}")
            
            st.divider()
            st.subheader("📝 Detalle de Operaciones")
            st.dataframe(
                ventas_dia[['fecha', 'metodo_pago', 'total']].rename(columns={'fecha':'Hora y Fecha', 'metodo_pago':'Método Usado', 'total':'Monto'}),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning(f"No hay ventas registradas para el día {fecha_seleccionada.strftime('%d/%m/%Y')}.")
            
    else:
        st.info("Aún no tienes ventas registradas en el sistema. ¡Ve a la pestaña de ventas para hacer la primera!")

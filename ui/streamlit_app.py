import streamlit as st
import pandas as pd
import ast
import altair as alt
import time

from agent.langchain_agent import get_agent_and_db
from agent.query_parser import detect_output_type
from agent.actions import plot_results, save_to_csv, plot_with_altair

st.set_page_config(
    page_title="Agente Inteligente de Ventas", 
    page_icon="📊",
    layout="wide"
)

# ============= ESTADO DE SESIÓN =============
if "history" not in st.session_state:
    st.session_state.history = []
if "last_df" not in st.session_state:
    st.session_state.last_df = None
if "last_sql" not in st.session_state:
    st.session_state.last_sql = None

# ============= FUNCIONES AUXILIARES =============
def extract_sql_and_results(steps):
    """Extrae SQL y resultados de forma robusta"""
    sql_query = None
    raw_results = None
    
    for action, response in reversed(steps):
        if hasattr(action, "tool") and action.tool == "sql_db_query":
            sql_query = action.tool_input
            try:
                # Manejar diferentes formatos de respuesta
                if isinstance(response, str):
                    raw_results = ast.literal_eval(response)
                elif isinstance(response, list):
                    raw_results = response
                else:
                    raw_results = list(response)
            except:
                raw_results = None
            break
    
    return sql_query, raw_results

def results_to_dataframe(sql_query, raw_results):
    """Convierte resultados a DataFrame con nombres de columnas correctos"""
    if not raw_results:
        return pd.DataFrame()
    
    try:
        # Extraer nombres de columnas del SQL
        select_section = sql_query.upper().split("SELECT")[1].split("FROM")[0]
        
        # Limpiar y extraer nombres de columnas
        columns = []
        for col in select_section.split(","):
            col = col.strip()
            # Buscar alias (AS nombre)
            if " AS " in col.upper():
                columns.append(col.split(" AS ")[-1].strip())
            else:
                # Tomar el último elemento después de puntos (tabla.columna)
                columns.append(col.split(".")[-1].strip())
        
        # Crear DataFrame
        df = pd.DataFrame.from_records(raw_results, columns=columns)
        
        # Limpiar nombres de columnas
        df.columns = [col.replace('"', '').replace('`', '').strip() for col in df.columns]
        
        return df
    except Exception as e:
        # Fallback: crear columnas genéricas
        if raw_results and len(raw_results) > 0:
            num_cols = len(raw_results[0]) if isinstance(raw_results[0], (list, tuple)) else 1
            columns = [f"columna_{i+1}" for i in range(num_cols)]
            return pd.DataFrame(raw_results, columns=columns)
        return pd.DataFrame()

# ============= SIDEBAR =============
with st.sidebar:
    st.header("⚙️ Configuración")
    
    # Inicializar agente
    with st.spinner("Inicializando agente..."):
        agent, db = get_agent_and_db()
    st.success("✅ Agente listo")
    
    st.divider()
    
    # Ejemplos de consultas
    st.subheader("📝 Ejemplos de consultas")
    ejemplos = [
        "Top 5 productos en Medellín",
        "Total de ventas por sede en 2025",
        "Producto más vendido en Bogotá en septiembre",
        "Ventas promedio por mes",
        "Clientes que más han comprado"
    ]
    
    ejemplo_seleccionado = st.selectbox("Selecciona un ejemplo:", [""] + ejemplos)
    
    st.divider()
    
    # Información de la BD
    if st.checkbox("🗄️ Ver información de la BD"):
        try:
            with db._engine.connect() as conn:
                # Contar registros
                count_df = pd.read_sql("SELECT COUNT(*) as total FROM ventas", conn)
                st.metric("Total de registros", count_df['total'].iloc[0])
                
                # Mostrar sedes disponibles
                sedes_df = pd.read_sql(
                    "SELECT DISTINCT sede, COUNT(*) as registros FROM ventas GROUP BY sede ORDER BY sede", 
                    conn
                )
                st.dataframe(sedes_df, use_container_width=True)
                
                # Rango de fechas
                fechas_df = pd.read_sql(
                    "SELECT MIN(fecha) as desde, MAX(fecha) as hasta FROM ventas", 
                    conn
                )
                st.write(f"📅 Datos desde {fechas_df['desde'].iloc[0]} hasta {fechas_df['hasta'].iloc[0]}")
        except Exception as e:
            st.error(f"Error al obtener info: {e}")

# ============= UI PRINCIPAL =============
st.title("📊 Agente Inteligente de Análisis de Ventas")
st.caption("Haz preguntas en lenguaje natural sobre los datos de ventas")

# Input de consulta
col1, col2 = st.columns([4, 1])
with col1:
    query = st.text_input(
        "🔍 Tu pregunta:",
        value=ejemplo_seleccionado if ejemplo_seleccionado else "",
        placeholder="Ej: Top 5 productos más vendidos en Bogotá en octubre de 2025"
    )
with col2:
    st.write("")  # Espaciado
    ejecutar = st.button("🚀 Consultar", type="primary", use_container_width=True)

# ============= PROCESAR CONSULTA =============
if (query and ejecutar) or (ejemplo_seleccionado and st.sidebar.button("Usar ejemplo")):
    consulta_actual = query if query else ejemplo_seleccionado
    
    with st.spinner("🤔 Procesando tu consulta..."):
        output_type = detect_output_type(consulta_actual)
        
        try:
            # Ejecutar agente
            start_time = time.time()
            result = agent.invoke({"input": consulta_actual})
            elapsed_time = time.time() - start_time
            
            steps = result.get("intermediate_steps", [])
            
            # Extraer SQL y resultados
            sql_query, raw_results = extract_sql_and_results(steps)
            
            if sql_query and raw_results:
                # Convertir a DataFrame
                df = results_to_dataframe(sql_query, raw_results)
                
                # Guardar en estado y historial
                st.session_state.last_df = df
                st.session_state.last_sql = sql_query
                
                st.session_state.history.insert(0, {
                    "query": consulta_actual,
                    "type": output_type,
                    "df": df,
                    "sql": sql_query,
                    "time": elapsed_time
                })
                
                # Limitar historial a 10 elementos
                st.session_state.history = st.session_state.history[:10]
                
            else:
                st.warning("⚠️ No se pudo extraer resultados de la consulta")
                
        except Exception as e:
            st.error(f"❌ Error al procesar: {str(e)}")
            with st.expander("Ver detalles del error"):
                st.code(str(e))

# ============= MOSTRAR RESULTADOS ACTUALES =============
if st.session_state.last_df is not None and not st.session_state.last_df.empty:
    st.divider()
    st.subheader("📋 Resultados")
    
    # Mostrar SQL
    with st.expander("🔍 Ver consulta SQL ejecutada"):
        st.code(st.session_state.last_sql, language="sql")
    
    # Métricas rápidas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Filas", len(st.session_state.last_df))
    with col2:
        st.metric("Columnas", len(st.session_state.last_df.columns))
    with col3:
        if st.session_state.history:
            st.metric("Tiempo", f"{st.session_state.history[0].get('time', 0):.2f}s")
    
    # Tabs para diferentes vistas
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Tabla", "📈 Gráfico", "📥 Exportar", "📝 Estadísticas"])
    
    with tab1:
        st.dataframe(
            st.session_state.last_df,
            use_container_width=True,
            hide_index=True
        )
    
    with tab2:
        # Visualización con Altair
        if len(st.session_state.last_df.columns) >= 2:
            df_viz = st.session_state.last_df
            
            # Detectar columnas numéricas y categóricas
            numeric_cols = df_viz.select_dtypes(include=['number']).columns.tolist()
            categorical_cols = df_viz.select_dtypes(exclude=['number']).columns.tolist()
            
            if numeric_cols and categorical_cols:
                # Selección de columnas para graficar
                col1, col2, col3 = st.columns(3)
                with col1:
                    x_col = st.selectbox("Eje X (categoría):", categorical_cols)
                with col2:
                    y_col = st.selectbox("Eje Y (valor):", numeric_cols)
                with col3:
                    chart_type = st.selectbox("Tipo:", ["Barras", "Línea", "Puntos"])
                
                # Limitar datos si son muchos
                max_items = st.slider("Máximo de elementos:", 5, 50, min(20, len(df_viz)))
                df_plot = df_viz.nlargest(max_items, y_col) if y_col in numeric_cols else df_viz.head(max_items)
                
                # Crear gráfico según tipo
                if chart_type == "Barras":
                    chart = alt.Chart(df_plot).mark_bar().encode(
                        x=alt.X(y_col, title=y_col),
                        y=alt.Y(x_col, sort='-x', title=x_col),
                        color=alt.Color(x_col, legend=None),
                        tooltip=[x_col, y_col]
                    )
                elif chart_type == "Línea":
                    chart = alt.Chart(df_plot).mark_line(point=True).encode(
                        x=alt.X(x_col, title=x_col),
                        y=alt.Y(y_col, title=y_col),
                        tooltip=[x_col, y_col]
                    )
                else:  # Puntos
                    chart = alt.Chart(df_plot).mark_circle(size=100).encode(
                        x=alt.X(x_col, title=x_col),
                        y=alt.Y(y_col, title=y_col),
                        color=alt.Color(x_col, legend=None),
                        tooltip=[x_col, y_col]
                    )
                
                chart = chart.properties(height=400).interactive()
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("📊 Necesitas al menos una columna categórica y una numérica para graficar")
        else:
            st.info("📊 Necesitas al menos 2 columnas para crear un gráfico")
    
    with tab3:
        col1, col2 = st.columns(2)
        with col1:
            # Descargar CSV
            csv = st.session_state.last_df.to_csv(index=False)
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"resultado_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col2:
            # Guardar en carpeta exported
            if st.button("💾 Guardar en servidor", use_container_width=True):
                filepath = save_to_csv(st.session_state.last_df)
                st.success(f"✅ Guardado en {filepath}")
    
    with tab4:
        # Estadísticas básicas
        st.write("📊 Estadísticas descriptivas:")
        st.dataframe(st.session_state.last_df.describe(), use_container_width=True)

# ============= HISTORIAL =============
if st.session_state.history:
    st.divider()
    st.subheader("🕐 Historial de Consultas")
    
    for i, item in enumerate(st.session_state.history):
        with st.expander(
            f"**Consulta {i+1}:** {item['query'][:50]}... "
            f"({len(item['df'])} filas, {item.get('time', 0):.1f}s)"
        ):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.code(item["sql"], language="sql")
            with col2:
                if st.button(f"Restaurar", key=f"restore_{i}"):
                    st.session_state.last_df = item["df"]
                    st.session_state.last_sql = item["sql"]
                    st.rerun()
            
            st.dataframe(item["df"].head(5), use_container_width=True)
import streamlit as st
import pandas as pd
import ast
import altair as alt
import time
import re
import datetime
import decimal
from sqlalchemy import text  # ⬅️ para ejecutar SQL directo en fallbacks

from agent.langchain_agent import get_agent_and_db
from agent.query_parser import detect_output_type
from agent.actions import plot_results, save_to_csv, save_to_excel

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
if "last_query" not in st.session_state:
    st.session_state.last_query = None
if "last_time" not in st.session_state:
    st.session_state.last_time = None

# ============= UTILIDADES FECHAS (REGLA DURA + FALLBACK) =============
SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12
}

# Detecta BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'
BETWEEN_RE = re.compile(
    r"fecha\s+BETWEEN\s+'(\d{4})-(\d{2})-(\d{2})'\s+AND\s+'(\d{4})-(\d{2})-(\d{2})'",
    re.IGNORECASE
)

def get_date_bounds_and_years(db):
    """Devuelve (min_fecha, max_fecha, [years disponibles])."""
    with db._engine.connect() as conn:
        bounds = conn.execute(text(
            "SELECT MIN(fecha) AS minf, MAX(fecha) AS maxf FROM ventas"
        )).mappings().first()
        years = conn.execute(text(
            "SELECT DISTINCT EXTRACT(YEAR FROM fecha)::int AS y "
            "FROM ventas ORDER BY y"
        )).fetchall()
    minf, maxf = bounds["minf"], bounds["maxf"]
    year_list = [r[0] for r in years]
    return minf, maxf, year_list

def infer_missing_year_from_query(nl_query: str, db):
    """
    Si el usuario menciona un mes en español y NO menciona año (20xx),
    añadimos por defecto el año MÁS RECIENTE con datos en la BD.
    """
    q = (nl_query or "").lower()
    has_year = re.search(r"\b20\d{2}\b", q) is not None
    month = next((m for m in SPANISH_MONTHS if m in q), None)
    if has_year or month is None:
        return nl_query  # no tocamos

    _, _, years = get_date_bounds_and_years(db)
    if not years:
        return nl_query
    last_year = years[-1]
    return f"{nl_query.strip()} de {last_year}"

def patch_sql_to_latest_year_if_out_of_range(sql_stmt: str, db):
    """
    Si el agente generó un BETWEEN fuera del rango de la BD (p.ej. 2023),
    sustituimos el año por el último año disponible, manteniendo mes/día.
    """
    if not sql_stmt:
        return sql_stmt
    m = BETWEEN_RE.search(sql_stmt)
    if not m:
        return sql_stmt

    y1, m1, d1, y2, m2, d2 = map(int, m.groups())
    minf, maxf, years = get_date_bounds_and_years(db)
    if not years:
        return sql_stmt

    # Si cualquiera de los años está antes del mínimo, subimos al último año con datos
    if y1 < minf.year or y2 < minf.year:
        target_year = years[-1]
        new1 = f"{target_year}-{m1:02d}-{d1:02d}"
        new2 = f"{target_year}-{m2:02d}-{d2:02d}"
        return BETWEEN_RE.sub(
            f"fecha BETWEEN '{new1}' AND '{new2}'",
            sql_stmt
        )

    # También podríamos recortar si excede el máximo, pero no es necesario ahora.
    return sql_stmt

# ============= FUNCIONES AUXILIARES (EXTRACCIÓN Y DF) =============
def extract_sql_and_results(steps):
    """Extrae SQL y resultados tolerando reprs con datetime/Decimal."""
    sql_query, raw_results = None, None

    for action, response in reversed(steps or []):
        if hasattr(action, "tool") and action.tool == "sql_db_query":
            sql_query = action.tool_input

            # 1) Si ya es lista/tuplas
            if isinstance(response, list):
                raw_results = response
                break

            # 2) Si es string, intentamos varias rutas
            if isinstance(response, str):
                # a) literal_eval directo
                try:
                    raw_results = ast.literal_eval(response)
                    break
                except Exception:
                    pass
                # b) aislar bloque [...] y literal_eval
                try:
                    m = re.search(r"\[.*\]", response, re.DOTALL)
                    if m:
                        raw_results = ast.literal_eval(m.group(0))
                        break
                except Exception:
                    pass
                # c) eval "seguro" con globals limitados
                try:
                    safe_globals = {
                        "__builtins__": {},
                        "datetime": datetime,
                        "Decimal": decimal.Decimal,
                    }
                    raw_results = eval(response, safe_globals, {})
                    if isinstance(raw_results, (list, tuple)):
                        raw_results = list(raw_results)
                        break
                except Exception:
                    pass

            # 3) último recurso
            try:
                raw_results = list(response)
                break
            except Exception:
                raw_results = None
            break

    return sql_query, raw_results

def _normalize_cell(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (datetime.datetime, datetime.date)):
        try:
            return v.date() if hasattr(v, "date") else v
        except Exception:
            return str(v)
    return v

def results_to_dataframe(sql_query, raw_results):
    """Convierte resultados a DataFrame con nombres de columnas correctos."""
    if not raw_results:
        return pd.DataFrame()

    try:
        select_section = sql_query.upper().split("SELECT")[1].split("FROM")[0]
        columns = []
        for col in select_section.split(","):
            col = col.strip()
            if " AS " in col.upper():
                columns.append(col.split(" AS ")[-1].strip())
            else:
                columns.append(col.split(".")[-1].strip())

        df = pd.DataFrame.from_records(raw_results, columns=columns)
        df = df.applymap(_normalize_cell)
        df.columns = [col.replace('"', '').replace('`', '').strip().upper() for col in df.columns]
        return df
    except Exception:
        if raw_results and len(raw_results) > 0:
            num_cols = len(raw_results[0]) if isinstance(raw_results[0], (list, tuple)) else 1
            columns = [f"COLUMNA_{i+1}" for i in range(num_cols)]
            return pd.DataFrame(raw_results, columns=columns)
        return pd.DataFrame()

# ============= SIDEBAR =============
with st.sidebar:
    st.header("⚙️ Configuración")
    with st.spinner("Inicializando agente..."):
        agent, db = get_agent_and_db()
    st.success("✅ Agente listo")

    st.divider()

    # Ejemplos de consultas
    st.subheader("📝 Ejemplos de consultas")
    ejemplos = [
        # Ventas por sede (monto)
        "Total de ventas (cantidad*precio) por sede en 2025 — todas las sedes, sin límite, ordenar de mayor a menor.",
        
        # Top N productos en una ciudad y año
        "Top 5 productos más vendidos en Medellín en 2025 — sumar cantidad, ordenar de mayor a menor.",
        
        # Producto más vendido en un mes/año concreto
        "Producto más vendido en Bogotá en septiembre de 2024 — sumar cantidad, devolver solo 1 fila (el máximo).",
                
        # Ventas por producto en una ciudad
        "Total de ventas (cantidad*precio) por producto en Cali durante 2025 — sin límite, ordenar de mayor a menor.",
        
        # Sede ganadora (1 fila)
        "Sede con mayores ventas en 2025 — sumar cantidad*precio y devolver solo la sede ganadora (1 fila).",
        
        # Top productos a nivel nacional
        "Top 10 productos con mayor cantidad vendida en todo 2025 (todas las sedes) — sumar cantidad, ordenar de mayor a menor.",
        
        # Ventas diarias en un rango concreto
        "Ventas totales por día en Bogotá entre 2025-11-01 y 2025-11-30 — sumar cantidad*precio, sin límite, ordenar por fecha ascendente.",
        
        # Ranking de vendedores por monto
        "Top 5 vendedores por ventas totales (cantidad*precio) en 2025 — ordenar de mayor a menor.",
        
        # Conteo de registros por sede (útil para debug)
        "Número de registros por sede en 2025 — sin límite, ordenar alfabéticamente por sede."
    ]

    ejemplo_seleccionado = st.selectbox("Selecciona un ejemplo:", [""] + ejemplos)

    st.divider()

    # Información de la BD
    if st.checkbox("🗄️ Ver información de la BD"):
        try:
            with db._engine.connect() as conn:
                count_df = pd.read_sql("SELECT COUNT(*) as total FROM ventas", conn)
                st.metric("Total de registros", f"{count_df['total'].iloc[0]:,}")

                sedes_df = pd.read_sql(
                    "SELECT DISTINCT sede, COUNT(*) as registros "
                    "FROM ventas GROUP BY sede ORDER BY sede",
                    conn
                )
                st.dataframe(sedes_df, use_container_width=True, hide_index=True)

                fechas_df = pd.read_sql(
                    "SELECT MIN(fecha) as desde, MAX(fecha) as hasta FROM ventas",
                    conn
                )
                st.write(f"📅 Desde {fechas_df['desde'].iloc[0]} hasta {fechas_df['hasta'].iloc[0]}")
        except Exception as e:
            st.error(f"Error: {e}")

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
    st.write("")
    ejecutar = st.button("🚀 Consultar", type="primary", use_container_width=True)

# ============= PROCESAR CONSULTA =============
if (query and ejecutar) or (ejemplo_seleccionado and st.sidebar.button("Usar ejemplo")):
    consulta_actual = query if query else ejemplo_seleccionado

    # 🔒 Regla dura: si no hay año explícito y hay mes, añadimos el año más reciente con datos
    consulta_actual = infer_missing_year_from_query(consulta_actual, db)

    with st.spinner("🤔 Procesando tu consulta..."):
        output_type = detect_output_type(consulta_actual)

        try:
            start_time = time.time()
            result = agent.invoke({"input": consulta_actual})
            elapsed_time = time.time() - start_time

            steps = result.get("intermediate_steps", [])
            sql_query, raw_results = extract_sql_and_results(steps)

            df = pd.DataFrame()
            chosen_sql = sql_query

            if sql_query is not None and raw_results is not None:
                df = results_to_dataframe(sql_query, raw_results)

                # 🛟 Fallback: si salió vacío y el SQL trae un BETWEEN fuera de rango, parcheamos y re-ejecutamos
                if df.empty and sql_query:
                    patched_sql = patch_sql_to_latest_year_if_out_of_range(sql_query, db)
                    if patched_sql and patched_sql != sql_query:
                        try:
                            with db._engine.connect() as conn:
                                df2 = pd.read_sql_query(text(patched_sql), conn)
                            if not df2.empty:
                                # normalizamos como arriba (upper y normalization)
                                df2.columns = [c.replace('"', '').replace('`', '').strip().upper() for c in df2.columns]
                                df2 = df2.applymap(_normalize_cell)
                                df = df2
                                chosen_sql = patched_sql
                                st.info("ℹ️ La consulta se ajustó automáticamente al año más reciente con datos.")
                        except Exception as e:
                            # si falla el reintento seguimos con df vacío
                            pass

            if chosen_sql is not None:
                st.session_state.last_df = df.applymap(_normalize_cell)
                st.session_state.last_sql = chosen_sql
                st.session_state.last_query = consulta_actual
                st.session_state.last_time = elapsed_time

                st.session_state.history.insert(0, {
                    "query": consulta_actual,
                    "type": output_type,
                    "df": df,
                    "sql": chosen_sql,
                    "time": elapsed_time
                })
                st.session_state.history = st.session_state.history[:10]
            else:
                st.warning("⚠️ No se pudo extraer resultados de la consulta")
        except Exception as e:
            st.error(f"❌ Error al procesar: {str(e)}")

# ============= MOSTRAR RESULTADOS =============
if st.session_state.last_df is not None and not st.session_state.last_df.empty:
    st.divider()

    # SQL ejecutado (colapsado por defecto y sin duplicados)
    with st.expander("🔍 Ver SQL ejecutado"):
        st.code(st.session_state.last_sql, language="sql")

    # Métricas arriba
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📋 Filas", f"{len(st.session_state.last_df):,}")
    with col2:
        st.metric("📊 Columnas", len(st.session_state.last_df.columns))
    with col3:
        st.metric("⏱️ Tiempo", f"{st.session_state.last_time:.2f}s" if st.session_state.last_time else "N/A")
    with col4:
        total_sum = st.session_state.last_df.select_dtypes(include=['number']).sum().sum()
        if total_sum > 0:
            st.metric("💰 Total", f"{total_sum:,.0f}")

    st.write("")  # Espaciado

    # Tabs: Gráfico / Tabla / Exportar / Estadísticas
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Gráfico", "📋 Tabla", "📥 Exportar", "📊 Estadísticas"])

    with tab1:
        if len(st.session_state.last_df.columns) >= 2:
            # 👇 Copia y normaliza otra vez por si llegó algo raro
            df_viz = st.session_state.last_df.copy().applymap(_normalize_cell)

            # Si alguna numérica quedó como object, fuerzala a numérica
            for c in df_viz.columns:
                if df_viz[c].dtype == "object":
                    try:
                        df_viz[c] = pd.to_numeric(df_viz[c])
                    except Exception:
                        pass
            numeric_cols = df_viz.select_dtypes(include=['number']).columns.tolist()
            categorical_cols = df_viz.select_dtypes(exclude=['number']).columns.tolist()

            if numeric_cols and categorical_cols:
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    x_col = st.selectbox("Categoría (Eje Y):", categorical_cols, key="viz_cat")
                with c2:
                    y_col = st.selectbox("Valor (Eje X):", numeric_cols, key="viz_num")
                with c3:
                    chart_type = st.selectbox("Tipo:", ["Barras", "Línea", "Puntos"], key="viz_type")
                with c4:
                    max_items = st.slider("Máximo:", 5, 50, min(15, len(df_viz)), key="viz_max")

                df_plot = df_viz.nlargest(max_items, y_col) if y_col in numeric_cols else df_viz.head(max_items)

                
                color_palette = [
                    "#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
                    "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC",
                ]

                if chart_type == "Barras":
                    chart = alt.Chart(df_plot).mark_bar().encode(
                        x=alt.X(y_col, title=y_col.replace('_', ' ').title()),
                        y=alt.Y(x_col, sort='-x', title=x_col.replace('_', ' ').title()),
                        color=alt.Color(
                            x_col,
                            scale=alt.Scale(
                                domain=df_plot[x_col].tolist(),
                                range=color_palette[:len(df_plot)]
                            ),
                            legend=None
                        ),
                        tooltip=[alt.Tooltip(x_col, title=x_col.replace('_', ' ').title()),
                                 alt.Tooltip(y_col, title=y_col.replace('_', ' ').title(), format=',.0f')]
                    )
                elif chart_type == "Línea":
                    chart = alt.Chart(df_plot).mark_line(
                        point=alt.OverlayMarkDef(color="red", size=100)
                    ).encode(
                        x=alt.X(x_col, title=x_col.replace('_', ' ').title()),
                        y=alt.Y(y_col, title=y_col.replace('_', ' ').title()),
                        tooltip=[alt.Tooltip(x_col, title=x_col.replace('_', ' ').title()),
                                 alt.Tooltip(y_col, title=y_col.replace('_', ' ').title(), format=',.0f')]
                    )
                else:  # Puntos
                    chart = alt.Chart(df_plot).mark_circle(size=200).encode(
                        x=alt.X(x_col, title=x_col.replace('_', ' ').title()),
                        y=alt.Y(y_col, title=y_col.replace('_', ' ').title()),
                        color=alt.Color(
                            x_col,
                            scale=alt.Scale(
                                domain=df_plot[x_col].tolist(),
                                range=color_palette[:len(df_plot)]
                            ),
                            legend=None
                        ),
                        size=alt.Size(y_col, legend=None),
                        tooltip=[alt.Tooltip(x_col, title=x_col.replace('_', ' ').title()),
                                 alt.Tooltip(y_col, title=y_col.replace('_', ' ').title(), format=',.0f')]
                    )

                chart = chart.properties(
                    height=450,
                    title={
                        "text": f"{y_col.replace('_', ' ').title()} por {x_col.replace('_', ' ').title()}",
                        "fontSize": 16,
                        "anchor": "middle"
                    }
                ).interactive().configure_axis(
                    labelFontSize=12,
                    titleFontSize=14
                )

                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("📊 Se necesita al menos una columna categórica y una numérica para graficar")
        else:
            st.info("📊 Se necesitan al menos 2 columnas para crear un gráfico")

    with tab2:
        st.dataframe(
            st.session_state.last_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                col: st.column_config.NumberColumn(format="%.2f")
                for col in st.session_state.last_df.select_dtypes(include=['number']).columns
            }
        )

    with tab3:
        st.write("### 📥 Opciones de descarga")
        c1, c2  = st.columns(2)
        with c1:
            csv = st.session_state.last_df.to_csv(index=False)
            st.download_button(
                label="📄 Descargar CSV",
                data=csv,
                file_name=f"resultado_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with c2:
            if st.button("💾 Guardar en servidor", use_container_width=True):
                filepath = save_to_csv(st.session_state.last_df)
                st.success(f"✅ Guardado: {filepath}")
    with tab4:
        # ESTADÍSTICAS SIMPLIFICADAS (sin el histograma problemático)
        st.write("### 📊 Estadísticas descriptivas")

        numeric_df = st.session_state.last_df.select_dtypes(include=['number'])

        if not numeric_df.empty:
            # 👉 describe() con índices traducidos al español (OJO: no lo sobrescribas luego)
            stats_df = numeric_df.describe().rename(index={
                "count": "conteo",
                "mean": "media",
                "std": "desviación estándar",
                "min": "mínimo",
                "25%": "25 %",
                "50%": "mediana",
                "75%": "75 %",
                "max": "máximo"
            })

            st.dataframe(
                stats_df,
                use_container_width=True,
                column_config={
                    col: st.column_config.NumberColumn(format="%.2f")
                    for col in stats_df.columns
                }
            )

            # Resumen adicional
            st.write("#### 📈 Resumen rápido")
            col1, col2 = st.columns(2)

            with col1:
                for col in numeric_df.columns[:len(numeric_df.columns)//2 + 1]:
                    st.write(f"**{col}**")
                    st.write(f"- Mínimo: {numeric_df[col].min():,.2f}")
                    st.write(f"- Máximo: {numeric_df[col].max():,.2f}")
                    st.write(f"- Media: {numeric_df[col].mean():,.2f}")
                    st.write("")

            with col2:
                for col in numeric_df.columns[len(numeric_df.columns)//2 + 1:]:
                    st.write(f"**{col}**")
                    st.write(f"- Mínimo: {numeric_df[col].min():,.2f}")
                    st.write(f"- Máximo: {numeric_df[col].max():,.2f}")
                    st.write(f"- Media: {numeric_df[col].mean():,.2f}")
                    st.write("")
        else:
            st.info("No hay columnas numéricas para mostrar estadísticas")


# ============= HISTORIAL (COLAPSADO) =============
if st.session_state.history:
    st.divider()
    with st.expander(f"🕐 Historial de Consultas ({len(st.session_state.history)} consultas)", expanded=False):
        for i, item in enumerate(st.session_state.history):
            c1, c2 = st.columns([4, 1])
            with c1:
                query_preview = item['query'][:50] + "..." if len(item['query']) > 50 else item['query']
                st.write(
                    f"**Consulta {i+1}:** {query_preview} "
                    f"({len(item['df'])} filas, {item.get('time', 0):.1f}s)"
                )
            with c2:
                if st.button("Ver", key=f"view_{i}", use_container_width=True):
                    st.session_state.last_df = item["df"]
                    st.session_state.last_sql = item["sql"]
                    st.session_state.last_query = item["query"]
                    st.session_state.last_time = item.get("time", 0)
                    st.rerun()

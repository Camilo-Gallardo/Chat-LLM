import streamlit as st
import pandas as pd
import ast

from agent.langchain_agent import get_agent_and_db
from agent.query_parser import detect_output_type
from agent.actions import plot_results, save_to_csv

st.set_page_config(page_title="Agente de Ventas", layout="wide")
st.title("📊 Agente Inteligente de Análisis de Ventas")

# Inicializar historial si no existe
if "history" not in st.session_state:
    st.session_state.history = []

query = st.text_input("Haz una pregunta sobre ventas (ej. Top 5 productos en Medellín):")

if query:
    with st.spinner("Procesando..."):
        agent, db = get_agent_and_db()
        output_type = detect_output_type(query)

        try:
            result = agent.invoke({"input": query})
            steps = result.get("intermediate_steps", [])
            print("🔍 Intermediate steps:", steps)

            sql_query = None
            raw_results = None

            # Buscar el ÚLTIMO paso sql_db_query para obtener query + resultado
            for action, response in reversed(steps):
                if hasattr(action, "tool") and action.tool == "sql_db_query":
                    sql_query = action.tool_input
                    try:
                        raw_results = ast.literal_eval(response)
                    except Exception as e:
                        st.error(f"❌ Error al interpretar resultados: {e}")
                        raw_results = None
                    break

            if sql_query and raw_results:
                print("✅ SQL extraído:", sql_query)
                print("📊 Resultados crudos:", raw_results)

                try:
                    select_section = sql_query.split("SELECT")[1].split("FROM")[0]
                    columns = [col.strip().split(" AS ")[-1] for col in select_section.split(",")]
                    df = pd.DataFrame.from_records(raw_results, columns=columns)
                except Exception as e:
                    st.error(f"❌ Error al construir DataFrame: {e}")
                    st.text(f"SQL: {sql_query}")
                    st.text(f"Resultados crudos: {raw_results}")
                    raise e

                # Guardar en historial
                st.session_state.history.insert(0, {
                    "query": query,
                    "type": output_type,
                    "df": df,
                    "sql": sql_query
                })

            else:
                st.warning("⚠️ No se pudo extraer la consulta SQL ni los datos.")

        except Exception as e:
            st.error(f"❌ Error al procesar: {e}")

# Mostrar historial de consultas anteriores
if st.session_state.history:
    st.subheader("🕘 Historial de Consultas")

    for i, item in enumerate(st.session_state.history):
        with st.expander(f"🔎 Consulta {i+1}: {item['query']}"):
            st.code(item["sql"], language="sql")
            if item["type"] == "file":
                filepath = save_to_csv(item["df"])
                st.success(f"✅ CSV generado")
                with open(filepath, "rb") as f:
                    st.download_button("📥 Descargar CSV", data=f, file_name=filepath.split("/")[-1])
                st.dataframe(item["df"])
            elif item["type"] == "plot":
                filepath = plot_results(item["df"])
                st.image(filepath, caption="📊 Gráfico", use_column_width=False, width=400)
                st.dataframe(item["df"])
            else:
                st.dataframe(item["df"])

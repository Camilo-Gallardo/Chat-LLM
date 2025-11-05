# run_examples.py
import time
import sys
import ast
import re
import datetime
import decimal

import pandas as pd

from agent.langchain_agent import get_agent_and_db  # usa el mismo agente de tu app

# -------- Helpers para sacar SQL + resultados del agente --------
def extract_sql_and_results(steps):
    """
    Busca la última llamada real a sql_db_query en intermediate_steps
    y devuelve (sql_query:str|None, rows:list|None)
    Tolerante con reprs que traen datetime/Decimal.
    """
    sql_query, raw_results = None, None

    for action, response in reversed(steps or []):
        if hasattr(action, "tool") and action.tool == "sql_db_query":
            sql_query = action.tool_input

            # Caso 1: ya es lista/tuplas
            if isinstance(response, list):
                raw_results = response
                break

            # Caso 2: string -> intentar literal_eval/eval
            if isinstance(response, str):
                # a) literal_eval directo
                try:
                    raw_results = ast.literal_eval(response)
                    break
                except Exception:
                    pass

                # b) aislar un bloque tipo [...]
                try:
                    m = re.search(r"\[.*\]", response, re.DOTALL)
                    if m:
                        raw_results = ast.literal_eval(m.group(0))
                        break
                except Exception:
                    pass

                # c) eval seguro con datetime/Decimal
                try:
                    safe_globals = {
                        "__builtins__": {},
                        "datetime": datetime,
                        "Decimal": decimal.Decimal,
                    }
                    val = eval(response, safe_globals, {})
                    if isinstance(val, (list, tuple)):
                        raw_results = list(val)
                        break
                except Exception:
                    pass

            # Caso 3: último recurso
            try:
                raw_results = list(response)
                break
            except Exception:
                raw_results = None
            break

    return sql_query, raw_results


def rows_to_df(sql_query, rows):
    """
    Convierte rows a DataFrame e intenta inferir nombres de columnas desde la sección SELECT.
    Si falla, devuelve columnas genéricas.
    """
    if not rows:
        return pd.DataFrame()

    # Inferir columnas desde el SELECT
    cols = None
    if isinstance(sql_query, str):
        try:
            select_section = sql_query.upper().split("SELECT")[1].split("FROM")[0]
            cols = []
            for col in select_section.split(","):
                col = col.strip()
                if " AS " in col.upper():
                    cols.append(col.split(" AS ")[-1].strip())
                else:
                    cols.append(col.split(".")[-1].strip())
        except Exception:
            cols = None

    # Si no pudimos inferir, usar genéricas
    if cols is None:
        if rows and isinstance(rows[0], (list, tuple)):
            cols = [f"col_{i+1}" for i in range(len(rows[0]))]
        else:
            cols = ["col_1"]

    # Normalizar celdas (Decimal, datetime)
    def _norm(v):
        if isinstance(v, decimal.Decimal):
            return float(v)
        if isinstance(v, (datetime.datetime, datetime.date)):
            try:
                return v.date() if hasattr(v, "date") else v
            except Exception:
                return str(v)
        return v

    norm_rows = []
    for r in rows:
        if isinstance(r, (list, tuple)):
            norm_rows.append([_norm(v) for v in r])
        else:
            norm_rows.append([_norm(r)])

    df = pd.DataFrame.from_records(norm_rows, columns=cols)
    # Un poquito de limpieza de nombres
    df.columns = [c.replace('"', '').replace('`', '').strip() for c in df.columns]
    return df


# -------- Tus ejemplos explícitos --------
EXAMPLES = [
    # Ventas por sede (monto)
    "Total de ventas (cantidad*precio) por sede en 2025 — todas las sedes, sin límite, ordenar de mayor a menor.",
    # Top N productos en una ciudad y año
    "Top 5 productos más vendidos en Medellín en 2025 — sumar cantidad, ordenar de mayor a menor.",
    # Producto más vendido en un mes/año concreto
    "Producto más vendido en Bogotá en septiembre de 2024 — sumar cantidad, devolver solo 1 fila (el máximo).",
    # Ventas por mes (monto) de un año
    "Ventas totales por mes en 2024 — sumar cantidad*precio por mes, todas las filas (sin límite), ordenar por mes ascendente.",
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
    "Número de registros por sede en 2025 — sin límite, ordenar alfabéticamente por sede.",
]


# -------- Runner --------
def main():
    agent, db = get_agent_and_db()

    ok = 0
    fail = 0
    results_summary = []

    print("\n=== Ejecutando ejemplos NL → SQL → DB ===\n")

    for idx, question in enumerate(EXAMPLES, start=1):
        print(f"[{idx:02d}] ❓ {question}")
        try:
            t0 = time.time()
            out = agent.invoke({"input": question})
            elapsed = time.time() - t0

            steps = out.get("intermediate_steps", [])
            sql, rows = extract_sql_and_results(steps)

            if sql is None:
                print("   ⚠️  No se pudo extraer el SQL.")
                fail += 1
                results_summary.append((idx, "FAIL", question, None, 0, elapsed))
                continue

            df = rows_to_df(sql, rows) if rows is not None else pd.DataFrame()

            row_count = len(df)
            status = "OK" if row_count > 0 else "EMPTY"

            if status == "OK":
                ok += 1
            else:
                fail += 1

            print(f"   🧠 SQL: {sql}")
            print(f"   📋 Filas: {row_count} | ⏱ {elapsed:.2f}s | ✅ {status}\n")

            results_summary.append((idx, status, question, sql, row_count, elapsed))

        except Exception as e:
            fail += 1
            print(f"   ❌ Error: {e}\n")
            results_summary.append((idx, "ERROR", question, None, 0, 0.0))

    # Resumen final
    print("\n=== Resumen ===")
    for idx, status, q, sql, n, secs in results_summary:
        print(f"[{idx:02d}] {status:6s} | filas={n:4d} | t={secs:5.2f}s | {q}")

    print(f"\nTotales: ✅ OK={ok}  ❌ FAIL/EMPTY/ERROR={fail}\n")
    # Salida con código de proceso útil para CI
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()

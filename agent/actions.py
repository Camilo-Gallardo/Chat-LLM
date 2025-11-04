import pandas as pd
import matplotlib.pyplot as plt
import altair as alt
import uuid
import os

# 📁 Crea carpeta de archivos exportados (si no existe)
EXPORT_FOLDER = "exported"
os.makedirs(EXPORT_FOLDER, exist_ok=True)

def save_to_csv(df: pd.DataFrame):
    """Guarda DataFrame como CSV"""
    filename = f"{EXPORT_FOLDER}/resultado_{uuid.uuid4().hex[:6]}.csv"
    df.to_csv(filename, index=False)
    return filename

def save_to_excel(df: pd.DataFrame):
    """Guarda DataFrame como Excel"""
    filename = f"{EXPORT_FOLDER}/resultado_{uuid.uuid4().hex[:6]}.xlsx"
    df.to_excel(filename, index=False)
    return filename

def plot_results(df: pd.DataFrame):
    """Crea gráfico con matplotlib (legacy)"""
    if len(df.columns) < 2:
        return None
        
    x = df.columns[0]
    y = df.columns[1] if len(df.columns) > 1 else df.columns[0]
    
    plt.figure(figsize=(10, 6))
    plt.bar(df[x], df[y], color='skyblue', edgecolor='navy', alpha=0.7)
    plt.xlabel(x, fontsize=12)
    plt.ylabel(y, fontsize=12)
    plt.title(f"{y} por {x}", fontsize=14, fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    
    filename = f"{EXPORT_FOLDER}/grafico_{uuid.uuid4().hex[:6]}.png"
    plt.savefig(filename, dpi=100, bbox_inches='tight')
    plt.close()
    return filename

def plot_with_altair(df: pd.DataFrame, chart_type="bar"):
    """Crea gráfico interactivo con Altair"""
    if len(df.columns) < 2:
        return None
    
    x = df.columns[0]
    y = df.columns[1]
    
    # Limitar a top 20 si hay muchos datos
    if len(df) > 20:
        df = df.nlargest(20, y) if pd.api.types.is_numeric_dtype(df[y]) else df.head(20)
    
    if chart_type == "bar":
        chart = alt.Chart(df).mark_bar().encode(
            x=alt.X(y, title=y),
            y=alt.Y(x, sort='-x', title=x),
            color=alt.Color(x, legend=None),
            tooltip=[x, y]
        )
    elif chart_type == "line":
        chart = alt.Chart(df).mark_line(point=True).encode(
            x=alt.X(x, title=x),
            y=alt.Y(y, title=y),
            tooltip=[x, y]
        )
    else:  # scatter
        chart = alt.Chart(df).mark_circle(size=100).encode(
            x=alt.X(x, title=x),
            y=alt.Y(y, title=y),
            color=alt.Color(x),
            tooltip=[x, y]
        )
    
    return chart.properties(width=600, height=400).interactive()

def aggregate_data(df: pd.DataFrame, group_by: str, agg_col: str, agg_func: str = "sum"):
    """Agrega datos según parámetros"""
    if group_by not in df.columns or agg_col not in df.columns:
        return df
    
    agg_funcs = {
        "sum": "sum",
        "mean": "mean", 
        "count": "count",
        "max": "max",
        "min": "min"
    }
    
    func = agg_funcs.get(agg_func, "sum")
    
    return df.groupby(group_by)[agg_col].agg(func).reset_index()
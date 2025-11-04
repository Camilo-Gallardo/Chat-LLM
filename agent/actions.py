import pandas as pd
import matplotlib.pyplot as plt
import uuid
import os

# 📁 Crea carpeta de archivos exportados (si no existe)
EXPORT_FOLDER = "exported"
os.makedirs(EXPORT_FOLDER, exist_ok=True)

def save_to_csv(df: pd.DataFrame):
    filename = f"{EXPORT_FOLDER}/resultado_{uuid.uuid4().hex[:6]}.csv"
    df.to_csv(filename, index=False)
    return filename

def plot_results(df: pd.DataFrame):
    # Solo gráfica si hay al menos 2 columnas numéricas o una categórica + una numérica
    x = df.columns[0]
    y = df.columns[1]
    
    plt.figure(figsize=(10, 6))
    plt.bar(df[x], df[y], color='skyblue')
    plt.xlabel(x)
    plt.ylabel(y)
    plt.title(f"{y} por {x}")
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    filename = f"{EXPORT_FOLDER}/grafico_{uuid.uuid4().hex[:6]}.png"
    plt.savefig(filename)
    plt.close()
    return filename

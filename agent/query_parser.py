def detect_output_type(prompt: str) -> str:
    """Detecta el tipo de output deseado basado en el prompt"""
    prompt_lower = prompt.lower()
    
    # Palabras clave para cada tipo
    file_keywords = ["csv", "excel", "archivo", "exporta", "descarga", "guarda"]
    plot_keywords = ["gráfico", "grafico", "visualiza", "muestra", "dibuja", "plot", "chart"]
    
    # Detectar tipo
    if any(keyword in prompt_lower for keyword in file_keywords):
        return "file"
    elif any(keyword in prompt_lower for keyword in plot_keywords):
        return "plot"
    else:
        return "table"

def detect_aggregation(prompt: str) -> dict:
    """Detecta si se necesita agregación y de qué tipo"""
    prompt_lower = prompt.lower()
    
    aggregations = {
        "suma": "sum",
        "total": "sum",
        "promedio": "mean",
        "media": "mean",
        "máximo": "max",
        "maximo": "max",
        "mínimo": "min",
        "minimo": "min",
        "cuenta": "count",
        "cantidad": "count"
    }
    
    for key, value in aggregations.items():
        if key in prompt_lower:
            return {"needs_agg": True, "type": value}
    
    return {"needs_agg": False, "type": None}

def extract_time_range(prompt: str) -> dict:
    """Extrae rango de tiempo del prompt"""
    import re
    
    months = {
        "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
        "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
        "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
    }
    
    # Buscar mes
    month = None
    for month_name, month_num in months.items():
        if month_name in prompt.lower():
            month = month_num
            break
    
    # Buscar año
    year_match = re.search(r'20\d{2}', prompt)
    year = year_match.group() if year_match else "2025"
    
    return {"month": month, "year": year}
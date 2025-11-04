def detect_output_type(prompt: str) -> str:
    prompt = prompt.lower()
    if "csv" in prompt or "excel" in prompt:
        return "file"
    elif "gráfico" in prompt or "grafico" in prompt or "visualiza" or "muestrame" in prompt:
        return "plot"
    else:
        return "table"

# **Aplicación de Análisis de Ventas con Streamlit y Agente LangChain**

**Diseñado y desarrollado por:**

* Joger Muñoz
* Josué Pescador Ramos
* Juan Camilo Gallardo
* Gian Morales
* Fabio Murcia

---

## **Descripción general del proyecto**

Este repositorio contiene una pequeña aplicación de datos que carga información de ventas y expone una interfaz en **Streamlit** junto con un **agente basado en LangChain** para realizar consultas analíticas y exportaciones visuales.

---

## **Contenido**

* `ui/streamlit_app.py` — Interfaz en Streamlit para interactuar con el conjunto de datos y los gráficos generados.
* `agent/` — Código del agente (integración con LangChain, análisis de consultas y acciones).
* `data/ventas.csv` — Datos de ventas de ejemplo utilizados por la aplicación.
* `db/init.sql` — Script SQL de inicialización (crea tablas y datos de ejemplo) para inicializar una base de datos Postgres.
* `exported/` — Carpeta donde se guardan las imágenes y archivos CSV generados por la aplicación o el agente.
* `Dockerfile`, `docker-compose.yml` — Configuración para ejecutar la aplicación y la base de datos Postgres en contenedores.
* `requirements.txt` — Dependencias de Python utilizadas por la aplicación.

---

## **Resumen del proyecto**

El proyecto ofrece una interfaz **Streamlit** que visualiza los datos de ventas contenidos en `data/ventas.csv` y un **agente LangChain** que puede ejecutar consultas y acciones más avanzadas (ver `agent/`).
La aplicación puede ejecutarse localmente con Python o dentro de un contenedor **Docker** usando los archivos provistos.

---

## **Inicio rápido (con Docker)**

1. **Construir y levantar los servicios:**

```bash
docker compose up --build
```

2. **Abrir la interfaz de Streamlit en el navegador:**

```text
http://localhost:8501
```

**Notas:**

* `docker-compose.yml` levanta dos servicios:

  * `db` (Postgres 16)
  * `app` (la aplicación Streamlit).
* El archivo compose usa variables de entorno definidas en un archivo `.env` (ver sección de variables de entorno).
* Si solo deseas ejecutar la aplicación Streamlit (sin Postgres), puedes hacerlo localmente sin Docker (ver siguiente sección).

---

## **Inicio rápido (local / entorno virtual)**

1. **Crear entorno virtual e instalar dependencias:**

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

2. **Ejecutar la aplicación Streamlit:**

```bash
streamlit run ui/streamlit_app.py --server.port=8501
```

Luego abre en tu navegador:
👉 `http://localhost:8501`

---

## **Variables de entorno**

El archivo `docker-compose.yml` utiliza un archivo `.env`.
Variables comunes que puedes definir:

* `POSTGRES_USER` — Usuario de Postgres (por defecto: `user`)
* `POSTGRES_PASSWORD` — Contraseña de Postgres (por defecto: `password`)
* `POSTGRES_DB` — Nombre de la base de datos (por defecto: `mydb`)
* `AWS_ACCESS_KEY_ID` — Clave de acceso de AWS
* `AWS_SECRET_ACCESS_KEY` — Clave secreta de AWS
* `AWS_SESSION_TOKEN` — Token de sesión de AWS
* `AWS_DEFAULT_REGION` — Región AWS donde está disponible el modelo

Ejemplo de `.env` en la raíz del proyecto:

```env
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_DB=mydb
# otras variables de entorno necesarias para la app
```

---

## **Inicialización de la base de datos**

El repositorio incluye el script `db/init.sql` con el esquema y datos de ejemplo.
Puedes aplicarlo de las siguientes maneras:

### 🧩 Opción 1 — Desde el host con `psql` instalado

```bash
psql "postgresql://user:password@localhost:5432/mydb" -f db/init.sql
```

### 🐳 Opción 2 — Desde el contenedor Docker

Después de levantar el contenedor de base de datos:

```bash
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /var/lib/postgresql/data/init.sql || true
```

Si la ruta anterior no existe, puedes copiar el archivo dentro del contenedor o conectarte desde un cliente externo al puerto expuesto.

---

## **Uso de la aplicación**

* La interfaz Streamlit carga `data/ventas.csv` y ofrece visualizaciones y opciones de exportación.
* En el directorio `agent/` encontrarás:

  * `langchain_agent.py` — configuración del agente LangChain que interpreta y ejecuta acciones.
  * `query_parser.py` — analizador para consultas en lenguaje natural.
  * `actions.py` — implementaciones de acciones (consultas, gráficos, exportaciones a CSV o imágenes en `exported/`).

---

## **Salidas generadas**

* Los gráficos y archivos CSV generados se guardan automáticamente en la carpeta `exported/`.
* Revisa dicha carpeta después de ejecutar la app o el agente.

---

## **Notas de desarrollo**

* En el `Dockerfile` se define `ENV PYTHONPATH="/app"` para permitir importaciones como `agent.*` y `ui.*`.
* El Dockerfile instala las dependencias del sistema necesarias para `psycopg2` y otros paquetes.

---

## **Pruebas y verificación rápida**

* Este repositorio no incluye pruebas automatizadas por defecto.
* Para hacer una verificación rápida, ejecuta la aplicación Streamlit y prueba cargar el CSV `data/ventas.csv` y las acciones del agente.
* Si modificas código en `agent/`, reinicia la aplicación para aplicar los cambios.

---

## **Casos límite y consideraciones**

1. **Archivo CSV faltante o malformado:**
   La aplicación debe manejar la ausencia del archivo o encabezados incorrectos. Si no lo hace, valida y corrige el CSV.

2. **Base de datos inaccesible:**
   Asegúrate de que Postgres esté en ejecución y accesible en `localhost:5432`.
   Verifica las variables en `.env` y los logs del contenedor.

3. **Conjuntos de datos grandes / memoria:**
   Streamlit corre en un solo proceso; los CSV muy grandes pueden consumir mucha memoria. Considera muestrear o paginar.

4. **Concurrencia:**
   Si varios usuarios escriben en `exported/` simultáneamente, podrían ocurrir colisiones de nombres de archivos.
   El agente usa nombres con tokens aleatorios, pero puede mejorarse si es necesario.

---

## **Solución de problemas**

* **La página de Streamlit no carga:**
  Verifica que el servicio esté corriendo y escuchando en el puerto `8501`.
  En Docker, usa:

  ```bash
  docker compose ps
  docker compose logs app
  ```

* **Errores de conexión con la base de datos:**
  Verifica los logs del contenedor con:

  ```bash
  docker compose logs db
  ```

  Asegúrate de que las variables `POSTGRES_*` coincidan entre `.env` y el cliente.

* **Problemas con dependencias:**
  Si `pip install -r requirements.txt` falla, asegúrate de usar **Python 3.10** y tener instalados los paquetes del sistema (`gcc`, `libpq-dev`).
  El Dockerfile ya los instala automáticamente.

---



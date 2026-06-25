# ParkControl

Aplicación web responsive para gestión de parqueadero de autos y motos con Flask y PostgreSQL.

## Archivos incluidos
- `app.py`: backend Flask con conexión PostgreSQL.
- `static/parkcontrol-app.html`: frontend responsive.
- `requirements.txt`: dependencias Python.
- `.env.example`: ejemplo de configuración.

## Requisitos
- Python 3.10+
- PostgreSQL

## Instalación en Visual Studio Code
1. Crear y activar entorno virtual.
2. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Crear base de datos en PostgreSQL llamada `parkcontrol`.
4. Copiar `.env.example` a `.env` y ajustar la cadena `DATABASE_URL`.
5. Ejecutar:
   ```bash
   python app.py
   ```
6. Abrir en navegador:
   [http://localhost:5000](http://localhost:5000)

## Funcionalidades entregadas
- Registro de ingreso con validación de placas de autos y motos.
- Normalización automática a mayúsculas y eliminación de espacios.
- Persistencia de datos en PostgreSQL.
- Carga automática de registros del día al volver a abrir la aplicación.
- Registro de pagos con método efectivo o virtual.
- Corrección de registros erróneos.
- Listado de salida con estado OK.
- Formulario de registro y control con CRUD.
- Consulta por placa.
- Submenú de consulta por día, semana y mes.
- Diseño responsive para celular, tableta y computador.

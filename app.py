#!/usr/bin/env python3
"""
ParkControl — Backend Flask + PostgreSQL
========================================
Instalación:
    pip install -r requirements.txt

Archivo .env:
    DATABASE_URL=postgresql://usuario:contrasena@localhost:5432/parkcontrol

Uso local:
    python app.py
"""

import os
import re
from datetime import datetime, timedelta
from calendar import monthrange

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

app = Flask(__name__, static_folder="static")
CORS(app)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/parkcontrol"
)

PATRON_AUTO = re.compile(r"^[A-Z]{3}[0-9]{3}$")
PATRON_MOTO = re.compile(r"^[A-Z]{3}[0-9]{2}[A-Z]{1}$")
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def normalizar_placa(raw: str) -> str:
    return (raw or "").upper().replace(" ", "").strip()


def validar_placa(raw: str) -> dict:
    placa = normalizar_placa(raw)
    if not placa:
        return {"ok": False, "tipo": None, "msg": "La placa no puede estar vacía."}
    if len(placa) != 6:
        return {"ok": False, "tipo": None, "msg": f"Longitud inválida: {len(placa)} caracteres. Se esperan 6."}
    if not placa[:3].isalpha():
        return {"ok": False, "tipo": None, "msg": "Los primeros 3 caracteres deben ser letras."}
    if PATRON_AUTO.match(placa):
        return {"ok": True, "tipo": "Auto", "msg": ""}
    if PATRON_MOTO.match(placa):
        return {"ok": True, "tipo": "Moto", "msg": ""}
    return {
        "ok": False,
        "tipo": None,
        "msg": "Formato inválido. Auto: EHU842 (3 letras + 3 números) | Moto: VHZ43G (3 letras + 2 números + 1 letra)."
    }


def get_fecha_hora() -> dict:
    ahora = datetime.now()
    return {
        "fecha": ahora.strftime("%d-%m-%Y"),
        "hora": ahora.strftime("%H:%M:%S"),
        "dia": DIAS[ahora.weekday()],
    }


def fechas_rango(periodo: str):
    hoy = datetime.now().date()
    if periodo == "dia":
        fechas = [hoy]
    elif periodo == "semana":
        inicio = hoy - timedelta(days=hoy.weekday())
        fechas = [inicio + timedelta(days=i) for i in range(7)]
    else:
        _, ultimo = monthrange(hoy.year, hoy.month)
        fechas = [hoy.replace(day=d) for d in range(1, ultimo + 1)]
    return [f.strftime("%d-%m-%Y") for f in fechas]


def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def inicializar_db():
    ddl = """
    CREATE TABLE IF NOT EXISTS ingresos (
        id BIGSERIAL PRIMARY KEY,
        placa VARCHAR(6) NOT NULL,
        tipo VARCHAR(10) NOT NULL,
        fecha VARCHAR(10) NOT NULL,
        hora VARCHAR(8) NOT NULL,
        dia VARCHAR(12) NOT NULL,
        pagado VARCHAR(3) NOT NULL DEFAULT 'NO',
        hora_pago VARCHAR(8) DEFAULT '',
        estado VARCHAR(12) NOT NULL DEFAULT 'ACTIVO',
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS pagos (
        id BIGSERIAL PRIMARY KEY,
        placa VARCHAR(6) NOT NULL,
        tipo VARCHAR(10) NOT NULL,
        fecha_ingreso VARCHAR(10) NOT NULL,
        hora_ingreso VARCHAR(8) NOT NULL,
        fecha_pago VARCHAR(10) NOT NULL,
        hora_pago VARCHAR(8) NOT NULL,
        metodo VARCHAR(20) NOT NULL DEFAULT 'efectivo',
        estado VARCHAR(5) NOT NULL DEFAULT 'OK',
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS salida (
        id BIGSERIAL PRIMARY KEY,
        placa VARCHAR(6) NOT NULL,
        tipo VARCHAR(10) NOT NULL,
        hora_ingreso VARCHAR(8) NOT NULL,
        estado VARCHAR(5) NOT NULL DEFAULT 'OK',
        fecha VARCHAR(10) NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    );
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()
    finally:
        conn.close()


@app.route("/")
def inicio():
    return send_from_directory("static", "parkcontrol-app.html")


@app.route("/parkcontrol-app.html")
def app_html():
    return send_from_directory("static", "parkcontrol-app.html")


@app.route("/api/ping", methods=["GET"])
def ping():
    try:
        conn = get_conn()
        conn.close()
        return jsonify({"status": "ok", "mensaje": "Conectado a PostgreSQL correctamente"})
    except Exception as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 500


@app.route("/api/ingreso", methods=["POST"])
def registrar_ingreso():
    data = request.get_json()
    if not data or "placa" not in data:
        return jsonify({"ok": False, "msg": "Campo 'placa' requerido."}), 400

    validacion = validar_placa(data["placa"])
    if not validacion["ok"]:
        return jsonify({"ok": False, "msg": validacion["msg"]}), 400

    placa = normalizar_placa(data["placa"])
    fh = get_fecha_hora()
    tipo = validacion["tipo"]
    fecha = fh["fecha"]
    hora = fh["hora"]
    dia = fh["dia"]

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, hora FROM ingresos WHERE placa = %s AND fecha = %s AND estado = 'ACTIVO'",
                (placa, fecha),
            )
            duplicado = cur.fetchone()
            if duplicado:
                return jsonify({"ok": False, "msg": f"La placa {placa} ya fue registrada hoy a las {duplicado['hora']}."}), 409

            cur.execute(
                """
                INSERT INTO ingresos (placa, tipo, fecha, hora, dia, pagado, hora_pago, estado)
                VALUES (%s, %s, %s, %s, %s, 'NO', '', 'ACTIVO')
                RETURNING id
                """,
                (placa, tipo, fecha, hora, dia),
            )
            nuevo_id = cur.fetchone()["id"]
        conn.commit()
    finally:
        conn.close()

    return jsonify({
        "ok": True,
        "msg": f"Vehículo {placa} ({tipo}) registrado correctamente.",
        "registro": {"id": nuevo_id, "placa": placa, "tipo": tipo, "fecha": fecha, "hora": hora, "dia": dia},
    })


@app.route("/api/registros/hoy", methods=["GET"])
def registros_hoy():
    hoy = get_fecha_hora()["fecha"]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, placa, tipo, fecha, hora, dia, pagado, hora_pago, estado
                FROM ingresos
                WHERE fecha = %s AND estado != 'CORRECCION'
                ORDER BY id ASC
                """,
                (hoy,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"ok": True, "registros": [dict(r) for r in rows], "fecha": hoy, "total": len(rows)})


@app.route("/api/pago", methods=["POST"])
def registrar_pago():
    data = request.get_json()
    if not data or "placa" not in data:
        return jsonify({"ok": False, "msg": "Campo 'placa' requerido."}), 400

    placa = normalizar_placa(data["placa"])
    metodo = data.get("metodo", "efectivo").lower()
    if metodo not in ("efectivo", "virtual"):
        metodo = "efectivo"

    fh = get_fecha_hora()
    fecha_pago = fh["fecha"]
    hora_pago = fh["hora"]

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, tipo, fecha, hora
                FROM ingresos
                WHERE placa = %s AND fecha = %s AND pagado = 'NO' AND estado = 'ACTIVO'
                ORDER BY id DESC LIMIT 1
                """,
                (placa, fecha_pago),
            )
            ingreso = cur.fetchone()
            if not ingreso:
                return jsonify({"ok": False, "msg": f"No existe un ingreso pendiente de pago para {placa} en el día actual."}), 404

            cur.execute("UPDATE ingresos SET pagado = 'SÍ', hora_pago = %s WHERE id = %s", (hora_pago, ingreso["id"]))
            cur.execute(
                """
                INSERT INTO pagos (placa, tipo, fecha_ingreso, hora_ingreso, fecha_pago, hora_pago, metodo, estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'OK')
                """,
                (placa, ingreso["tipo"], ingreso["fecha"], ingreso["hora"], fecha_pago, hora_pago, metodo),
            )
            cur.execute(
                """
                INSERT INTO salida (placa, tipo, hora_ingreso, estado, fecha)
                VALUES (%s, %s, %s, 'OK', %s)
                """,
                (placa, ingreso["tipo"], ingreso["hora"], fecha_pago),
            )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True, "msg": f"Pago registrado para {placa}.", "hora_pago": hora_pago, "metodo": metodo})


@app.route("/api/correccion", methods=["POST"])
def correccion_placa():
    data = request.get_json()
    if not data or "placa" not in data:
        return jsonify({"ok": False, "msg": "Campo 'placa' requerido."}), 400

    placa = normalizar_placa(data["placa"])
    hoy = get_fecha_hora()["fecha"]

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE ingresos SET estado = 'CORRECCION' WHERE placa = %s AND fecha = %s", (placa, hoy))
            cur.execute("DELETE FROM pagos WHERE placa = %s AND fecha_pago = %s", (placa, hoy))
            cur.execute("DELETE FROM salida WHERE placa = %s AND fecha = %s", (placa, hoy))
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True, "msg": f"La placa {placa} fue marcada como corrección."})


@app.route("/api/salida", methods=["GET"])
def salida_hoy():
    hoy = get_fecha_hora()["fecha"]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT placa, tipo, hora_ingreso, estado, fecha FROM salida WHERE fecha = %s ORDER BY id ASC",
                (hoy,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"ok": True, "registros": [dict(r) for r in rows], "total": len(rows)})


@app.route("/api/consultar/<placa>", methods=["GET"])
def consultar_placa(placa):
    placa = normalizar_placa(placa)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, placa, tipo, fecha, hora, dia, pagado, hora_pago, estado
                FROM ingresos
                WHERE placa = %s
                ORDER BY id DESC
                """,
                (placa,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"ok": True, "placa": placa, "resultados": [dict(r) for r in rows], "total": len(rows)})


@app.route("/api/registros", methods=["GET"])
def todos_registros():
    periodo = request.args.get("periodo", "").strip().lower()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if periodo in ("dia", "semana", "mes"):
                fechas = fechas_rango(periodo)
                placeholders = ",".join(["%s"] * len(fechas))
                cur.execute(
                    f"""
                    SELECT id, placa, tipo, fecha, hora, dia, pagado, hora_pago, estado
                    FROM ingresos
                    WHERE fecha IN ({placeholders}) AND estado != 'CORRECCION'
                    ORDER BY fecha DESC, id DESC
                    """,
                    fechas,
                )
            else:
                cur.execute(
                    """
                    SELECT id, placa, tipo, fecha, hora, dia, pagado, hora_pago, estado
                    FROM ingresos
                    WHERE estado != 'CORRECCION'
                    ORDER BY id DESC
                    LIMIT 1000
                    """
                )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"ok": True, "registros": [dict(r) for r in rows], "total": len(rows), "periodo": periodo or "todos"})


@app.route("/api/crear", methods=["POST"])
def crear_registro():
    data = request.get_json()
    if not data or "placa" not in data:
        return jsonify({"ok": False, "msg": "Campo 'placa' requerido."}), 400

    validacion = validar_placa(data["placa"])
    if not validacion["ok"]:
        return jsonify({"ok": False, "msg": validacion["msg"]}), 400

    fh = get_fecha_hora()
    placa = normalizar_placa(data["placa"])
    tipo = validacion["tipo"]
    fecha = data.get("fecha", fh["fecha"])
    hora = data.get("hora", fh["hora"])
    dia = data.get("dia", fh["dia"])
    pagado = data.get("pagado", "NO")
    hora_pago = data.get("hora_pago", "")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingresos (placa, tipo, fecha, hora, dia, pagado, hora_pago, estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'ACTIVO')
                RETURNING id
                """,
                (placa, tipo, fecha, hora, dia, pagado, hora_pago),
            )
            nuevo_id = cur.fetchone()["id"]
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "msg": f"Registro creado para {placa}.", "id": nuevo_id})


@app.route("/api/modificar", methods=["PUT"])
def modificar_registro():
    data = request.get_json()
    if not data or "id" not in data:
        return jsonify({"ok": False, "msg": "Campo 'id' requerido."}), 400

    registro_id = data["id"]
    campos = {}

    if "placa" in data and data["placa"]:
        validacion = validar_placa(data["placa"])
        if not validacion["ok"]:
            return jsonify({"ok": False, "msg": validacion["msg"]}), 400
        campos["placa"] = normalizar_placa(data["placa"])
        campos["tipo"] = validacion["tipo"]

    for campo in ("pagado", "hora_pago", "estado"):
        if campo in data:
            campos[campo] = data[campo]

    if not campos:
        return jsonify({"ok": False, "msg": "No hay campos para modificar."}), 400

    set_clause = ", ".join(f"{k} = %s" for k in campos.keys())
    values = list(campos.values()) + [registro_id]

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE ingresos SET {set_clause} WHERE id = %s", values)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "msg": f"Registro {registro_id} actualizado correctamente."})


@app.route("/api/borrar/<int:registro_id>", methods=["DELETE"])
def borrar_registro(registro_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT placa, fecha FROM ingresos WHERE id = %s", (registro_id,))
            registro = cur.fetchone()
            if not registro:
                return jsonify({"ok": False, "msg": f"Registro {registro_id} no encontrado."}), 404
            placa = registro["placa"]
            fecha = registro["fecha"]
            cur.execute("DELETE FROM ingresos WHERE id = %s", (registro_id,))
            cur.execute("DELETE FROM pagos WHERE placa = %s AND fecha_pago = %s", (placa, fecha))
            cur.execute("DELETE FROM salida WHERE placa = %s AND fecha = %s", (placa, fecha))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "msg": f"Registro {registro_id} ({placa}) eliminado en formularios relacionados."})


if __name__ == "__main__":
    inicializar_db()
    app.run(debug=True, host="0.0.0.0", port=5000)

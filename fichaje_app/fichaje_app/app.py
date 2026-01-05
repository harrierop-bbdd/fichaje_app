from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
from datetime import datetime
import csv
import io

app = Flask(__name__)
app.secret_key = "clave_secreta_cambia_esto"

# ---------- BASE DE DATOS ----------
def get_db():
    conn = sqlite3.connect("fichajes.db")
    conn.row_factory = sqlite3.Row
    return conn

def crear_tablas():
    conn = get_db()
    c = conn.cursor()
    # Usuarios
    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE
    )
    """)
    # Fichajes
    c.execute("""
    CREATE TABLE IF NOT EXISTS fichajes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT,
        tipo TEXT,
        fecha TEXT,
        hora TEXT
    )
    """)
    conn.commit()
    conn.close()

crear_tablas()

# ---------- LOGIN ----------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nombre = request.form["nombre"].strip()
        if nombre:
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO usuarios (nombre) VALUES (?)", (nombre,))
            conn.commit()
            conn.close()
            session["usuario"] = nombre
            return redirect("/fichar")
    return render_template("login.html")

# ---------- FICHAJE ----------
@app.route("/fichar", methods=["GET", "POST"])
def fichar():
    if "usuario" not in session:
        return redirect("/")
    if request.method == "POST":
        tipo = request.form["tipo"]
        ahora = datetime.now()
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "INSERT INTO fichajes (usuario, tipo, fecha, hora) VALUES (?, ?, ?, ?)",
            (session["usuario"], tipo, ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M:%S"))
        )
        conn.commit()
        conn.close()
        return redirect("/fichar")
    return render_template("fichar.html", usuario=session["usuario"])

# ---------- TABLA DE FICHAJES ----------
@app.route("/tabla")
def tabla_fichajes():
    if "usuario" not in session:
        return redirect("/")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM fichajes ORDER BY fecha, hora")
    fichajes = c.fetchall()
    conn.close()
    return render_template("tabla_fichajes.html", fichajes=fichajes)

# ---------- RESUMEN MENSUAL ----------
@app.route("/resumen")
def resumen_mensual():
    if "usuario" not in session:
        return redirect("/")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM fichajes ORDER BY usuario, fecha, hora")
    fichajes = c.fetchall()
    conn.close()

    resumen = {}
    for fila in fichajes:
        usuario = fila["usuario"]
        fecha = fila["fecha"]
        hora = fila["hora"]
        tipo = fila["tipo"]

        if usuario not in resumen:
            resumen[usuario] = {}
        if fecha not in resumen[usuario]:
            resumen[usuario][fecha] = {"Entrada": None, "Salida": None, "Pausas": []}

        if tipo == "Entrada":
            resumen[usuario][fecha]["Entrada"] = hora
        elif tipo == "Salida":
            resumen[usuario][fecha]["Salida"] = hora
        elif tipo in ["Pausa", "Fin pausa"]:
            resumen[usuario][fecha]["Pausas"].append((tipo, hora))

    # Calcular horas trabajadas y tiempo en pausa
    resultados = {}
    for usuario, dias in resumen.items():
        resultados[usuario] = []
        for fecha, info in dias.items():
            entrada = info["Entrada"]
            salida = info["Salida"]
            pausas = info["Pausas"]
            tiempo_trabajado = 0
            tiempo_pausa = 0
            if entrada and salida:
                fmt = "%H:%M:%S"
                entrada_dt = datetime.strptime(entrada, fmt)
                salida_dt = datetime.strptime(salida, fmt)
                tiempo_total = (salida_dt - entrada_dt).total_seconds()
                # calcular pausas
                segundos_pausa = 0
                i = 0
                while i < len(pausas)-1:
                    if pausas[i][0] == "Pausa" and pausas[i+1][0] == "Fin pausa":
                        ini = datetime.strptime(pausas[i][1], fmt)
                        fin = datetime.strptime(pausas[i+1][1], fmt)
                        segundos_pausa += (fin - ini).total_seconds()
                        i +=2
                    else:
                        i +=1
                tiempo_trabajado = tiempo_total - segundos_pausa
                tiempo_pausa = segundos_pausa
            resultados[usuario].append({
                "fecha": fecha,
                "entrada": entrada,
                "salida": salida,
                "tiempo_trabajado": tiempo_trabajado/3600, # horas
                "tiempo_pausa": tiempo_pausa/3600
            })
    return render_template("resumen_mensual.html", resultados=resultados)

# ---------- EXPORTAR CSV ----------
@app.route("/exportar")
def exportar_csv():
    if "usuario" not in session:
        return redirect("/")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM fichajes ORDER BY usuario, fecha, hora")
    fichajes = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Usuario", "Tipo", "Fecha", "Hora"])
    for fila in fichajes:
        writer.writerow([fila["usuario"], fila["tipo"], fila["fecha"], fila["hora"]])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="fichajes.csv"
    )

# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)


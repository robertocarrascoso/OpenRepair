from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session, Response
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from config import DB_CONFIG, SECRET_KEY
from utilidades.pdf_generator import generar_pdf
from datetime import datetime, date
import csv
import io
import os

app = Flask(__name__,
            template_folder='plantillas',
            static_folder='estaticos')
app.secret_key = SECRET_KEY


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Inicia sesión para continuar.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Inicia sesión para continuar.', 'error')
            return redirect(url_for('login'))
        if session.get('user_rol') != 'admin':
            flash('Acceso restringido a administradores.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


def get_db():
    import mysql.connector
    return mysql.connector.connect(**DB_CONFIG)


def _construir_where_filtros(filtro, fecha_desde, fecha_hasta, tipo_dispositivo, cliente_nombre):
    where, params = [], []
    if filtro != 'todos':
        where.append("r.estado = %s"); params.append(filtro)
    if fecha_desde:
        where.append("DATE(r.created_at) >= %s"); params.append(fecha_desde)
    if fecha_hasta:
        where.append("DATE(r.created_at) <= %s"); params.append(fecha_hasta)
    if tipo_dispositivo:
        where.append("r.tipo_dispositivo = %s"); params.append(tipo_dispositivo)
    if cliente_nombre:
        where.append("c.nombre LIKE %s"); params.append(f'%{cliente_nombre}%')
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    return where_sql, params


@app.context_processor
def inject_pendientes():
    if 'user_id' not in session:
        return {'pendientes_count': 0}
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) as total FROM reparaciones WHERE estado != 'Entregado'")
    count = cursor.fetchone()['total']
    cursor.close()
    db.close()
    return {'pendientes_count': count}


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_nombre'] = user['nombre']
            session['user_rol'] = user['rol']
            return redirect(url_for('dashboard'))

        flash('Email o contraseña incorrectos.', 'error')
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada.', 'success')
    return redirect(url_for('login'))


@app.route('/')
@login_required
def dashboard():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) as total FROM reparaciones WHERE estado != 'Entregado'")
    pendientes = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM reparaciones WHERE MONTH(created_at) = MONTH(NOW()) AND YEAR(created_at) = YEAR(NOW())")
    este_mes = cursor.fetchone()['total']

    cursor.execute("SELECT COALESCE(SUM(precio_final), 0) as total FROM reparaciones WHERE estado = 'Entregado' AND MONTH(updated_at) = MONTH(NOW()) AND YEAR(updated_at) = YEAR(NOW())")
    ingresos_mes = cursor.fetchone()['total']

    cursor.execute("""
        SELECT AVG(DATEDIFF(updated_at, created_at)) as media
        FROM reparaciones WHERE estado = 'Entregado'
    """)
    row_media = cursor.fetchone()
    tiempo_medio = round(row_media['media'], 1) if row_media['media'] else 0

    cursor.execute("""
        SELECT r.*, c.nombre as cliente_nombre
        FROM reparaciones r
        JOIN clientes c ON r.cliente_id = c.id
        ORDER BY r.created_at DESC LIMIT 5
    """)
    ultimas = cursor.fetchall()

    cursor.execute("SELECT estado, tipo_dispositivo FROM reparaciones")
    reparaciones = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template('dashboard.html',
        pendientes=pendientes,
        este_mes=este_mes,
        ingresos_mes=ingresos_mes,
        tiempo_medio=tiempo_medio,
        ultimas=ultimas,
        reparaciones=reparaciones
    )


@app.route('/nueva-entrada', methods=['GET', 'POST'])
@login_required
def nueva_entrada():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        telefono = request.form.get('telefono', '').strip()
        email = request.form.get('email', '').strip()
        tipo = request.form.get('tipo_dispositivo', '').strip()
        marca = request.form.get('marca', '').strip()
        modelo = request.form.get('modelo', '').strip()
        averia = request.form.get('averia', '').strip()
        observaciones = request.form.get('observaciones', '').strip()

        if not nombre or not averia or not tipo:
            flash('Nombre, avería y tipo de dispositivo son obligatorios.', 'error')
            return redirect(url_for('nueva_entrada'))

        if not telefono and not email:
            flash('Indica al menos un dato de contacto (teléfono o email).', 'error')
            return redirect(url_for('nueva_entrada'))

        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM clientes WHERE telefono = %s OR email = %s", (telefono, email))
        cliente = cursor.fetchone()

        if not cliente:
            cursor.execute("INSERT INTO clientes (nombre, telefono, email) VALUES (%s, %s, %s)", (nombre, telefono, email))
            db.commit()
            cliente_id = cursor.lastrowid
        else:
            cliente_id = cliente['id']

        # Contador atómico por año para evitar códigos duplicados en concurrencia
        year = datetime.now().year
        cursor.execute("INSERT INTO contadores (year, ultimo_num) VALUES (%s, 1) ON DUPLICATE KEY UPDATE ultimo_num = ultimo_num + 1", (year,))
        cursor.execute("SELECT ultimo_num FROM contadores WHERE year = %s", (year,))
        num = cursor.fetchone()['ultimo_num']
        codigo = f"REP-{year}-{num:05d}"

        cursor.execute("""
            INSERT INTO reparaciones (codigo, cliente_id, tipo_dispositivo, marca, modelo, averia, observaciones)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (codigo, cliente_id, tipo, marca, modelo, averia, observaciones))
        reparacion_id = cursor.lastrowid

        cursor.execute("INSERT INTO historial_estados (reparacion_id, estado, tecnico) VALUES (%s, 'Recibido', %s)", (reparacion_id, session.get('user_nombre', 'Técnico')))
        db.commit()
        cursor.close()
        db.close()

        return redirect(url_for('nueva_entrada', pdf=codigo))

    return render_template('nueva_entrada.html')


PER_PAGE = 20


def _get_filtros_from_request():
    filtro = request.args.get('estado', 'todos')
    fecha_desde_str = request.args.get('fecha_desde', '')
    fecha_hasta_str = request.args.get('fecha_hasta', '')
    tipo_dispositivo = request.args.get('tipo_dispositivo', '')
    cliente_nombre = request.args.get('cliente', '')
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1

    fecha_desde = None
    fecha_hasta = None
    if fecha_desde_str:
        try:
            fecha_desde = date.fromisoformat(fecha_desde_str)
        except ValueError:
            pass
    if fecha_hasta_str:
        try:
            fecha_hasta = date.fromisoformat(fecha_hasta_str)
        except ValueError:
            pass

    return filtro, fecha_desde, fecha_hasta, tipo_dispositivo, cliente_nombre, page, fecha_desde_str, fecha_hasta_str


@app.route('/reparaciones')
@login_required
def reparaciones():
    filtro, fecha_desde, fecha_hasta, tipo_dispositivo, cliente_nombre, page, fecha_desde_str, fecha_hasta_str = _get_filtros_from_request()

    db = get_db()
    cursor = db.cursor(dictionary=True)

    where_sql, params = _construir_where_filtros(filtro, fecha_desde, fecha_hasta, tipo_dispositivo, cliente_nombre)

    cursor.execute(f"SELECT COUNT(*) as total FROM reparaciones r JOIN clientes c ON r.cliente_id = c.id{where_sql}", params)
    total = cursor.fetchone()['total']
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(page, total_pages)
    offset = (page - 1) * PER_PAGE

    cursor.execute(f"""
        SELECT r.*, c.nombre as cliente_nombre
        FROM reparaciones r JOIN clientes c ON r.cliente_id = c.id
        {where_sql}
        ORDER BY r.created_at DESC
        LIMIT %s OFFSET %s
    """, params + [PER_PAGE, offset])
    lista = cursor.fetchall()

    cursor.execute("SELECT DISTINCT tipo_dispositivo FROM reparaciones ORDER BY tipo_dispositivo")
    tipos = [row['tipo_dispositivo'] for row in cursor.fetchall()]

    cursor.close()
    db.close()
    return render_template('reparaciones.html',
        reparaciones=lista, filtro_actual=filtro,
        page=page, total_pages=total_pages, total=total,
        fecha_desde=fecha_desde_str, fecha_hasta=fecha_hasta_str,
        tipo_dispositivo=tipo_dispositivo, cliente=cliente_nombre,
        tipos_dispositivo=tipos)


FLUJO_ESTADOS = {
    'Recibido': ['Diagnosticado'],
    'Diagnosticado': ['Presupuesto enviado'],
    'Presupuesto enviado': ['Presupuesto aceptado', 'Entregado'],  # "Entregado" aquí = presupuesto rechazado
    'Presupuesto aceptado': ['Reparando'],
    'Reparando': ['Esperando pieza', 'Listo'],
    'Esperando pieza': ['Reparando'],
    'Listo': ['Entregado'],
    'Entregado': []
}


@app.route('/reparacion/<codigo>')
@login_required
def detalle_reparacion(codigo):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT r.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono,
               c.email as cliente_email, c.id as cid
        FROM reparaciones r JOIN clientes c ON r.cliente_id = c.id
        WHERE r.codigo = %s
    """, (codigo,))
    rep = cursor.fetchone()

    if not rep:
        cursor.close()
        db.close()
        flash('Reparación no encontrada.', 'error')
        return redirect(url_for('reparaciones'))

    cursor.execute("SELECT * FROM historial_estados WHERE reparacion_id = %s ORDER BY fecha DESC", (rep['id'],))
    historial = cursor.fetchall()

    cursor.close()
    db.close()

    estados_posibles = FLUJO_ESTADOS.get(rep['estado'], [])
    return render_template('reparacion.html', rep=rep, historial=historial, estados_posibles=estados_posibles)


@app.route('/reparacion/<codigo>/cambiar-estado', methods=['POST'])
@login_required
def cambiar_estado(codigo):
    nuevo_estado = request.form.get('nuevo_estado')

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM reparaciones WHERE codigo = %s", (codigo,))
    rep = cursor.fetchone()

    if rep and nuevo_estado in FLUJO_ESTADOS.get(rep['estado'], []):
        cursor.execute("UPDATE reparaciones SET estado = %s WHERE codigo = %s", (nuevo_estado, codigo))

        if nuevo_estado == 'Presupuesto aceptado':
            cursor.execute("UPDATE reparaciones SET presupuesto_aceptado = TRUE WHERE codigo = %s", (codigo,))
        elif nuevo_estado == 'Entregado' and rep.get('presupuesto') and not rep.get('presupuesto_aceptado'):
            cursor.execute("UPDATE reparaciones SET presupuesto_aceptado = FALSE WHERE codigo = %s", (codigo,))

        cursor.execute("INSERT INTO historial_estados (reparacion_id, estado, tecnico) VALUES (%s, %s, %s)", (rep['id'], nuevo_estado, session.get('user_nombre', 'Técnico')))
        db.commit()
        flash(f'Estado cambiado a "{nuevo_estado}".', 'success')
    else:
        flash('Cambio de estado no válido.', 'error')

    cursor.close()
    db.close()
    return redirect(url_for('detalle_reparacion', codigo=codigo))
@app.route('/reparacion/<codigo>/presupuesto', methods=['POST'])
@login_required
def enviar_presupuesto(codigo):
    presupuesto = request.form.get('presupuesto', type=float)

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM reparaciones WHERE codigo = %s", (codigo,))
    rep = cursor.fetchone()

    if rep and rep['estado'] == 'Diagnosticado':
        cursor.execute("UPDATE reparaciones SET presupuesto = %s, estado = 'Presupuesto enviado' WHERE codigo = %s", (presupuesto, codigo))
        cursor.execute("INSERT INTO historial_estados (reparacion_id, estado, tecnico) VALUES (%s, 'Presupuesto enviado', %s)", (rep['id'], session.get('user_nombre', 'Técnico')))
        db.commit()
        flash(f'Presupuesto de {presupuesto}€ enviado.', 'success')

    cursor.close()
    db.close()
    return redirect(url_for('detalle_reparacion', codigo=codigo))


@app.route('/reparacion/<codigo>/precio-final', methods=['POST'])
@login_required
def precio_final(codigo):
    precio = request.form.get('precio_final', type=float)

    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE reparaciones SET precio_final = %s WHERE codigo = %s", (precio, codigo))
    db.commit()
    cursor.close()
    db.close()
    flash(f'Precio final: {precio}€.', 'success')
    return redirect(url_for('detalle_reparacion', codigo=codigo))


@app.route('/reparacion/<codigo>/editar', methods=['GET', 'POST'])
@login_required
def editar_reparacion(codigo):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM reparaciones WHERE codigo = %s", (codigo,))
    rep = cursor.fetchone()

    if not rep:
        cursor.close()
        db.close()
        flash('Reparación no encontrada.', 'error')
        return redirect(url_for('reparaciones'))

    if request.method == 'POST':
        tipo = request.form.get('tipo_dispositivo', '').strip() or rep['tipo_dispositivo']
        marca = request.form.get('marca', '').strip()
        modelo = request.form.get('modelo', '').strip()
        averia = request.form.get('averia', '').strip() or rep['averia']
        observaciones = request.form.get('observaciones', '').strip()

        cursor.execute("""
            UPDATE reparaciones SET tipo_dispositivo=%s, marca=%s, modelo=%s,
            averia=%s, observaciones=%s WHERE codigo=%s
        """, (tipo, marca, modelo, averia, observaciones, codigo))
        db.commit()
        cursor.close()
        db.close()
        flash('Reparación actualizada.', 'success')
        return redirect(url_for('detalle_reparacion', codigo=codigo))

    cursor.close()
    db.close()
    return render_template('editar_reparacion.html', rep=rep)


@app.route('/reparacion/<codigo>/eliminar', methods=['POST'])
@login_required
def eliminar_reparacion(codigo):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id FROM reparaciones WHERE codigo = %s", (codigo,))
    rep = cursor.fetchone()

    if not rep:
        cursor.close()
        db.close()
        flash('Reparación no encontrada.', 'error')
        return redirect(url_for('reparaciones'))

    cursor.execute("DELETE FROM historial_estados WHERE reparacion_id = %s", (rep['id'],))
    cursor.execute("DELETE FROM reparaciones WHERE id = %s", (rep['id'],))
    db.commit()
    cursor.close()
    db.close()
    flash(f'Reparación {codigo} eliminada.', 'success')
    return redirect(url_for('reparaciones'))


@app.route('/clientes')
@login_required
def clientes():
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) as total FROM clientes")
    total = cursor.fetchone()['total']
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(page, total_pages)
    offset = (page - 1) * PER_PAGE

    cursor.execute("""
        SELECT c.*, COUNT(r.id) as n_reparaciones
        FROM clientes c
        LEFT JOIN reparaciones r ON c.id = r.cliente_id
        GROUP BY c.id
        ORDER BY c.nombre
        LIMIT %s OFFSET %s
    """, (PER_PAGE, offset))
    lista = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('clientes.html', clientes=lista,
        page=page, total_pages=total_pages, total=total)

@app.route('/cliente/<int:id>')
@login_required
def detalle_cliente(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM clientes WHERE id = %s", (id,))
    cliente = cursor.fetchone()

    if not cliente:
        cursor.close()
        db.close()
        flash('Cliente no encontrado.', 'error')
        return redirect(url_for('clientes'))

    cursor.execute("SELECT * FROM reparaciones WHERE cliente_id = %s ORDER BY created_at DESC", (id,))
    reps = cursor.fetchall()

    cursor.execute("SELECT COALESCE(SUM(precio_final), 0) as total FROM reparaciones WHERE cliente_id = %s AND estado = 'Entregado'", (id,))
    gasto = cursor.fetchone()['total']

    cursor.close()
    db.close()
    return render_template('cliente.html', cliente=cliente, reparaciones=reps, gasto_total=gasto)


@app.route('/cliente/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_cliente(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM clientes WHERE id = %s", (id,))
    cliente = cursor.fetchone()

    if not cliente:
        cursor.close()
        db.close()
        flash('Cliente no encontrado.', 'error')
        return redirect(url_for('clientes'))

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        telefono = request.form.get('telefono', '').strip()
        email = request.form.get('email', '').strip()

        if not nombre:
            flash('El nombre es obligatorio.', 'error')
            cursor.close()
            db.close()
            return render_template('editar_cliente.html', cliente=cliente)

        cursor.execute(
            "UPDATE clientes SET nombre = %s, telefono = %s, email = %s WHERE id = %s",
            (nombre, telefono, email, id)
        )
        db.commit()
        cursor.close()
        db.close()
        flash('Cliente actualizado correctamente.', 'success')
        return redirect(url_for('detalle_cliente', id=id))

    cursor.close()
    db.close()
    return render_template('editar_cliente.html', cliente=cliente)


@app.route('/buscar')
@login_required
def buscar():
    return render_template('buscar.html')


@app.route('/api/buscar')
@login_required
def api_buscar():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({'reparaciones': [], 'clientes': []})

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT r.*, c.nombre as cliente_nombre
        FROM reparaciones r JOIN clientes c ON r.cliente_id = c.id
        WHERE r.codigo LIKE %s OR c.nombre LIKE %s OR c.telefono LIKE %s
        ORDER BY r.created_at DESC LIMIT 10
    """, (f'%{q}%', f'%{q}%', f'%{q}%'))
    reps = cursor.fetchall()

    cursor.execute("""
        SELECT * FROM clientes
        WHERE nombre LIKE %s OR telefono LIKE %s
        LIMIT 10
    """, (f'%{q}%', f'%{q}%'))
    clientes = cursor.fetchall()

    cursor.close()
    db.close()
    return jsonify({'reparaciones': reps, 'clientes': clientes})


@app.route('/api/buscar-cliente')
@login_required
def api_buscar_cliente():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify([])

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM clientes
        WHERE nombre LIKE %s OR telefono LIKE %s OR email LIKE %s
        LIMIT 5
    """, (f'%{q}%', f'%{q}%', f'%{q}%'))
    resultados = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify(resultados)


@app.route('/pdf/<codigo>')
@login_required
def ver_pdf(codigo):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT r.*, c.nombre as nombre_cliente, c.telefono, c.email
        FROM reparaciones r
        JOIN clientes c ON r.cliente_id = c.id
        WHERE r.codigo = %s
    """, (codigo,))
    row = cursor.fetchone()
    cursor.close()
    db.close()

    if not row:
        flash('Reparación no encontrada.', 'error')
        return redirect(url_for('dashboard'))

    datos = {
        'codigo': row['codigo'],
        'nombre_cliente': row['nombre_cliente'],
        'telefono': row.get('telefono', ''),
        'email': row.get('email', ''),
        'tipo_dispositivo': row['tipo_dispositivo'],
        'marca': row.get('marca', ''),
        'modelo': row.get('modelo', ''),
        'averia': row['averia'],
        'observaciones': row.get('observaciones', ''),
        'fecha': row['created_at']
    }

    pdf_dir = os.path.join(app.root_path, 'pdfs')
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, f'{codigo}.pdf')

    generar_pdf(datos, pdf_path)

    return send_file(pdf_path, as_attachment=False, download_name=f'{codigo}.pdf')


@app.route('/reparaciones/csv')
@login_required
def exportar_csv():
    filtro, fecha_desde, fecha_hasta, tipo_dispositivo, cliente_nombre, _, fecha_desde_str, fecha_hasta_str = _get_filtros_from_request()

    db = get_db()
    cursor = db.cursor(dictionary=True)
    where_sql, params = _construir_where_filtros(filtro, fecha_desde, fecha_hasta, tipo_dispositivo, cliente_nombre)

    cursor.execute(f"""
        SELECT r.*, c.nombre as cliente_nombre
        FROM reparaciones r JOIN clientes c ON r.cliente_id = c.id
        {where_sql}
        ORDER BY r.created_at DESC
    """, params)
    lista = cursor.fetchall()
    cursor.close()
    db.close()

    output = io.StringIO()
    output.write('﻿')  # BOM para que Excel detecte UTF-8
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Código', 'Cliente', 'Tipo dispositivo', 'Marca', 'Modelo', 'Avería', 'Estado', 'Presupuesto', 'Precio final', 'Fecha entrada'])

    for r in lista:
        fecha = r['created_at'].strftime('%d/%m/%Y') if isinstance(r['created_at'], datetime) else str(r['created_at'])
        writer.writerow([
            r['codigo'],
            r.get('cliente_nombre', ''),
            r['tipo_dispositivo'],
            r.get('marca', ''),
            r.get('modelo', ''),
            r['averia'],
            r['estado'],
            r.get('presupuesto') or '',
            r.get('precio_final') or '',
            fecha
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=reparaciones.csv'}
    )


@app.route('/admin')
@admin_required
def admin_panel():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre, email, rol, created_at FROM usuarios ORDER BY id")
    usuarios = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('admin.html', usuarios=usuarios)


@app.route('/admin/crear-usuario', methods=['POST'])
@admin_required
def crear_usuario():
    nombre = request.form.get('nombre', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    rol = request.form.get('rol', 'tecnico')

    if not nombre or not email or not password:
        flash('Todos los campos son obligatorios.', 'error')
        return redirect(url_for('admin_panel'))

    if rol not in ('admin', 'tecnico'):
        rol = 'tecnico'

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
    if cursor.fetchone():
        cursor.close()
        db.close()
        flash('Ya existe un usuario con ese email.', 'error')
        return redirect(url_for('admin_panel'))

    cursor.execute(
        "INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (%s, %s, %s, %s)",
        (nombre, email, generate_password_hash(password), rol)
    )
    db.commit()
    cursor.close()
    db.close()
    flash(f'Usuario "{nombre}" creado correctamente.', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/admin/eliminar-usuario/<int:id>', methods=['POST'])
@admin_required
def eliminar_usuario(id):
    if id == session.get('user_id'):
        flash('No puedes eliminar tu propio usuario.', 'error')
        return redirect(url_for('admin_panel'))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre FROM usuarios WHERE id = %s", (id,))
    usuario = cursor.fetchone()

    if not usuario:
        cursor.close()
        db.close()
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('admin_panel'))

    cursor.execute("DELETE FROM usuarios WHERE id = %s", (id,))
    db.commit()
    cursor.close()
    db.close()
    flash(f'Usuario "{usuario["nombre"]}" eliminado.', 'success')
    return redirect(url_for('admin_panel'))


if __name__ == '__main__':
    app.run(debug=True)

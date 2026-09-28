import os
import io
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, session, redirect, url_for, render_template, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'clave_secreta_muy_segura_para_produccion')

# URL de conexión a Neon PostgreSQL desde variables de entorno
DATABASE_URL = os.environ.get('DATABASE_URL')

# ==========================================
# FUNCIONES AUXILIARES DE BASE DE DATOS
# ==========================================
def get_db():
    """Crea una conexión con la base de datos Neon en PostgreSQL."""
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    """Inicializa la estructura de las tablas en Neon e inserta datos iniciales si la BD está vacía."""
    conn = get_db()
    c = conn.cursor()
    
    # Crear tablas en PostgreSQL
    c.execute('''
        CREATE TABLE IF NOT EXISTS edificios (
            id SERIAL PRIMARY KEY, 
            nombre TEXT NOT NULL, 
            password_acceso TEXT NOT NULL, 
            color_tema TEXT NOT NULL
        );
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS documentos_pdf (
            id SERIAL PRIMARY KEY, 
            edificio_id INTEGER REFERENCES edificios(id) ON DELETE CASCADE, 
            archivo_pdf BYTEA
        );
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS administradores (
            id SERIAL PRIMARY KEY, 
            usuario TEXT UNIQUE NOT NULL, 
            password_hash TEXT NOT NULL
        );
    ''')
    
    # Verificar si la tabla edificios está vacía para poblar datos por primera vez
    c.execute('SELECT COUNT(*) FROM edificios;')
    if c.fetchone()[0] == 0:
        edificios = [
            ('Administración DIMA', 'dima2026', 'bg-green-500'),
            ('Villas San Fernando', 'villas2026', 'bg-blue-600'),
            ('Cerezas 76', 'cerezas2026', 'bg-teal-600'),
            ('Miguel Laurent 28', 'miguel2026', 'bg-gray-700')
        ]
        c.executemany('INSERT INTO edificios (nombre, password_acceso, color_tema) VALUES (%s, %s, %s)', edificios)
        c.execute('INSERT INTO administradores (usuario, password_hash) VALUES (%s, %s)', ('admin', generate_password_hash('admin123')))
    
    conn.commit()
    c.close()
    conn.close()

# ==========================================
# RUTAS DE FLASK
# ==========================================
@app.route('/')
def index():
    conn = get_db()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute('SELECT id, nombre, color_tema FROM edificios ORDER BY id ASC;')
    edificios = c.fetchall()
    c.close()
    conn.close()
    return render_template('index.html', edificios=edificios)

@app.route('/acceso/<int:edificio_id>', methods=['POST'])
def acceso_edificio(edificio_id):
    password = request.form['password']
    conn = get_db()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute('SELECT password_acceso FROM edificios WHERE id = %s;', (edificio_id,))
    edificio = c.fetchone()
    c.close()
    conn.close()
    
    if edificio and edificio['password_acceso'] == password:
        session[f'acceso_{edificio_id}'] = True
        return redirect(url_for('visor_pdf', edificio_id=edificio_id))
    else:
        flash('Contraseña incorrecta, intenta de nuevo.', 'error')
        return redirect(url_for('index'))

@app.route('/visor/<int:edificio_id>')
def visor_pdf(edificio_id):
    es_admin = session.get('admin_logged_in', False)
    tiene_acceso = session.get(f'acceso_{edificio_id}', False)
    
    if not (es_admin or tiene_acceso):
        flash('Por favor ingresa la contraseña de tu edificio para acceder.', 'error')
        return redirect(url_for('index'))
        
    conn = get_db()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute('SELECT id, nombre FROM edificios WHERE id = %s;', (edificio_id,))
    edificio = c.fetchone()
    
    c.execute('SELECT 1 FROM documentos_pdf WHERE edificio_id = %s;', (edificio_id,))
    pdf_existe = c.fetchone()
    
    c.close()
    conn.close()
    
    return render_template('visor.html', edificio=edificio, es_admin=es_admin, pdf_existe=bool(pdf_existe))

@app.route('/ver_archivo/<int:edificio_id>')
def ver_archivo(edificio_id):
    if not (session.get('admin_logged_in') or session.get(f'acceso_{edificio_id}')):
        return "Acceso denegado", 403
        
    conn = get_db()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute('SELECT archivo_pdf FROM documentos_pdf WHERE edificio_id = %s;', (edificio_id,))
    documento = c.fetchone()
    c.close()
    conn.close()
    
    if documento and documento['archivo_pdf']:
        pdf_data = bytes(documento['archivo_pdf'])
        return send_file(io.BytesIO(pdf_data), mimetype='application/pdf')
    return "No encontrado", 404

@app.route('/subir_pdf/<int:edificio_id>', methods=['POST'])
def subir_pdf(edificio_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('index'))
        
    archivo = request.files.get('documento_pdf')
    if archivo and archivo.filename.endswith('.pdf'):
        pdf_bytes = archivo.read()
        conn = get_db()
        c = conn.cursor(cursor_factory=RealDictCursor)
        
        c.execute('SELECT id FROM documentos_pdf WHERE edificio_id = %s;', (edificio_id,))
        existe = c.fetchone()
        
        if existe:
            c.execute('UPDATE documentos_pdf SET archivo_pdf = %s WHERE edificio_id = %s;', (psycopg2.Binary(pdf_bytes), edificio_id))
        else:
            c.execute('INSERT INTO documentos_pdf (edificio_id, archivo_pdf) VALUES (%s, %s);', (edificio_id, psycopg2.Binary(pdf_bytes)))
            
        conn.commit()
        c.close()
        conn.close()
        flash('Estado de cuenta subido y actualizado exitosamente en Neon.', 'success')
    else:
        flash('Por favor, selecciona un archivo PDF válido.', 'error')
        
    return redirect(url_for('visor_pdf', edificio_id=edificio_id))

@app.route('/eliminar_pdf/<int:edificio_id>', methods=['POST'])
def eliminar_pdf(edificio_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('index'))
        
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM documentos_pdf WHERE edificio_id = %s;', (edificio_id,))
    conn.commit()
    c.close()
    conn.close()
    
    flash('Estado de cuenta eliminado correctamente de Neon.', 'success')
    return redirect(url_for('visor_pdf', edificio_id=edificio_id))

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']
        
        conn = get_db()
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute('SELECT password_hash FROM administradores WHERE usuario = %s;', (usuario,))
        admin = c.fetchone()
        c.close()
        conn.close()
        
        if admin and check_password_hash(admin['password_hash'], password):
            session['admin_logged_in'] = True
            flash('Has iniciado sesión como administrador.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Credenciales incorrectas.', 'error')
            
    return render_template('admin_login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente.', 'success')
    return redirect(url_for('index'))

# Inicialización obligatoria para producción en Render
with app.app_context():
    init_db()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
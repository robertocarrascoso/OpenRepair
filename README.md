# OpenRepair

Gestión de taller de reparaciones **open-source y autohospedable**. Clientes, reparaciones con seguimiento de estado, presupuestos, precio final, historial, búsqueda, export CSV y resguardo en PDF.

Hecho con **Flask + MariaDB**. Se levanta con **un comando** gracias a Docker — sin montar servidores ni instalar nada más.

---

## Características

- Login con roles **admin / técnico** (sesiones, contraseñas con hash)
- Alta de reparaciones con código automático `REP-AÑO-NNNNN`
- Flujo de estados: `Recibido → Diagnosticado → Presupuesto → Reparando → Listo → Entregado`
- Ficha de cliente con historial y gasto total
- Dashboard con métricas (pendientes, ingresos del mes, tiempo medio)
- Búsqueda, filtros avanzados y paginación
- Exportación a **CSV** y resguardo en **PDF**

---

## Arranque rápido (Docker)

Requisito único: tener **Docker** instalado ([Docker Desktop](https://www.docker.com/products/docker-desktop/) en Windows/Mac, o `docker` + plugin compose en Linux).

```bash
git clone https://github.com/robertocarrascoso/OpenRepair.git
cd OpenRepair

cp .env.example .env          # edita SECRET_KEY y las contraseñas
docker compose up -d          # construye y levanta web + base de datos
```

Abre **http://localhost:8000**

### Cargar datos de demo (opcional)

Crea usuarios y reparaciones de ejemplo para probar:

```bash
docker compose exec web python base-de-datos/seed.py
```

Credenciales de demo:

| Rol     | Email                  | Contraseña   |
|---------|------------------------|--------------|
| admin   | `admin@openrepair.com`  | `admin123`   |
| técnico | `roberto@openrepair.com`| `tecnico123` |

> ⚠️ **Cámbialas antes de usar en producción.** El seed borra y recrea los datos cada vez que se ejecuta.

### Comandos útiles

```bash
docker compose logs -f web    # ver logs de la app
docker compose down           # parar (los datos persisten en el volumen)
docker compose down -v        # parar y BORRAR la base de datos
```

---

## Configuración

Todo se controla por variables de entorno en `.env` (ver `.env.example`):

| Variable           | Para qué sirve                          |
|--------------------|-----------------------------------------|
| `PORT`             | Puerto público de la web (def. 8000)    |
| `DB_NAME`          | Nombre de la base de datos              |
| `DB_USER` / `DB_PASSWORD` | Credenciales de la app a la DB   |
| `DB_ROOT_PASSWORD` | Contraseña root de MariaDB              |
| `SECRET_KEY`       | Clave de sesiones Flask (¡aleatoria!)   |

Genera una `SECRET_KEY` segura:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Cómo funciona el stack

- **web**: la app Flask servida con `gunicorn` (3 workers).
- **db**: MariaDB 11. El esquema `base-de-datos/schema.sql` se ejecuta automáticamente la primera vez que se crea la base de datos.
- Los datos viven en un volumen Docker (`db_data`) y persisten entre reinicios.

---

## Desplegar sin máquina propia (PaaS)

El `Dockerfile` funciona tal cual en plataformas como **Render**, **Railway** o **Fly.io**:
conecta este repo de GitHub, añade una base de datos MySQL/MariaDB gestionada y define las
variables de entorno (`DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `SECRET_KEY`).

---

## Desarrollo local (sin Docker)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # apunta DB_HOST a tu MySQL/MariaDB local
python app.py                 # servidor de desarrollo en http://localhost:5000
```

---

## Licencia

MIT

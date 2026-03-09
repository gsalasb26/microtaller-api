# MicroTaller API

Sistema de gestión de órdenes de trabajo para talleres mecánicos.  
Construido con **FastAPI + PostgreSQL + Docker**, diseñado para correr en un VPS o en local con un comando.

---

## Quick Start

> Requisitos previos: **Docker Desktop** en ejecución, **PowerShell 7+**, **Python 3.12+** con `venv`.

```powershell
# 1. Clonar el repositorio
git clone https://github.com/TU_USUARIO/microtaller.git
cd microtaller

# 2. Crear el archivo de variables de entorno
cp backend/.env.example backend/.env
#    → Editar backend/.env con tus credenciales de BD

# 3. Levantar la base de datos y activar el entorno
.\start.ps1

# 4. Aplicar migraciones
cd backend
alembic upgrade head

# 5. (Opcional) Poblar con datos iniciales
python -m app.seed_data

# 6. Iniciar el servidor de desarrollo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

La API queda disponible en `http://localhost:8000`.  
Documentación interactiva: `http://localhost:8000/docs`.

---

Este proyecto utiliza un "Toolbelt" de PowerShell para estandarizar las tareas comunes. Los scripts se encuentran en la raíz y en la carpeta `/backend`.

## 🚀 Comandos Rápidos (PowerShell Aliases)
Si trabajas frecuentemente en este equipo, se recomienda configurar los siguientes aliases en tu `$PROFILE`:

| Comando | Script Destino | Propósito |
| :--- | :--- | :--- |
| `tstart` | `start.ps1` | Levanta Docker (DB) e inicia el servidor FastAPI. |
| `tdb` | `upgrade_model.ps1` | Sincroniza cambios en modelos de Python con la DB. |
| `tsync` | `sync_git.ps1` | Limpia, indexa, commitea y sube cambios a GitHub. |
---

## Stack Tecnológico

| Capa | Tecnología | Versión |
|---|---|---|
| Lenguaje | Python | 3.12+ |
| Framework web | FastAPI | 0.115.6 |
| Servidor ASGI | Uvicorn (standard) | 0.32.1 |
| ORM (async) | SQLAlchemy | 2.0.36 |
| Driver PostgreSQL | asyncpg | 0.30.0 |
| Migraciones | Alembic | 1.14.1 |
| Validación / Esquemas | Pydantic v2 | 2.10.3 |
| Configuración (.env) | pydantic-settings | 2.7.0 |
| Base de datos | PostgreSQL | 15+ |
| Contenedores | Docker + Docker Compose | — |

---

## Estructura del Repositorio

```
microtaller/
├── README.md
├── CONTEXTO.md               ← Documentación técnica completa (para el equipo y la IA)
├── .gitignore
├── start.ps1                 ← Inicio rápido
├── sync_git.ps1              ← Sync con GitHub
├── backend/
│   ├── upgrade_model.ps1     ← Migraciones automáticas
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/         ← Archivos de migración versionados
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── seed_data.py      ← Datos iniciales (idempotente)
│       ├── models/
│       ├── schemas/
│       └── routers/
└── docker/
    └── docker-compose.yml
```

---

## Variables de Entorno

Copia `backend/.env.example` como `backend/.env` y ajusta los valores:

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_USER=microtaller
DB_PASSWORD=tu_password_seguro
DB_NAME=microtaller_db

DEBUG=false
SEED_ON_STARTUP=false
```

> `SEED_ON_STARTUP=true` ejecuta `seed_data.py` automáticamente al arrancar la API.  
> `DEBUG=true` habilita el endpoint `POST /seed` en Swagger UI.

---

## Endpoints Principales

| Recurso | Ruta base | Operaciones |
|---|---|---|
| Clientes | `/api/v1/customers` | CRUD completo |
| Vehículos | `/api/v1/vehicles` | CRUD completo |
| Tipos de Vehículo | `/api/v1/vehicle-types` | CRUD completo |
| Monedas | `/api/v1/currencies` | CRUD completo |
| Órdenes de Trabajo | `/api/v1/work-orders` | CRUD + gestión de ítems |
| Health | `/health` | Estado del servicio |
| Seed (solo DEBUG) | `/seed` | Poblar BD con datos iniciales |

---

## Licencia

Uso interno — todos los derechos reservados.

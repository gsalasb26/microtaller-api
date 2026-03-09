# CONTEXTO.md — Documentación Técnica: MicroTaller API

> Versión del documento: 3.0 · Fecha: 2026-03-08  
> Actualizado para reflejar el **Motor de Órdenes de Trabajo (OT)**: módulo Reception, flujo SAP-style con atomicidad de estados, descuentos por línea y validación E2E via TestClient.

---

## 1. Visión General

**MicroTaller** es un sistema de gestión de órdenes de trabajo para talleres mecánicos pequeños. Expone una API REST que permite administrar clientes, vehículos y órdenes de trabajo (con sus líneas de detalle).

| Atributo | Valor |
|---|---|
| Nombre del servicio | `MicroTaller API` |
| Versión del servicio | `1.0.0` |
| Puerto HTTP | `8000` |
| Base de datos | PostgreSQL |
| Prefijo de rutas | `/api/v1` |
| Documentación interactiva | `/docs` (Swagger UI) · `/redoc` |

---

## 2. Stack Tecnológico

| Capa | Tecnología | Versión |
|---|---|---|
| Framework web | FastAPI | 0.115.6 |
| Servidor ASGI | Uvicorn (standard) | 0.32.1 |
| ORM (async) | SQLAlchemy | 2.0.36 |
| Driver PostgreSQL | asyncpg | 0.30.0 |
| Migraciones | Alembic | 1.14.1 |
| Validación / Esquemas | Pydantic v2 | 2.10.3 |
| Configuración (.env) | pydantic-settings | 2.7.0 |
| Runtime | Python | 3.12 |
| Contenedores | Docker + Docker Compose | — |

---

## 3. Estructura del Proyecto

```
microtaller/
├── README.md                     # Contrato público: Quick Start, Toolbelt, Stack
├── CONTEXTO.md                   # Este archivo: cerebro técnico del proyecto
├── .gitignore
├── start.ps1                     # Inicio rápido: Docker + venv
├── sync_git.ps1                  # Sync automático con GitHub
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini               # Configuración de Alembic
│   ├── upgrade_model.ps1         # Script de migración automatizada
│   ├── alembic.ini               # Configuración de Alembic
│   ├── alembic/
│   │   ├── env.py                # Config async + carga de modelos
│   │   ├── script.py.mako        # Plantilla de scripts de migración
│   │   ├── README                # Referencia rápida de comandos
│   │   └── versions/             # Archivos de migración generados
│   ├── app/
│   │   ├── main.py               # Punto de entrada FastAPI, lifespan, CORS, routers
│   │   ├── config.py             # Settings (pydantic-settings, .env) · SEED_ON_STARTUP
│   │   ├── database.py           # Motor async, sesión, Base declarativa
│   │   ├── seed_data.py          # Datos iniciales idempotentes (CRC, USD, tipos, clientes)
│   │   ├── models/               # Modelos SQLAlchemy (ORM)
│   │   │   ├── currency.py
│   │   │   ├── customer.py
│   │   │   ├── reception.py       # Boleta de ingreso de vehículo
│   │   │   ├── reception_detail.py # Líneas de trabajo solicitadas
│   │   │   ├── vehicle.py
│   │   │   ├── vehicle_type.py
│   │   │   ├── work_order.py      # OT financiera (WorkOrder + WorkOrderLine)
│   │   │   └── work_type.py       # Catálogo de tipos de trabajo
│   │   ├── schemas/              # Schemas Pydantic (request / response)
│   │   │   ├── currency.py
│   │   │   ├── customer.py
│   │   │   ├── reception.py
│   │   │   ├── reception_detail.py
│   │   │   ├── vehicle.py
│   │   │   ├── vehicle_type.py
│   │   │   ├── work_order.py
│   │   │   └── work_type.py
│   │   ├── routers/              # Endpoints FastAPI
│   │   │   ├── currencies.py
│   │   │   ├── customers.py
│   │   │   ├── reception_details.py
│   │   │   ├── receptions.py
│   │   │   ├── vehicle_types.py
│   │   │   ├── vehicles.py
│   │   │   ├── work_orders.py
│   │   │   └── work_types.py
│   │   └── seeds/                # Scripts de validación y carga de datos
│   │       └── test_sap_flow.py  # Validación E2E del flujo SAP completo
│   └── sql/
│       └── add_foreign_keys.sql  # Script idempotente para FK en BD
└── docker/
    └── docker-compose.yml
```

---

## 4. Arquitectura

El proyecto sigue una **arquitectura en capas** (Layered Architecture) sin capa de servicio explícita; la lógica de negocio reside directamente en los routers.

```
┌─────────────────────────────────────────┐
│              Cliente HTTP               │
└────────────────────┬────────────────────┘
                     │
┌────────────────────▼────────────────────┐
│           Routers (FastAPI)             │  /api/v1/*
│  currencies · customers · vehicle_types │
│  vehicles · work_orders                 │
└────────┬───────────────────┬────────────┘
         │                   │
┌────────▼────────┐ ┌────────▼────────────┐
│ Schemas Pydantic│ │  Modelos SQLAlchemy  │
│  (validación)   │ │  (dominio / tablas)  │
└─────────────────┘ └────────┬────────────┘
                             │
                    ┌────────▼────────────┐
                    │  AsyncSession (DB)  │
                    │  PostgreSQL via     │
                    │  asyncpg            │
                    └─────────────────────┘
```

### Patrones aplicados

| Patrón | Dónde |
|---|---|
| Dependency Injection | `Depends(get_db)` en todos los endpoints |
| Repository implícito | SQLAlchemy Session actúa como Unit of Work |
| DTO (Data Transfer Object) | Schemas Pydantic separados de los modelos ORM |
| State Machine | `OrderStatus` con transiciones controladas |
| Lifespan events | Verificación de DB al arranque, cierre limpio del pool |

---

## 5. Configuración y Variables de Entorno

Gestionadas en `app/config.py` mediante **pydantic-settings**. Se leen desde un archivo `.env` o directamente como variables de entorno.

| Variable | Descripción | Valor defecto |
|---|---|---|
| `APP_NAME` | Nombre del servicio | `MicroTaller API` |
| `APP_VERSION` | Versión semántica | `1.0.0` |
| `DEBUG` | Activa `echo=True` en SQLAlchemy | `false` |
| `DB_HOST` | Host de PostgreSQL | `localhost` |
| `DB_PORT` | Puerto de PostgreSQL | `5432` |
| `DB_NAME` | Nombre de la base de datos | `microtaller` |
| `DB_USER` | Usuario de la base de datos | `microtaller` |
| `DB_PASSWORD` | Contraseña | `microtaller` |

La URL de conexión se construye dinámicamente como propiedad:
```
postgresql+asyncpg://<DB_USER>:<DB_PASSWORD>@<DB_HOST>:<DB_PORT>/<DB_NAME>
```

---

## 6. Base de Datos

### 6.1 Modelo de Datos (Entidad–Relación)

```
currencies
  ├── id      UUID  PK
  ├── name    VARCHAR(80)  NOT NULL  UNIQUE  INDEX
  ├── code    VARCHAR(3)   NOT NULL  UNIQUE  INDEX  (ej: USD, CRC, EUR)
  └── symbol  VARCHAR(5)   NOT NULL

customers
  ├── id            UUID  PK
  ├── name          VARCHAR(100)  NOT NULL  INDEX
  ├── phone         VARCHAR(20)   NOT NULL
  ├── email         VARCHAR(150)  NULLABLE
  ├── notes         TEXT          NULLABLE
  └── created_at    TIMESTAMPTZ   DEFAULT now()

vehicle_types
  ├── id    UUID  PK
  └── name  VARCHAR(80)  NOT NULL  UNIQUE  INDEX  (ej: Sedan, SUV, Pickup)

vehicles
  ├── id               UUID  PK
  ├── customer_id      UUID  FK → customers.id      ON DELETE RESTRICT  INDEX
  ├── vehicle_type_id  UUID  FK → vehicle_types.id  ON DELETE SET NULL   INDEX  NULLABLE
  ├── brand            VARCHAR(80)   NOT NULL
  ├── model            VARCHAR(80)   NOT NULL
  ├── year             INTEGER       NOT NULL
  ├── plate            VARCHAR(20)   UNIQUE NOT NULL  INDEX
  └── created_at       TIMESTAMPTZ   DEFAULT now()

work_types
  ├── id          UUID  PK
  ├── name        VARCHAR(100)  NOT NULL  UNIQUE  INDEX
  └── description TEXT          NULLABLE

receptions                         ← «Boleta de Ingreso»
  ├── id               UUID  PK
  ├── customer_id      UUID  FK → customers.id   ON DELETE RESTRICT  INDEX
  ├── vehicle_id       UUID  FK → vehicles.id    ON DELETE RESTRICT  INDEX
  ├── work_type_id     UUID  FK → work_types.id  ON DELETE SET NULL   INDEX  NULLABLE
  ├── current_status   ENUM(reception_status)  NOT NULL  DEFAULT 'NEW'  INDEX
  ├── reported_problem TEXT        NULLABLE
  ├── received_by      VARCHAR(100) NOT NULL
  ├── mileage          INTEGER      NULLABLE
  ├── fuel_level       ENUM(fuel_level) NULLABLE
  ├── vin_number       VARCHAR(50)  NULLABLE
  └── created_at       TIMESTAMPTZ  DEFAULT now()

reception_details                  ← «Líneas de trabajo solicitado»
  ├── id             UUID  PK
  ├── reception_id   UUID  FK → receptions.id  ON DELETE CASCADE   INDEX
  ├── work_type_id   UUID  FK → work_types.id  ON DELETE SET NULL   INDEX  NULLABLE
  ├── description    VARCHAR(255)  NOT NULL
  └── work_date      TIMESTAMPTZ   NULLABLE

work_orders                        ← «Orden de Trabajo Financiera»
  ├── id             UUID  PK
  ├── reception_id   UUID  FK → receptions.id  ON DELETE RESTRICT  INDEX  UNIQUE
  ├── currency_id    UUID  FK → currencies.id  ON DELETE RESTRICT  INDEX
  ├── order_number   VARCHAR(20)   NOT NULL  UNIQUE  INDEX  (ej: OT-1001)
  ├── status         ENUM(work_order_status)  NOT NULL  DEFAULT 'DRAFT'  INDEX
  ├── notes          TEXT          NULLABLE
  ├── total_labor    NUMERIC(12,2) NOT NULL  DEFAULT 0
  ├── total_parts    NUMERIC(12,2) NOT NULL  DEFAULT 0
  ├── tax_amount     NUMERIC(12,2) NOT NULL  DEFAULT 0
  ├── total_final    NUMERIC(12,2) NOT NULL  DEFAULT 0
  ├── created_at     TIMESTAMPTZ   DEFAULT now()
  └── updated_at     TIMESTAMPTZ   NULLABLE

work_order_lines                   ← «Líneas de la OT (mano de obra y repuestos)»
  ├── id                    UUID  PK
  ├── work_order_id         UUID  FK → work_orders.id      ON DELETE CASCADE   INDEX
  ├── reception_detail_id   UUID  FK → reception_details.id ON DELETE SET NULL  INDEX  NULLABLE
  ├── description           VARCHAR(255)  NOT NULL
  ├── quantity              NUMERIC(10,3) NOT NULL  CHECK > 0
  ├── unit_price            NUMERIC(10,2) NOT NULL  CHECK >= 0
  ├── discount_percentage   NUMERIC(5,2)  NOT NULL  DEFAULT 0.00  (0–100)
  ├── subtotal              NUMERIC(12,2) NOT NULL  CHECK >= 0
  └── is_part               BOOLEAN       NOT NULL  DEFAULT false
```

### 6.2 Relaciones

| Relación | Cardinalidad | Eliminación |
|---|---|---|
| Customer → Vehicle | 1 : N | RESTRICT (no se puede eliminar un cliente con vehículos) |
| Customer → Reception | 1 : N | RESTRICT |
| VehicleType → Vehicle | 1 : N | SET NULL |
| Vehicle → Reception | 1 : N | RESTRICT |
| WorkType → Reception | 1 : N | SET NULL |
| WorkType → ReceptionDetail | 1 : N | SET NULL |
| Reception → ReceptionDetail | 1 : N | CASCADE (los detalles pertenecen a la boleta) |
| Reception → WorkOrder | **1 : 1** | RESTRICT (la OT referencia una sola boleta) |
| WorkOrder → WorkOrderLine | 1 : N | CASCADE (al borrar la OT se borran sus líneas) |
| WorkOrderLine → ReceptionDetail | N : 1 | SET NULL (línea puede existir sin detalle de boleta) |
| Currency → WorkOrder | 1 : N | RESTRICT (no se puede borrar una moneda en uso) |

### 6.3 Connection Pool

Configurado en `app/database.py`:

| Parámetro | Valor |
|---|---|
| `pool_size` | 10 |
| `max_overflow` | 20 |
| `pool_pre_ping` | `True` (valida conexiones antes de usar) |
| `expire_on_commit` | `False` |
| `autoflush` | `False` |

---

## 7. Dominio y Lógica de Negocio

### 7.1 Máquina de Estados — `ReceptionStatus` (Boleta de Ingreso)

La boleta de ingreso del vehículo sigue su propio ciclo de vida:

```
  ┌─────────┐    manual PATCH     ┌─────────────┐    POST /process    ┌──────────┐
  │   NEW   │ ─────────────────►  │ IN_PROGRESS │ ──────────────────► │ FINISHED │
  └─────────┘                     └──────┬──────┘                     └──────────┘
                                         ▲                                  │
                                         │         PATCH /cancel            │
                                         └──────────────────────────────────┘
```

| Transición | Disparador | Observación |
|---|---|---|
| `NEW` → `IN_PROGRESS` | `PATCH /receptions/{id}/status?new_status=IN_PROGRESS` | Manual por el taller |
| `IN_PROGRESS` → `FINISHED` | `POST /work-orders/process` | **Automático y atómico** al generar la OT |
| `FINISHED` → `IN_PROGRESS` | `PATCH /work-orders/{id}/cancel` | **Reversión automática** al cancelar la OT |

### 7.2 Máquina de Estados — `WorkOrderStatus` (Orden de Trabajo)

```
  ┌───────┐    POST /process    ┌──────┐    PATCH /status    ┌──────────┐    PATCH /status    ┌──────────┐
  │ DRAFT │ ──────────────────► │ SENT │ ─────────────────►  │ APPROVED │ ─────────────────►  │ INVOICED │
  └───────┘                     └──────┘                     └──────────┘                     └──────────┘
       └──────────────────────────────────────────────────────────────────────────────────────────┐
                                        PATCH /cancel                                             ▼
                                                                                           ┌───────────┐
                                                                                           │ CANCELLED │ ← TERMINAL
                                                                                           └───────────┘
```

Transiciones válidas definidas en `WORK_ORDER_TRANSITIONS`:

| Desde | Hacia | Endpoint |
|---|---|---|
| `DRAFT` | `SENT` | `PATCH /work-orders/{id}/status?requested=SENT` |
| `SENT` | `APPROVED` | `PATCH /work-orders/{id}/status?requested=APPROVED` |
| `APPROVED` | `INVOICED` | `PATCH /work-orders/{id}/status?requested=INVOICED` |
| Cualquiera (excepto `INVOICED`) | `CANCELLED` | `PATCH /work-orders/{id}/cancel` |

### 7.3 Flujo SAP-Style — Atomicidad y Reversibilidad

El diseño garantiza consistencia entre la boleta y la OT en una sola transacción de base de datos:

#### Generar OT (`POST /work-orders/process`)
1. Valida que la `Reception` esté en estado `NEW` o `IN_PROGRESS` (HTTP 400 si no).
2. Crea el `WorkOrder` con sus `WorkOrderLine` (mano de obra + repuestos extra).
3. Calcula y persiste `total_labor`, `total_parts`, `tax_amount`, `total_final`.
4. Marca la `Reception` como `FINISHED` en el mismo `db.flush()`.
5. Hace `commit()` — ambas escrituras son atómicas.

#### Cancelar OT (`PATCH /work-orders/{id}/cancel`)
1. Valida que el `WorkOrder` no esté en estado `INVOICED`.
2. Cambia el estado del `WorkOrder` a `CANCELLED`.
3. Revierte la `Reception` a `IN_PROGRESS` en el mismo `db.flush()`.
4. Hace `commit()` — ambas escrituras son atómicas.

### 7.4 Motor de Cálculo Financiero

Cada `WorkOrderLine` incorpora descuento por línea. El subtotal se calcula como:

$$subtotal = quantity \times unit\_price \times \left(1 - \frac{discount\_percentage}{100}\right)$$

Redondeado a `Decimal("0.01")` con política `ROUND_HALF_UP`.

Los totales de la OT se calculan discriminando tipo de línea (`is_part`):

| Campo | Fórmula |
|---|---|
| `total_labor` | $\sum subtotal$ donde `is_part = false` |
| `total_parts` | $\sum subtotal$ donde `is_part = true` |
| `tax_amount` | $(total\_labor + total\_parts) \times tax\_rate$ (default `0.13`) |
| `total_final` | $total\_labor + total\_parts + tax\_amount$ |

> ⚠️ **Nota de implementación:** el `tax_amount` se calcula y almacena en el momento de la creación de la OT. Un IVA variable por moneda o exenciones por tipo de servicio está identificado como próximo paso (ver §13).

### 7.5 Composición de Líneas de una OT

| Tipo de línea | Origen | `is_part` | `reception_detail_id` |
|---|---|---|---|
| Mano de obra (labor) | `LaborItemCreate` — descripción tomada de `ReceptionDetail` | `false` | Requerido |
| Repuesto / extra | `WorkOrderLineCreate` — descripción libre | `true` | `null` |

---

## 8. API REST — Endpoints

Todos bajo el prefijo `/api/v1`.

### 8.1 Customers

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/customers` | Listar clientes (paginado: `skip`, `limit`) |
| `GET` | `/customers/search?q=` | Búsqueda case-insensitive en nombre, teléfono y email |
| `GET` | `/customers/{id}` | Obtener cliente por ID |
| `POST` | `/customers` | Crear cliente → 201 |
| `PATCH` | `/customers/{id}` | Actualización parcial |
| `DELETE` | `/customers/{id}` | Eliminar → 204 |

### 8.2 Vehicles

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/vehicles` | Listar vehículos (paginado; filtro opcional `customer_id`) |
| `GET` | `/vehicles/by-plate/{plate}` | Búsqueda por placa (case-insensitive, exacta) |
| `GET` | `/vehicles/{id}` | Obtener vehículo por ID |
| `POST` | `/vehicles` | Crear vehículo → 201 (409 si placa duplicada) |
| `PATCH` | `/vehicles/{id}` | Actualización parcial (valida placa única) |
| `DELETE` | `/vehicles/{id}` | Eliminar → 204 |

### 8.3 Receptions (Boletas de Ingreso)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/receptions` | Listar boletas (paginado; filtros `vehicle_id`, `status`) |
| `GET` | `/receptions/{id}` | Obtener boleta por ID |
| `POST` | `/receptions` | Crear boleta → 201 (estado inicial `NEW`) |
| `PATCH` | `/receptions/{id}` | Actualizar campos opcionales |
| `PATCH` | `/receptions/{id}/status?new_status=` | Avanzar estado manualmente |
| `DELETE` | `/receptions/{id}` | Eliminar → 204 |

### 8.4 Reception Details (Líneas de Trabajo Solicitado)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/reception-details?reception_id=` | Listar detalles de una boleta |
| `GET` | `/reception-details/{id}` | Obtener detalle por ID |
| `POST` | `/reception-details` | Crear línea de trabajo → 201 |
| `PATCH` | `/reception-details/{id}` | Actualización parcial |
| `DELETE` | `/reception-details/{id}` | Eliminar → 204 |

### 8.5 Work Orders (Órdenes de Trabajo Financieras)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/work-orders` | Listar OTs (paginado; filtros `status`) |
| `GET` | `/work-orders/{id}` | Obtener OT por ID |
| `POST` | `/work-orders/process` | **Generar OT** desde boleta → 201; marca boleta `FINISHED` |
| `PATCH` | `/work-orders/{id}/status?requested=` | Avanzar estado (SENT / APPROVED / INVOICED) |
| `PATCH` | `/work-orders/{id}/cancel` | **Cancelar OT**; revierte boleta a `IN_PROGRESS` |

#### Payload `POST /work-orders/process`

```json
{
  "reception_id": "<uuid>",
  "currency_id":  "<uuid>",
  "tax_rate":     0.13,
  "notes":        "Texto libre",
  "labor_items": [
    { "reception_detail_id": "<uuid>", "quantity": 1.0, "unit_price": 35.00, "discount_percentage": 10.0 }
  ],
  "extra_lines": [
    { "description": "Aceite Mobil 1L x5", "quantity": 5.0, "unit_price": 8.50, "is_part": true, "discount_percentage": 0.0 }
  ]
}
```

### 8.6 Work Types (Catálogo)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/work-types` | Listar tipos de trabajo |
| `GET` | `/work-types/{id}` | Obtener por ID |
| `POST` | `/work-types` | Crear → 201 (409 si nombre duplicado) |
| `PATCH` | `/work-types/{id}` | Actualización parcial |
| `DELETE` | `/work-types/{id}` | Eliminar → 204 |

### 8.7 Vehicle Types

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/vehicle-types` | Listar tipos de vehículo |
| `GET` | `/vehicle-types/{id}` | Obtener tipo por ID |
| `POST` | `/vehicle-types` | Crear tipo → 201 (409 si nombre duplicado) |
| `PATCH` | `/vehicle-types/{id}` | Actualización parcial |
| `DELETE` | `/vehicle-types/{id}` | Eliminar → 204 |

### 8.8 Currencies

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/currencies` | Listar monedas ordenadas por código ISO |
| `GET` | `/currencies/{id}` | Obtener moneda por ID |
| `POST` | `/currencies` | Crear moneda → 201 (409 si code o name duplicado) |
| `PATCH` | `/currencies/{id}` | Actualización parcial |
| `DELETE` | `/currencies/{id}` | Eliminar → 204 |

### 8.9 Salud

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Health check (nombre y versión del servicio) |

---

## 9. Schemas Pydantic

Cada entidad tiene un conjunto de schemas independientes siguiendo el patrón `Base / Create / Update / Response`:

| Schema | Propósito |
|---|---|
| `*Base` | Campos compartidos entre creación y lectura |
| `*Create` | Payload de entrada para `POST` |
| `*Update` | Payload parcial para `PATCH` (todos los campos opcionales) |
| `*Response` | Salida serializada con `from_attributes = True` |
| `*List` | Envolvente paginada `{ total, items[] }` |

**Notas relevantes:**
- `CustomerCreate` valida `email` como `EmailStr`.
- `VehicleCreate` incluye `vehicle_type_id: UUID | None` (opcional).
- `VehicleCreate` restringe `year` al rango `[1900, 2100]`.
- `VehicleResponse` embebe el objeto `VehicleTypeResponse` completo cuando existe.
- `CurrencyCreate` valida `code` con exactamente 3 caracteres (ISO-4217).
- `WorkOrderItemBase` incluye `currency_id: UUID | None` (opcional).
- `WorkOrderResponse.total` es un `@computed_field` derivado de la suma de ítems.
- `WorkOrderUpdate` **no** expone directamente una transición libre de estados; eso se delega al endpoint `/close`.

---

## 10. Infraestructura y Despliegue

### 10.1 Scripts de automatización

| Script | Ubicación | Propósito |
|---|---|---|
| `start.ps1` | raíz del proyecto | Levanta Docker y activa el venv |
| `upgrade_model.ps1` | `backend/` | Genera y aplica una migración de Alembic en un paso |

**`upgrade_model.ps1`** acepta un parámetro de mensaje opcional:
```powershell
# Con mensaje personalizado
.\upgrade_model.ps1 "add_service_notes"

# Sin parámetro — genera auto_migration_YYYYMMDD_HHMM
.\upgrade_model.ps1
```

### 10.2 Dockerfile

```
Base:    python:3.12-slim
WorkDir: /app
Cmd:     uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

El código de la aplicación se copia desde `backend/app`. El modo `--reload` está activo por defecto (adecuado para desarrollo; debe desactivarse en producción).

### 10.3 Docker Compose (`docker/docker-compose.yml`)

| Servicio | Contenedor | Puerto |
|---|---|---|
| `api` | `microtaller_api` | `8000:8000` |

El volumen `../backend/app:/app/app` permite recarga en caliente. La BD corre fuera del Compose (en el host), accedida mediante `host.docker.internal`.

Variables de entorno inyectadas: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DEBUG`.

### 10.4 Migraciones Alembic

Configuradas en `backend/alembic/`. El `env.py` importa todos los modelos y lee la URL de `app/config.py` para garantizar consistencia con la aplicación.

**Flujo estándar:**
```powershell
cd backend
# Opción A — script automatizado (recomendado)
.\upgrade_model.ps1 "descripcion_del_cambio"

# Opción B — manual
alembic revision --autogenerate -m "descripcion_del_cambio"
alembic upgrade head
```

**Reglas críticas para migraciones con ENUMs PostgreSQL:**
1. Crear el tipo con `op.execute(sa.text("CREATE TYPE ..."))` antes de cualquier `ALTER COLUMN`.
2. Eliminar el `DEFAULT` de la columna antes de cambiar el tipo.
3. Usar `USING status::order_status` en el `ALTER COLUMN TYPE`.
4. Restaurar el `DEFAULT` después del cambio.
5. En `downgrade()`, hacer el proceso inverso y terminar con `DROP TYPE`.

### 10.5 Script SQL (`sql/add_foreign_keys.sql`)

Script **idempotente** para añadir las FK que SQLAlchemy podría no haber creado automáticamente (p.ej. después de un `CREATE TABLE` manual). Usa bloques `DO $$ BEGIN IF NOT EXISTS ... END $$` para cada constraint.

| Constraint | Tabla origen | Tabla destino | On Delete |
|---|---|---|---|
| `fk_vehicles_customer_id` | `vehicles` | `customers` | RESTRICT |
| `fk_work_orders_vehicle_id` | `work_orders` | `vehicles` | RESTRICT |
| `fk_work_order_items_work_order_id` | `work_order_items` | `work_orders` | CASCADE |
| `fk_work_orders_customer_id` | `work_orders` | `customers` | RESTRICT |

---

## 11. CORS

Configurado con política abierta (desarrollo):

```python
allow_origins=["*"]
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```

> ⚠️ Para producción debe restringirse `allow_origins` a los dominios autorizados.

---

## 12. Decisiones de Diseño Relevantes

| Decisión | Razonamiento |
|---|---|
| UUIDs como PK | Evita enumeración de recursos y facilita distribución |
| asyncpg + SQLAlchemy async | I/O no bloqueante; adecuado para un servidor ASGI |
| `expire_on_commit=False` | Permite acceder a los objetos ORM después del commit sin nueva consulta |
| `autoflush=False` | Control explícito del flush; evita side-effects inesperados |
| Total calculado (no almacenado) | Evita inconsistencias entre `quantity * unit_price` y `total` |
| `ondelete="RESTRICT"` en Customer→Vehicle y Vehicle→WorkOrder | Integridad referencial; impide borrado accidental en cascada |
| `ondelete="CASCADE"` en WorkOrder→Line | Las líneas son parte de la OT; no tienen sentido sin ella |
| `ROUND_HALF_UP` | Comportamiento de redondeo contable estándar |
| Índices compuestos en `work_orders` | Optimizan las consultas más frecuentes: por recepción y por estado |
| Relación 1:1 Reception → WorkOrder | Una boleta solo puede tener una OT activa; garantiza integridad del flujo de caja |
| `discount_percentage` en `WorkOrderLine` | Descuento negociado por ítem; no afecta al precio catálogo registrado en `ReceptionDetail` |
| Totales almacenados en `WorkOrder` | A diferencia del subtotal de ítem, los totales de la OT se persisten para auditoría histórica (precio puede cambiar) |
| `tax_rate` como parámetro de entrada | Permite adaptar el IVA por país o tipo de servicio sin cambiar código |

---

## 13. Estado Actual del Backend y Próximos Pasos

### 13.1 Estado Actual

| Componente | Estado | Detalle |
|---|---|---|
| Motor de Órdenes de Trabajo (OT) | ✅ Implementado | Módulo completo: Reception, ReceptionDetail, WorkOrder, WorkOrderLine |
| Flujo SAP-style (atomicidad) | ✅ Implementado | `POST /process` y `PATCH /cancel` transicionan Reception y WorkOrder atómicamente |
| Descuentos por línea | ✅ Implementado | `discount_percentage` en `WorkOrderLine`; fórmula `qty × price × (1 − disc/100)` |
| Multi-moneda | ✅ Implementado | `WorkOrder.currency_id` FK a `currencies`; soporte CRC y USD en seed |
| Cálculo de totales discriminado | ✅ Implementado | `total_labor`, `total_parts`, `tax_amount`, `total_final` persistidos en OT |
| Validación E2E via TestClient | ✅ Implementado | `seeds/test_sap_flow.py` — httpx + ASGITransport; valida 4 pasos + 9 asserts |
| Migraciones Alembic | ✅ Aplicadas | Head: `5d8ce4790a41` (add_discount_percentage_to_work_order_lines) |
| Capa de servicio | ⚠️ Pendiente | Lógica de negocio en routers; extraer capa `services/` para testabilidad |
| Tests unitarios formales | ⚠️ Pendiente | No existe `tests/`; `test_sap_flow.py` es integración, no pytest formal |
| Autenticación | ⚠️ Pendiente | Sin JWT / API Key; bloqueante para producción |
| CORS en producción | ⚠️ Pendiente | Política wildcard; restringir `allow_origins` antes de deploy |
| Logging estructurado | ⚠️ Pendiente | Solo `print()` en lifespan; migrar a `structlog` o `logging` |
| Health check de BD | ⚠️ Pendiente | `/health` no verifica conectividad real a la DB |

### 13.2 Próximos Pasos (Backlog Priorizado)

| Prioridad | Tarea | Descripción |
|---|---|---|
| 🔴 Alta | **IVA configurable** | Soporte de exenciones por tipo de servicio (mano de obra vs repuesto); tabla `tax_rates` o campo en `WorkType` |
| 🔴 Alta | **Vistas de Frontend — Liquidación de OT** | Pantallas para generar, revisar y aprobar OTs; mostrar desglose labor/repuestos/IVA/total |
| 🟡 Media | **PDF de OT** | Generar documento imprimible de la orden de trabajo (WeasyPrint o similar) |
| 🟡 Media | **Historial de estados** | Tabla `work_order_status_log` con timestamp + usuario por cada transición |
| 🟢 Baja | **Autenticación JWT** | Proteger todos los endpoints; roles: `admin`, `técnico`, `recepcionista` |
| 🟢 Baja | **Capa `services/`** | Refactorizar lógica de negocio de routers a servicios para mejorar testabilidad |

---

## 14. Glosario

| Término | Definición |
|---|---|
| **Reception** | Boleta de ingreso de un vehículo al taller; registra estado, millaje, problema reportado |
| **ReceptionDetail** | Línea de trabajo solicitado dentro de una boleta (descripción del servicio a realizar) |
| **WorkOrder** | Orden de trabajo financiera; vinculada 1:1 a una Reception; contiene totales y moneda |
| **WorkOrderLine** | Línea de detalle de una OT: mano de obra (heredada de ReceptionDetail) o repuesto extra |
| **WorkType** | Catálogo de tipos de trabajo o servicio (Mantenimiento, Diagnóstico, Latonería…) |
| **is_part** | Bandera booleana en `WorkOrderLine`; `true` = repuesto, `false` = mano de obra |
| **discount_percentage** | Descuento por línea de OT (0–100 %); afecta el subtotal sin modificar el precio unitario |
| **LaborItemCreate** | Schema de entrada para líneas de mano de obra al procesar una OT |
| **NEW** | Estado inicial de una Reception: vehículo ingresado, aún no evaluado |
| **IN_PROGRESS** | Trabajo en ejecución en la Reception |
| **FINISHED** | Reception con OT generada (estado establecido automáticamente por `POST /process`) |
| **DRAFT** | Estado inicial de una WorkOrder recién creada |
| **CANCELLED** | WorkOrder cancelada; la Reception asociada vuelve a `IN_PROGRESS` |
| **SAP-Style Flow** | Término interno para el patrón de atomicidad: generar/cancelar OT modifica Reception en la misma transacción |
| **ASGITransport** | Transporte de httpx que inyecta la app ASGI directamente sin levantar sockets; usado en `test_sap_flow.py` |
| **Lifespan** | Hook de FastAPI para inicialización y limpieza al arrancar/detener la app |
| **AsyncSession** | Sesión de SQLAlchemy que opera de forma no bloqueante con `asyncio` |
| **Currency** | Moneda ISO-4217 associated a una WorkOrder (ej: CRC, USD) |
| **VehicleType** | Catálogo de tipos de vehículo (Sedan, SUV, Pickup, Motocicleta…) |
| **upgrade_model.ps1** | Script PowerShell que genera y aplica una migración Alembic en un solo comando |

---

## 15. Hito: Motor de Órdenes de Trabajo — Resumen Ejecutivo

> **Fecha de implementación:** 2026-03-08 · **Versión de documento:** 3.0

Este hito marca la transición del sistema de una herramienta de gestión de vehículos a un **motor financiero completo** para talleres mecánicos.

### 15.1 Componentes Implementados

| Componente | Descripción |
|---|---|
| **Relación 1:N Reception → ReceptionDetail** | Una boleta de ingreso puede registrar múltiples líneas de trabajo solicitado antes de generar la OT |
| **Relación 1:1 Reception → WorkOrder** | Cada boleta genera exactamente una OT financiera; garantiza trazabilidad completa |
| **Multi-moneda** | La OT se emite en la moneda negociada (`currency_id` FK a `currencies`); soporte inmediato para CRC y USD |
| **WorkOrderLine con discriminación** | Líneas de mano de obra (heredan descripción de `ReceptionDetail`) y repuestos extra (ítem libre) bajo el mismo modelo |
| **Descuento por línea** | Campo `discount_percentage NUMERIC(5,2)` con lógica de negocio en `_subtotal()` |
| **Totales persistidos** | `total_labor`, `total_parts`, `tax_amount`, `total_final` almacenados para auditoría histórica |

### 15.2 Lógica SAP-Style — Garantías de Consistencia

```
┌──────────────────────────────────────────────────────────────────────┐
│  POST /work-orders/process           (una transacción DB)            │
│  ┌────────────────────┐    flush()   ┌─────────────────────────────┐ │
│  │  WorkOrder DRAFT   │ ──────────►  │  Reception → FINISHED       │ │
│  │  + N WorkOrderLines│              │  (misma sesión SQLAlchemy)  │ │
│  └────────────────────┘   commit()  └─────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  PATCH /work-orders/{id}/cancel      (una transacción DB)            │
│  ┌────────────────────┐    flush()   ┌─────────────────────────────┐ │
│  │  WorkOrder →       │ ──────────►  │  Reception → IN_PROGRESS    │ │
│  │  CANCELLED         │              │  (misma sesión SQLAlchemy)  │ │
│  └────────────────────┘   commit()  └─────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### 15.3 Validación E2E — `seeds/test_sap_flow.py`

El script ejecuta el ciclo completo en orden usando **`httpx.AsyncClient` con `ASGITransport`** — sin levantar servidor ni manipular ORM directamente:

```
Setup   → GET-or-POST currency / work-type (idempotente por nombre/código)
          POST customer + vehicle (fresh por run_id)
Paso 1  → POST /api/v1/receptions              ASSERT: current_status == NEW
Paso 2  → PATCH .../status?new_status=IN_PROGRESS  ASSERT: current_status == IN_PROGRESS
Paso 3  → POST /api/v1/reception-details × 2
          POST /api/v1/work-orders/process
          GET  /api/v1/receptions/{id}           ASSERT: current_status == FINISHED
Paso 4  → PATCH /api/v1/work-orders/{id}/cancel
          GET  /api/v1/work-orders/{id}          ASSERT: status == CANCELLED
          GET  /api/v1/receptions/{id}           ASSERT: current_status == IN_PROGRESS
```

**Totales validados en el último run:**

| Concepto | Valor |
|---|---|
| Mano de obra (labor) | `51.50` |
| Repuestos (parts) | `53.90` |
| IVA 13 % | `13.70` |
| **Total final** | **`119.10`** |

### 15.4 Migraciones Aplicadas

| Revisión Alembic | Descripción |
|---|---|
| `35310d98cb8b` | Rediseño de `work_orders` (FK a Reception, WorkOrderStatus ENUM, WorkOrderLine) |
| `5d8ce4790a41` | `discount_percentage NUMERIC(5,2)` en `work_order_lines` |

---

## 16. Reglas de Oro para el Desarrollo (Instrucciones de Co-Ingeniería)

1. **Prioridad de Refactorización:** Antes de agregar nuevas funcionalidades complejas, se debe extraer la lógica de los `routers` a una capa de `services/`.
2. **Integración WhatsApp (Futuro):** El sistema debe estar preparado para disparar eventos (webhooks) cuando una `WorkOrder` cambie de estado (ej. de `received` a `in_progress`).
3. **Validación Estricta:** No se aceptarán cambios en los modelos de base de datos que no incluyan un script de migración o actualización manual documentado.
4. **Idempotencia:** Todos los scripts de SQL en `/sql` deben ser ejecutables múltiples veces sin romper la base de datos.

---

## 17. Manual de Operaciones para IA

> Este bloque es una instrucción directa para el asistente de IA (Claude / GitHub Copilot).
> Su propósito es evitar acciones destructivas o redundantes sobre recursos que ya existen.

### 17.1 Estado actual de la base de datos

La base de datos **ya está poblada** con datos iniciales ejecutados mediante `backend/app/seed_data.py`.  
**No volver a insertar, recrear ni sugerir insertar manualmente** los siguientes registros:

| Tabla | Registros ya existentes |
|---|---|
| `currencies` | `CRC` (Colón Costarricense, ₡) · `USD` (Dólar Estadounidense, $) |
| `vehicle_types` | `Sedán` · `SUV` · `4x4` · `Motocicleta` |
| `work_types` | `TEST - Mantenimiento SAP` (creado por `test_sap_flow.py`, idempotente) |
| `customers` | Juan Pérez Solís (8888-1111) · María Rodríguez Vega (8888-2222) |
| `vehicles` | Toyota Corolla placa `ABC-123` · Honda CB300 placa `MTO-456` |

Si el usuario solicita datos de prueba adicionales, **agregar registros nuevos** a `seed_data.py` siguiendo el patrón idempotente existente, no reemplazar los datos actuales.

### 17.2 Procedimiento para cambios en la base de datos

Cuando el usuario pida **agregar un modelo, una columna o una relación**, el flujo correcto es:

```
1. Editar el archivo en backend/app/models/<entidad>.py
2. Actualizar schemas en backend/app/schemas/<entidad>.py
3. Crear o actualizar el router en backend/app/routers/<entidad>.py
4. Registrar el router en backend/app/routers/__init__.py y main.py
5. Ejecutar desde backend/:
       .\upgrade_model.ps1 -Message "descripcion del cambio"
```

**Nunca** sugerir `alembic revision` o `alembic upgrade` como comandos manuales sueltos; siempre usar `upgrade_model.ps1`.

### 17.3 Procedimiento para sincronizar con GitHub

Cuando el usuario pida hacer commit, push o "guardar los cambios":

```powershell
# Desde la raíz del proyecto:
.\sync_git.ps1 -Message "descripcion concisa del cambio"
```

`sync_git.ps1` ejecuta automáticamente: limpieza de índice → `git add .` → commit → `git push origin main`.  
No sugerir los comandos Git por separado a menos que el usuario lo pida explícitamente.

### 17.4 Scripts disponibles y su propósito

| Script | Ubicación | Cuándo ejecutarlo |
|---|---|---|
| `start.ps1` | raíz | Al iniciar una sesión de trabajo |
| `upgrade_model.ps1` | `backend/` | Tras cualquier cambio en modelos ORM |
| `sync_git.ps1` | raíz | Para hacer commit + push a GitHub |
| `seed_data.py` | `backend/app/` | Solo para agregar nuevos datos de prueba (idempotente) |

### 17.5 Variables de entorno clave

| Variable | Valor por defecto | Efecto |
|---|---|---|
| `DEBUG` | `false` | `true` expone el endpoint `POST /seed` en Swagger |
| `SEED_ON_STARTUP` | `false` | `true` ejecuta `seed_data.py` al arrancar la API |

### 17.6 Reglas de migración (lecciones aprendidas)

1. **ENUMs nuevos**: crear con `op.execute(sa.text("CREATE TYPE ... AS ENUM ..."))` **antes** de usarlos en columnas.
2. **Cambio de tipo en columna con DEFAULT**: tres pasos en raw SQL: `DROP DEFAULT` → `ALTER TYPE USING` → `SET DEFAULT`.
3. **Nombres de FK**: siempre explícitos (`fk_tabla_columna`), nunca autogenerados anónimos.
4. **Columnas nuevas en tablas existentes**: siempre `nullable=True` en la primera migración.
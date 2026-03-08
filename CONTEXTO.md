# CONTEXTO.md — Documentación Técnica: MicroTaller API

> Versión del documento: 2.0 · Fecha: 2026-03-08  
> Actualizado para reflejar la incorporación de VehicleType, Currency, Alembic y scripts de automatización.

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
├── start.ps1                     # Inicio rápido: Docker + venv
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini               # Configuración de Alembic
│   ├── upgrade_model.ps1         # Script de migración automatizada
│   ├── alembic/
│   │   ├── env.py                # Config async + carga de modelos
│   │   ├── script.py.mako        # Plantilla de scripts de migración
│   │   ├── README                # Referencia rápida de comandos
│   │   └── versions/             # Archivos de migración generados
│   ├── app/
│   │   ├── main.py               # Punto de entrada FastAPI, lifespan, CORS, routers
│   │   ├── config.py             # Settings (pydantic-settings, .env)
│   │   ├── database.py           # Motor async, sesión, Base declarativa
│   │   ├── models/               # Modelos SQLAlchemy (ORM)
│   │   │   ├── currency.py
│   │   │   ├── customer.py
│   │   │   ├── vehicle.py
│   │   │   ├── vehicle_type.py
│   │   │   └── work_order.py
│   │   ├── schemas/              # Schemas Pydantic (request / response)
│   │   │   ├── currency.py
│   │   │   ├── customer.py
│   │   │   ├── vehicle.py
│   │   │   ├── vehicle_type.py
│   │   │   └── work_order.py
│   │   └── routers/              # Endpoints FastAPI
│   │       ├── currencies.py
│   │       ├── customers.py
│   │       ├── vehicle_types.py
│   │       ├── vehicles.py
│   │       └── work_orders.py
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

work_orders
  ├── id             UUID  PK
  ├── vehicle_id     UUID  FK → vehicles.id  ON DELETE RESTRICT  INDEX
  ├── status         ENUM(order_status)  NOT NULL  DEFAULT 'received'  INDEX
  ├── checkin_photos JSON            NULLABLE
  ├── notes          TEXT            NULLABLE
  ├── created_at     TIMESTAMPTZ     DEFAULT now()
  └── closed_at      TIMESTAMPTZ     NULLABLE
  [índice compuesto: (vehicle_id, created_at)]
  [índice compuesto: (status, created_at)]

work_order_items
  ├── id             UUID  PK
  ├── work_order_id  UUID  FK → work_orders.id  ON DELETE CASCADE   INDEX
  ├── currency_id    UUID  FK → currencies.id   ON DELETE SET NULL  INDEX  NULLABLE
  ├── description    VARCHAR(255)     NOT NULL
  ├── quantity       NUMERIC(10,3)    NOT NULL  CHECK > 0
  ├── unit_price     NUMERIC(10,2)    NOT NULL  CHECK >= 0
  └── total          NUMERIC(10,2)    NOT NULL  CHECK >= 0
```

### 6.2 Relaciones

| Relación | Cardinalidad | Eliminación |
|---|---|---|
| Customer → Vehicle | 1 : N | RESTRICT (no se puede eliminar un cliente con vehículos) |
| VehicleType → Vehicle | 1 : N | SET NULL (el vehículo queda sin tipo si se borra el tipo) |
| Vehicle → WorkOrder | 1 : N | RESTRICT (no se puede eliminar un vehículo con órdenes) |
| WorkOrder → WorkOrderItem | 1 : N | CASCADE (al borrar una orden se borran sus ítems) |
| Currency → WorkOrderItem | 1 : N | SET NULL (el ítem queda sin moneda si se borra la moneda) |

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

### 7.1 Máquina de Estados — `OrderStatus`

Las órdenes de trabajo siguen un ciclo de vida estricto:

```
  ┌──────────────┐
  │   received   │────────────────────────┐
  └──────┬───────┘                        │
         │                                ▼
         │               ┌────────────────────────────┐
         │               │         delivered          │  ← TERMINAL
         │               └────────────────────────────┘
         │                                ▲
         ▼                                │
  ┌──────────────┐                        │
  │ in_progress  │────────────────────────┘
  └──────────────┘
```

| Transición | Permitida |
|---|---|
| `received` → `in_progress` | ✅ |
| `received` → `delivered` | ✅ (trabajo simple sin etapa intermedia) |
| `in_progress` → `delivered` | ✅ |
| cualquier cosa → `received` | ❌ |
| `delivered` → cualquiera | ❌ (terminal) |

Las transiciones se validan en `_assert_transition()` devolviendo **HTTP 422** si no son válidas.

### 7.2 Cierre de Orden (`POST /work-orders/{id}/close`)

Reglas de negocio aplicadas antes de marcar como `delivered`:
1. La orden debe existir.
2. Debe tener **al menos un ítem**; sin ítems devuelve HTTP 422.
3. La transición de estado debe ser válida según la máquina de estados.
4. Al cerrar se registra `closed_at = datetime.now(UTC)`.

### 7.3 Cálculo del Total

El total de cada ítem se calcula en backend como:

$$total = quantity \times unit\_price$$

Redondeado a 2 decimales con política `ROUND_HALF_UP`. El total de la orden entera es un `@computed_field` de Pydantic, nunca almacenado en DB.

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

### 8.3 Work Orders

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/work-orders` | Listar órdenes (paginado; filtros `vehicle_id`, `status`) |
| `GET` | `/work-orders/open` | Listar órdenes no entregadas |
| `GET` | `/work-orders/by-plate/{plate}` | Órdenes de un vehículo por placa |
| `GET` | `/work-orders/{id}` | Obtener orden por ID |
| `POST` | `/work-orders` | Crear orden (con ítems opcionales) → 201 |
| `PATCH` | `/work-orders/{id}` | Actualizar estado / notas / fotos |
| `DELETE` | `/work-orders/{id}` | Eliminar → 204 |
| `POST` | `/work-orders/{id}/close` | Cerrar orden → `delivered` |

### 8.4 Work Order Items

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/work-orders/{id}/items` | Agregar ítem → 201 |
| `PATCH` | `/work-orders/{id}/items/{item_id}` | Actualizar ítem (recalcula total) |
| `DELETE` | `/work-orders/{id}/items/{item_id}` | Eliminar ítem → 204 |

### 8.5 Vehicle Types

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/vehicle-types` | Listar tipos de vehículo |
| `GET` | `/vehicle-types/{id}` | Obtener tipo por ID |
| `POST` | `/vehicle-types` | Crear tipo → 201 (409 si nombre duplicado) |
| `PATCH` | `/vehicle-types/{id}` | Actualización parcial |
| `DELETE` | `/vehicle-types/{id}` | Eliminar → 204 |

### 8.6 Currencies

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/currencies` | Listar monedas ordenadas por código ISO |
| `GET` | `/currencies/{id}` | Obtener moneda por ID |
| `POST` | `/currencies` | Crear moneda → 201 (409 si code o name duplicado) |
| `PATCH` | `/currencies/{id}` | Actualización parcial |
| `DELETE` | `/currencies/{id}` | Eliminar → 204 |

### 8.7 Salud

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
| `ondelete="CASCADE"` en WorkOrder→Item | Los ítems son parte de la orden; no tienen sentido sin ella |
| `ROUND_HALF_UP` | Comportamiento de redondeo contable estándar |
| Índices compuestos en `work_orders` | Optimizan las consultas más frecuentes: por vehículo+fecha y por estado+fecha |

---

## 13. Áreas de Mejora Identificadas

| Área | Estado | Observación |
|---|---|---|
| Capa de servicio | ⚠️ Pendiente | La lógica de negocio en los routers dificulta los tests unitarios; se recomienda extraer una capa `services/` |
| Migraciones | ✅ Implementado | Alembic configurado con `env.py` async y script `upgrade_model.ps1` |
| Tests | ⚠️ Pendiente | No existe directorio `tests/`; se recomienda pytest + httpx AsyncClient |
| Autenticación | ⚠️ Pendiente | No hay mecanismo de autenticación/autorización (JWT, API Key, OAuth2) |
| CORS en producción | ⚠️ Pendiente | La política wildcard debe restringirse antes de hacer deploy |
| `--reload` en producción | ⚠️ Pendiente | Debe quitarse del CMD del Dockerfile para producción |
| Logging estructurado | ⚠️ Pendiente | Solo hay `print()` en el lifespan; se recomienda `structlog` o `logging` estándar |
| Health check de BD | ⚠️ Pendiente | El endpoint `/health` no verifica la conectividad a la DB en tiempo real |

---

## 14. Glosario

| Término | Definición |
|---|---|
| **Work Order** | Orden de trabajo abierta para un vehículo; agrupa los trabajos realizados |
| **Work Order Item** | Línea de detalle de una orden (mano de obra, repuesto, etc.) |
| **received** | Estado inicial: vehículo ingresado, trabajo pendiente |
| **in_progress** | Trabajo en ejecución |
| **delivered** | Trabajo terminado y vehículo entregado al cliente (estado terminal) |
| **Lifespan** | Hook de FastAPI para inicialización y limpieza al arrancar/detener la app |
| **AsyncSession** | Sesión de SQLAlchemy que opera de forma no bloqueante con `asyncio` |
| **Currency** | Moneda ISO-4217 asociada opcionalmente a un ítem de orden de trabajo |
| **VehicleType** | Catálogo de tipos de vehículo (Sedan, SUV, Pickup, Motocicleta…) |
| **upgrade_model.ps1** | Script PowerShell que genera y aplica una migración Alembic en un solo comando |

## 15. Reglas de Oro para el Desarrollo (Instrucciones de Co-Ingeniería)

1. **Prioridad de Refactorización:** Antes de agregar nuevas funcionalidades complejas, se debe extraer la lógica de los `routers` a una capa de `services/`.
2. **Integración WhatsApp (Futuro):** El sistema debe estar preparado para disparar eventos (webhooks) cuando una `WorkOrder` cambie de estado (ej. de `received` a `in_progress`).
3. **Validación Estricta:** No se aceptarán cambios en los modelos de base de datos que no incluyan un script de migración o actualización manual documentado.
4. **Idempotencia:** Todos los scripts de SQL en `/sql` deben ser ejecutables múltiples veces sin romper la base de datos.
"""seeds/test_sap_flow.py â€” ValidaciÃ³n automÃ¡tica del flujo SAP-style.

Usa httpx.AsyncClient con ASGITransport para ejercitar los endpoints reales
de la API sin levantar un servidor.  Cada transiciÃ³n de estado ocurre a travÃ©s
de una llamada HTTP â€” exactamente igual a como lo harÃ­a un cliente real.

Ejecutar desde backend/:
    python -m app.seeds.test_sap_flow

Flujo completo:
    Setup   â†’ GET-or-POST currency / work-type  (datos de catÃ¡logo, idempotente)
              POST customer + vehicle fresh por cada ejecuciÃ³n
    Paso 1  â†’ POST /api/v1/receptions           â†’ NEW
    Paso 2  â†’ PATCH /api/v1/receptions/{id}/status?new_status=IN_PROGRESS
    Paso 3  â†’ POST /api/v1/reception-details    (x2 trabajos)
              POST /api/v1/work-orders/process
              ASSERT (GET reception): current_status == FINISHED
    Paso 4  â†’ PATCH /api/v1/work-orders/{id}/cancel
              ASSERT (GET reception): current_status == IN_PROGRESS
              ASSERT (GET work-order): status == CANCELLED
"""
import asyncio
import sys
import time

import httpx

from app.main import app

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Console colours
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

BOLD   = "\033[1m"
GREEN  = "\033[32m"
CYAN   = "\033[36m"
YELLOW = "\033[33m"
RED    = "\033[31m"
RESET  = "\033[0m"
LINE   = "â”€" * 60

BASE   = "http://test/api/v1"


def _log_header(title: str) -> None:
    print(f"\n{CYAN}{LINE}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{CYAN}{LINE}{RESET}")


def _log_ok(msg: str) -> None:
    print(f"  {GREEN}âœ“{RESET} {msg}")


def _log_info(msg: str) -> None:
    print(f"  {YELLOW}â€¢{RESET} {msg}")


def _assert_field(label: str, expected: str, actual: str) -> None:
    if expected == actual:
        print(f"  {GREEN}âœ“ ASSERT {label}: {actual!r}{RESET}")
    else:
        print(f"  {RED}âœ— ASSERT FAILED â€” {label}: expected={expected!r}, got={actual!r}{RESET}")
        sys.exit(1)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# HTTP helpers
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _check(response: httpx.Response, expected_status: int, ctx: str) -> dict:
    """Assert HTTP status; print the error body and exit(1) on mismatch."""
    if response.status_code != expected_status:
        print(
            f"\n  {RED}âœ— {ctx}\n"
            f"    HTTP {response.status_code} (expected {expected_status})\n"
            f"    {response.text}{RESET}\n"
        )
        sys.exit(1)
    return response.json()


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Setup helpers â€” catalog data (upsert via GET-or-POST)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def _get_or_create_currency(client: httpx.AsyncClient) -> dict:
    """Return the USD currency record, creating it if necessary."""
    resp  = _check(await client.get(f"{BASE}/currencies?limit=100"), 200, "GET /currencies")
    match = next((c for c in resp["items"] if c["code"] == "USD"), None)
    if match:
        _log_info(f"Currency existente â†’ {match['id']}  code=USD")
        return match
    data = _check(
        await client.post(f"{BASE}/currencies", json={"name": "US Dollar", "code": "USD", "symbol": "$"}),
        201, "POST /currencies",
    )
    _log_ok(f"Currency creada  â†’ {data['id']}  code=USD")
    return data


async def _get_or_create_work_type(client: httpx.AsyncClient) -> dict:
    """Return the test work-type, creating it if necessary."""
    name  = "TEST - Mantenimiento SAP"
    resp  = _check(await client.get(f"{BASE}/work-types?limit=100"), 200, "GET /work-types")
    match = next((w for w in resp["items"] if w["name"] == name), None)
    if match:
        _log_info(f"WorkType existente â†’ {match['id']}")
        return match
    data = _check(
        await client.post(f"{BASE}/work-types", json={"name": name, "description": "Usado por test_sap_flow"}),
        201, "POST /work-types",
    )
    _log_ok(f"WorkType creada  â†’ {data['id']}")
    return data


async def _create_customer(client: httpx.AsyncClient, run_id: str) -> dict:
    data = _check(
        await client.post(f"{BASE}/customers", json={
            "identification": f"SAP-{run_id}",
            "name":  f"Cliente Test SAP [{run_id}]",
            "phone": "0000-0000",
            "email": f"sap.{run_id}@example.com",
        }),
        201, "POST /customers",
    )
    _log_ok(f"Customer creado  â†’ {data['id']}")
    return data


async def _create_vehicle(client: httpx.AsyncClient, customer_id: str, run_id: str) -> dict:
    data = _check(
        await client.post(f"{BASE}/vehicles", json={
            "customer_id":  customer_id,
            "brand":  "Toyota",
            "model":  "Corolla",
            "year":   2020,
            "plate":  f"TST-{run_id}",
        }),
        201, "POST /vehicles",
    )
    _log_ok(f"Vehicle creado   â†’ {data['id']}  plate={data['plate']}")
    return data


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Paso 1 â€” Crear Reception (POST â†’ NEW)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def _paso1_create_reception(
    client: httpx.AsyncClient,
    customer_id: str,
    vehicle_id: str,
    work_type_id: str,
) -> dict:
    _log_header("PASO 1 â€” POST /receptions  â†’  NEW")

    data = _check(
        await client.post(f"{BASE}/receptions", json={
            "customer_id":       customer_id,
            "vehicle_id":        vehicle_id,
            "work_type_id":      work_type_id,
            "reported_problem":  "RevisiÃ³n general â€” test SAP flow",
            "received_by":       "QA-Bot",
            "mileage":           45000,
        }),
        201, "POST /receptions",
    )
    _log_ok(f"Reception creada â†’ {data['id']}")
    _assert_field("current_status", "NEW", data["current_status"])
    return data


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Paso 2 â€” Avanzar Reception a IN_PROGRESS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def _paso2_to_in_progress(client: httpx.AsyncClient, reception_id: str) -> dict:
    _log_header("PASO 2 â€” PATCH /receptions/{id}/status  â†’  IN_PROGRESS")

    data = _check(
        await client.patch(
            f"{BASE}/receptions/{reception_id}/status",
            params={"new_status": "IN_PROGRESS"},
        ),
        200, "PATCH /receptions/{id}/status IN_PROGRESS",
    )
    _log_ok(f"Reception {reception_id} avanzada")
    _assert_field("current_status", "IN_PROGRESS", data["current_status"])
    return data


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Paso 3 â€” Crear ReceptionDetails + WorkOrder (POST /process)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def _paso3_process_work_order(
    client: httpx.AsyncClient,
    reception_id: str,
    work_type_id: str,
    currency_id: str,
) -> dict:
    _log_header("PASO 3 â€” ReceptionDetails + POST /work-orders/process")

    # 3a. Create two labour work items on the reception
    detail_oil = _check(
        await client.post(f"{BASE}/reception-details", json={
            "reception_id":  reception_id,
            "work_type_id":  work_type_id,
            "description":   "Cambio de aceite 5W-30",
        }),
        201, "POST /reception-details (aceite)",
    )
    _log_ok(f"ReceptionDetail (aceite)  â†’ {detail_oil['id']}")

    detail_filter = _check(
        await client.post(f"{BASE}/reception-details", json={
            "reception_id":  reception_id,
            "work_type_id":  work_type_id,
            "description":   "Reemplazo filtro de aire",
        }),
        201, "POST /reception-details (filtro)",
    )
    _log_ok(f"ReceptionDetail (filtro)  â†’ {detail_filter['id']}")

    # 3b. Create WorkOrder linking those details with pricing
    wo_data = _check(
        await client.post(f"{BASE}/work-orders/process", json={
            "reception_id": reception_id,
            "currency_id":  currency_id,
            "notes":        "Generado por test_sap_flow",
            "tax_rate":     0.13,
            "labor_items": [
                {
                    "reception_detail_id": detail_oil["id"],
                    "quantity":            1.0,
                    "unit_price":          35.00,
                    "discount_percentage": 10.00,
                },
                {
                    "reception_detail_id": detail_filter["id"],
                    "quantity":            1.0,
                    "unit_price":          20.00,
                    "discount_percentage": 0.00,
                },
            ],
            "extra_lines": [
                {
                    "description":         "Aceite Mobil 1L x5",
                    "quantity":            5.0,
                    "unit_price":          8.50,
                    "is_part":             True,
                    "discount_percentage": 0.00,
                },
                {
                    "description":         "Filtro de aire OEM",
                    "quantity":            1.0,
                    "unit_price":          12.00,
                    "is_part":             True,
                    "discount_percentage": 5.00,
                },
            ],
        }),
        201, "POST /work-orders/process",
    )
    _log_ok(f"WorkOrder creada â†’ {wo_data['work_order_id']}  nÃºmero={wo_data['order_number']}")
    _log_info(
        f"Totales â€” labor={wo_data['total_labor']}  parts={wo_data['total_parts']}  "
        f"tax={wo_data['tax_amount']}  final={wo_data['total_final']}"
    )

    # 3c. Verify reception transitioned to FINISHED via GET (endpoint side-effect)
    _log_info("Verificando Reception via GET...")
    reception_data = _check(
        await client.get(f"{BASE}/receptions/{reception_id}"),
        200, "GET /receptions/{id}",
    )
    _assert_field(
        "reception_status after process",
        "FINISHED",
        reception_data["current_status"],
    )
    _assert_field("work_order.reception_status in response", "FINISHED", wo_data["reception_status"])

    return wo_data


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Paso 4 â€” Cancelar WorkOrder (PATCH /{id}/cancel)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def _paso4_cancel(client: httpx.AsyncClient, wo_id: str, reception_id: str) -> None:
    _log_header("PASO 4 â€” PATCH /work-orders/{id}/cancel")

    wo_data = _check(
        await client.patch(f"{BASE}/work-orders/{wo_id}/cancel"),
        200, "PATCH /work-orders/{id}/cancel",
    )
    _log_ok(f"WorkOrder {wo_id} cancelada")

    # Verify work order via GET
    _log_info("Verificando WorkOrder via GET...")
    wo_get = _check(
        await client.get(f"{BASE}/work-orders/{wo_id}"),
        200, "GET /work-orders/{id}",
    )
    _assert_field("work_order.status == CANCELLED", "CANCELLED", wo_get["status"])

    # Verify reception rolled back via GET
    _log_info("Verificando Reception via GET...")
    reception_data = _check(
        await client.get(f"{BASE}/receptions/{reception_id}"),
        200, "GET /receptions/{id}",
    )
    _assert_field(
        "reception_status after cancel",
        "IN_PROGRESS",
        reception_data["current_status"],
    )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Summary
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _print_summary(customer: dict, vehicle: dict, reception: dict, wo: dict) -> None:
    _log_header("RESUMEN FINAL")
    rows = [
        ("customer_id",       customer["id"]),
        ("vehicle_plate",     vehicle["plate"]),
        ("reception_id",      reception["id"]),
        ("reception_status",  "IN_PROGRESS  (revertida tras cancelaciÃ³n)"),
        ("work_order_id",     wo["work_order_id"]),
        ("work_order_number", wo["order_number"]),
        ("work_order_status", "CANCELLED"),
        ("total_labor",       str(wo["total_labor"])),
        ("total_parts",       str(wo["total_parts"])),
        ("tax_amount",        str(wo["tax_amount"])),
        ("total_final",       str(wo["total_final"])),
    ]
    for key, val in rows:
        print(f"  {BOLD}{key:<28}{RESET} {val}")
    print(f"\n{GREEN}{BOLD}  âœ“ Flujo SAP completo validado correctamente.{RESET}\n")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Entrypoint
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def run() -> None:
    run_id = str(int(time.time()))[-6:]  # last 6 digits of Unix timestamp

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

        # â”€â”€ Setup fixtures â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _log_header(f"SETUP â€” Fixtures  (run_id={run_id})")
        currency  = await _get_or_create_currency(client)
        work_type = await _get_or_create_work_type(client)
        customer  = await _create_customer(client, run_id)
        vehicle   = await _create_vehicle(client, customer["id"], run_id)

        # â”€â”€ Business flow â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        reception = await _paso1_create_reception(
            client, customer["id"], vehicle["id"], work_type["id"]
        )
        await _paso2_to_in_progress(client, reception["id"])

        wo = await _paso3_process_work_order(
            client, reception["id"], work_type["id"], currency["id"]
        )
        await _paso4_cancel(client, wo["work_order_id"], reception["id"])

        _print_summary(customer, vehicle, reception, wo)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"\n{RED}{BOLD}  âœ— ERROR INESPERADO: {exc}{RESET}\n")
        raise



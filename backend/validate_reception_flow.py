"""validate_reception_flow.py — Script de validación QA para el flujo completo de Recepción.

Ejecutar desde backend/ con el servidor activo:
    python validate_reception_flow.py
    python validate_reception_flow.py --base-url http://localhost:8000
    python validate_reception_flow.py --base-url http://localhost:8000 --work-type-id <uuid>

Requisitos:
    pip install httpx      (o: pip install -r requirements.txt)

El script realiza 7 pasos secuenciales contra la API real y reporta
PASS / FAIL para cada verificación, con detalle de los valores esperados
vs. los obtenidos cuando hay una discrepancia.
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx

# ── Color helpers ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

PASS = f"{GREEN}[PASS]{RESET}"
FAIL = f"{RED}[FAIL]{RESET}"
STEP = f"{CYAN}{BOLD}[STEP]{RESET}"
INFO = f"{YELLOW}[INFO]{RESET}"


def ok(msg: str) -> None:
    print(f"  {PASS} {msg}")


def fail(msg: str, expected=None, got=None) -> None:
    print(f"  {FAIL} {msg}")
    if expected is not None:
        print(f"         esperado : {expected!r}")
        print(f"         obtenido : {got!r}")


def step(n: int, title: str) -> None:
    print(f"\n{STEP} {BOLD}Paso {n}: {title}{RESET}")


def assert_status(resp: httpx.Response, expected: int, context: str) -> bool:
    if resp.status_code == expected:
        ok(f"HTTP {resp.status_code} — {context}")
        return True
    fail(f"HTTP status incorrecto — {context}", expected=expected, got=resp.status_code)
    print(f"         body: {resp.text[:300]}")
    return False


def assert_field(data: dict, path: str, expected, label: str) -> bool:
    """Traverse dot-separated path and compare leaf value."""
    keys = path.split(".")
    node = data
    for k in keys:
        if isinstance(node, dict) and k in node:
            node = node[k]
        else:
            fail(f"{label}: campo '{path}' no encontrado en la respuesta")
            return False
    if node == expected:
        ok(f"{label}: {path} == {expected!r}")
        return True
    fail(f"{label}: {path}", expected=expected, got=node)
    return False


# ── Main flow ─────────────────────────────────────────────────────────────────

def run(base_url: str, work_type_id: str | None) -> int:
    """Returns exit code: 0 = all passed, 1 = one or more failures."""
    failures = 0
    client = httpx.Client(base_url=base_url, timeout=10.0)

    # -- Resolve a work_type_id automatically if not provided -----------------
    if work_type_id is None:
        print(f"\n{INFO} work_type_id no especificado — consultando GET /api/v1/work-types")
        r = client.get("/api/v1/work-types", params={"limit": 1})
        if r.status_code == 200 and r.json().get("total", 0) > 0:
            work_type_id = r.json()["items"][0]["id"]
            print(f"  {INFO} Usando work_type_id: {work_type_id}")
        else:
            print(f"  {RED}No se encontró ningún WorkType. "
                  f"Crea uno en /api/v1/work-types o pasa --work-type-id.{RESET}")
            return 1

    # ─────────────────────────────────────────────────────────────────────────
    # Paso 1: Crear recepción atómica
    # ─────────────────────────────────────────────────────────────────────────
    step(1, "Crear Recepción Atómica (POST /api/v1/receptions/process)")

    now_utc = datetime.now(timezone.utc)
    process_payload = {
        "customer": {
            "identification": f"QA-{int(now_utc.timestamp())}",
            "name": "Cliente QA Automatizado",
            "phone": "8000-0000",
            "email": "qa@microtaller.test",
        },
        "vehicle": {
            "plate": f"QA-{int(now_utc.timestamp()) % 100000:05d}",
            "brand": "Toyota",
            "model": "Corolla QA",
            "year": 2022,
            "vin_number": f"VIN-QA-{int(now_utc.timestamp())}",
        },
        "work_type_id": work_type_id,
        "reported_problem": "Vibración al frenar en autopista",
        "received_by": "QA Bot",
        "mileage": 45000,
        "fuel_level": "THREE_QUARTERS",
    }

    r = client.post("/api/v1/receptions/process", json=process_payload)
    if not assert_status(r, 201, "Recepción creada"):
        failures += 1
        print(f"\n{RED}Paso 1 fallido — no se puede continuar.{RESET}")
        return 1

    proc = r.json()
    reception_id: str = proc["reception_id"]
    customer_id:  str = proc["customer_id"]
    vehicle_id:   str = proc["vehicle_id"]

    if not assert_field(proc, "current_status", "NEW", "Estado inicial"):
        failures += 1
    if proc.get("customer_created"):
        ok("customer_created == True (nuevo cliente)")
    else:
        fail("Se esperaba customer_created == True")
        failures += 1
    if proc.get("vehicle_created"):
        ok("vehicle_created == True (nuevo vehículo)")
    else:
        fail("Se esperaba vehicle_created == True")
        failures += 1

    print(f"  {INFO} reception_id : {reception_id}")
    print(f"  {INFO} customer_id  : {customer_id}")
    print(f"  {INFO} vehicle_id   : {vehicle_id}")

    # ─────────────────────────────────────────────────────────────────────────
    # Paso 2: Cambiar estado NEW → IN_PROGRESS
    # ─────────────────────────────────────────────────────────────────────────
    step(2, "Cambiar estado NEW → IN_PROGRESS")

    r = client.patch(
        f"/api/v1/receptions/{reception_id}/status",
        params={"new_status": "IN_PROGRESS"},
    )
    if not assert_status(r, 200, "Transición de estado"):
        failures += 1
    else:
        if not assert_field(r.json(), "current_status", "IN_PROGRESS", "Estado actualizado"):
            failures += 1

    # ─────────────────────────────────────────────────────────────────────────
    # Paso 3a: Registrar Trabajo 1
    # ─────────────────────────────────────────────────────────────────────────
    step(3, "Registrar Trabajo 1 — Cambio de pastillas cerámicas")

    r = client.post("/api/v1/reception-details", json={
        "reception_id": reception_id,
        "work_type_id": work_type_id,
        "description": "Cambio de pastillas cerámicas",
        # work_date omitted → backend defaults to now
    })
    if not assert_status(r, 201, "Trabajo 1 creado"):
        failures += 1
        work1 = {}
    else:
        work1 = r.json()
        ok(f"work1_id: {work1['id']}")

        # Validate work_date was auto-filled (should be very close to now)
        try:
            wd = datetime.fromisoformat(work1["work_date"].replace("Z", "+00:00"))
            delta = abs((wd - now_utc).total_seconds())
            if delta < 30:
                ok(f"work_date auto-asignada (delta={delta:.1f}s ≤ 30s)")
            else:
                fail("work_date auto-asignada fuera del rango esperado (>30s de diferencia)", expected="≈ now", got=work1["work_date"])
                failures += 1
        except Exception as e:
            fail(f"No se pudo parsear work_date: {e}")
            failures += 1

    # ─────────────────────────────────────────────────────────────────────────
    # Paso 3b: Registrar Trabajo 2 (work_date = hace 2 horas)
    # ─────────────────────────────────────────────────────────────────────────
    step(3, "Registrar Trabajo 2 — Rectificación de discos (work_date = hace 2 horas)")

    two_hours_ago = (now_utc - timedelta(hours=2)).isoformat()
    r = client.post("/api/v1/reception-details", json={
        "reception_id": reception_id,
        "work_type_id": work_type_id,
        "description": "Rectificación de discos delanteros",
        "work_date": two_hours_ago,
    })
    if not assert_status(r, 201, "Trabajo 2 creado"):
        failures += 1
        work2_id = None
    else:
        work2 = r.json()
        work2_id: str = work2["id"]
        ok(f"work2_id: {work2_id}")

        # Validate stored work_date matches the sent value
        try:
            stored_wd  = datetime.fromisoformat(work2["work_date"].replace("Z", "+00:00"))
            sent_wd    = datetime.fromisoformat(two_hours_ago)
            delta_secs = abs((stored_wd - sent_wd).total_seconds())
            if delta_secs < 2:
                ok(f"work_date almacenada correctamente (delta={delta_secs:.2f}s)")
            else:
                fail("work_date guardada difiere de la enviada", expected=two_hours_ago, got=work2["work_date"])
                failures += 1
        except Exception as e:
            fail(f"No se pudo parsear work_date: {e}")
            failures += 1

        # created_at should be AFTER work_date
        try:
            created = datetime.fromisoformat(work2["created_at"].replace("Z", "+00:00"))
            work_dt = datetime.fromisoformat(work2["work_date"].replace("Z", "+00:00"))
            if created > work_dt:
                ok(f"created_at ({created.strftime('%H:%M:%S')}) > work_date ({work_dt.strftime('%H:%M:%S')}) ✓")
            else:
                fail("created_at debería ser POSTERIOR a work_date (trabajo pasado)",
                     expected="created_at > work_date", got=f"created_at={work2['created_at']}, work_date={work2['work_date']}")
                failures += 1
        except Exception as e:
            fail(f"No se pudo comparar fechas de auditoría: {e}")
            failures += 1

    # ─────────────────────────────────────────────────────────────────────────
    # Paso 4: Modificar descripción del Trabajo 2
    # ─────────────────────────────────────────────────────────────────────────
    step(4, f"Modificar descripción del Trabajo 2 (PATCH /reception-details/{work2_id})")

    if work2_id is None:
        print(f"  {YELLOW}Saltado — Trabajo 2 no fue creado en el paso anterior.{RESET}")
        failures += 1
    else:
        new_desc = "Rectificación de discos de alta precisión"
        r = client.patch(f"/api/v1/reception-details/{work2_id}", json={"description": new_desc})
        if not assert_status(r, 200, "Descripción actualizada"):
            failures += 1
        else:
            patched = r.json()
            if not assert_field(patched, "description", new_desc, "Nueva descripción"):
                failures += 1

            # updated_at must be >= created_at
            try:
                created   = datetime.fromisoformat(patched["created_at"].replace("Z", "+00:00"))
                updated   = datetime.fromisoformat(patched["updated_at"].replace("Z", "+00:00"))
                if updated >= created:
                    ok(f"updated_at ({updated.strftime('%H:%M:%S')}) ≥ created_at ({created.strftime('%H:%M:%S')}) ✓")
                else:
                    fail("updated_at debería ser ≥ created_at",
                         expected="updated_at ≥ created_at", got=f"updated={patched['updated_at']}, created={patched['created_at']}")
                    failures += 1
            except Exception as e:
                fail(f"No se pudo comparar fechas de auditoría en PATCH: {e}")
                failures += 1

    # ─────────────────────────────────────────────────────────────────────────
    # Paso 5: Cambiar estado IN_PROGRESS → FINISHED
    # ─────────────────────────────────────────────────────────────────────────
    step(5, "Finalizar recepción — IN_PROGRESS → FINISHED")

    r = client.patch(
        f"/api/v1/receptions/{reception_id}/status",
        params={"new_status": "FINISHED"},
    )
    if not assert_status(r, 200, "Transición a FINISHED"):
        failures += 1
    else:
        if not assert_field(r.json(), "current_status", "FINISHED", "Estado final"):
            failures += 1

    # Verify terminal transitions are rejected
    r_bad = client.patch(
        f"/api/v1/receptions/{reception_id}/status",
        params={"new_status": "NEW"},
    )
    if r_bad.status_code == 422:
        ok("Transición FINISHED → NEW correctamente rechazada (422)")
    else:
        fail("Se esperaba 422 al intentar FINISHED → NEW", expected=422, got=r_bad.status_code)
        failures += 1

    # ─────────────────────────────────────────────────────────────────────────
    # Paso 6: GET final y validación completa
    # ─────────────────────────────────────────────────────────────────────────
    step(6, f"Validación final — GET /api/v1/receptions/{reception_id}")

    r = client.get(f"/api/v1/receptions/{reception_id}")
    if not assert_status(r, 200, "Detalle de recepción"):
        failures += 1
    else:
        rec = r.json()

        if not assert_field(rec, "current_status", "FINISHED", "Estado final confirmado"):
            failures += 1
        if not assert_field(rec, "customer_id", customer_id, "customer_id correcto"):
            failures += 1
        if not assert_field(rec, "vehicle_id", vehicle_id, "vehicle_id correcto"):
            failures += 1
        if not assert_field(rec, "mileage", 45000, "Kilometraje preservado"):
            failures += 1

        details = rec.get("details", [])
        if len(details) == 2:
            ok(f"2 trabajos incluídos en la respuesta")
        else:
            fail("Cantidad de trabajos en details", expected=2, got=len(details))
            failures += 1

        # Verify the updated description persists in the full GET
        descriptions = {d["description"] for d in details}
        if "Rectificación de discos de alta precisión" in descriptions:
            ok("Descripción modificada persiste en GET completo")
        else:
            fail("Descripción no actualizada en GET final",
                 expected="Rectificación de discos de alta precisión",
                 got=descriptions)
            failures += 1

        # Check all details have work_date and created_at populated
        all_dates_ok = all(d.get("work_date") and d.get("created_at") for d in details)
        if all_dates_ok:
            ok("Todos los detalles tienen work_date y created_at poblados")
        else:
            fail("Algún detalle tiene work_date o created_at vacío")
            failures += 1

    # ─────────────────────────────────────────────────────────────────────────
    # Resumen
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'─'*55}")
    if failures == 0:
        print(f"{GREEN}{BOLD}  ✓ TODOS LOS PASOS PASARON ({failures} fallos){RESET}")
    else:
        print(f"{RED}{BOLD}  ✗ {failures} VERIFICACIÓN(ES) FALLARON{RESET}")
    print(f"{'─'*55}\n")

    client.close()
    return 0 if failures == 0 else 1


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Valida el flujo completo de Recepción en MicroTaller")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="URL base de la API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--work-type-id",
        default=None,
        help="UUID de un WorkType existente. Si se omite, se usa el primero disponible.",
    )
    args = parser.parse_args()

    try:
        import httpx  # noqa: F401 — give a clear error if missing
    except ImportError:
        print(f"{RED}httpx no está instalado. Ejecuta: pip install httpx{RESET}")
        sys.exit(1)

    sys.exit(run(args.base_url, args.work_type_id))

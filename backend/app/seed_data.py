"""seed_data.py — Datos de prueba iniciales para MicroTaller.

Ejecución directa (desde backend/ con el venv activo):
    python -m app.seed_data

También se puede invocar desde main.py en modo DEBUG mediante la
variable de entorno SEED_ON_STARTUP=true.

Lógica de seguridad: cada entidad verifica si ya existe antes de
insertar, usando el campo único de negocio (code, name, plate, etc.)
para ser completamente idempotente.
"""
import asyncio
import uuid

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.currency import Currency
from app.models.customer import Customer
from app.models.vehicle import Vehicle
from app.models.vehicle_type import VehicleType


# ---------------------------------------------------------------------------
# Datos de referencia
# ---------------------------------------------------------------------------

CURRENCIES = [
    {"code": "CRC", "name": "Colón Costarricense", "symbol": "₡"},
    {"code": "USD", "name": "Dólar Estadounidense", "symbol": "$"},
]

VEHICLE_TYPES = [
    "Sedán",
    "SUV",
    "4x4",
    "Motocicleta",
]

CUSTOMERS = [
    {
        "name": "Juan Pérez Solís",
        "phone": "8888-1111",
        "email": "juan.perez@ejemplo.cr",
        "notes": "Cliente frecuente",
    },
    {
        "name": "María Rodríguez Vega",
        "phone": "8888-2222",
        "email": "maria.rodriguez@ejemplo.cr",
        "notes": None,
    },
]

# Vinculados por índice: vehículos[0] → clientes[0], vehículos[1] → clientes[1]
# vehicle_type_name hace referencia a uno de los VEHICLE_TYPES de arriba
VEHICLES = [
    {
        "brand": "Toyota",
        "model": "Corolla",
        "year": 2020,
        "plate": "ABC-123",
        "vehicle_type_name": "Sedán",
        "customer_index": 0,
    },
    {
        "brand": "Suzuki",
        "model": "Jimny",
        "year": 2022,
        "plate": "XYZ-789",
        "vehicle_type_name": "4x4",
        "customer_index": 1,
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print(msg: str, ok: bool = True) -> None:
    status = "  [OK]" if ok else "  [--]"
    print(f"{status} {msg}")


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

async def seed_currencies(session) -> dict[str, Currency]:
    """Returns a {code: Currency} map for later use."""
    result: dict[str, Currency] = {}
    for data in CURRENCIES:
        existing = await session.scalar(
            select(Currency).where(Currency.code == data["code"])
        )
        if existing:
            _print(f"Currency '{data['code']}' ya existe — omitiendo.", ok=False)
            result[data["code"]] = existing
        else:
            currency = Currency(id=uuid.uuid4(), **data)
            session.add(currency)
            await session.flush()
            _print(f"Currency '{data['code']}' creada.")
            result[data["code"]] = currency
    return result


async def seed_vehicle_types(session) -> dict[str, VehicleType]:
    """Returns a {name: VehicleType} map for later use."""
    result: dict[str, VehicleType] = {}
    for name in VEHICLE_TYPES:
        existing = await session.scalar(
            select(VehicleType).where(VehicleType.name == name)
        )
        if existing:
            _print(f"VehicleType '{name}' ya existe — omitiendo.", ok=False)
            result[name] = existing
        else:
            vt = VehicleType(id=uuid.uuid4(), name=name)
            session.add(vt)
            await session.flush()
            _print(f"VehicleType '{name}' creado.")
            result[name] = vt
    return result


async def seed_customers(session) -> list[Customer]:
    """Returns the Customer list (existing or newly created) in order."""
    result: list[Customer] = []
    for data in CUSTOMERS:
        existing = await session.scalar(
            select(Customer).where(Customer.phone == data["phone"])
        )
        if existing:
            _print(f"Customer '{data['name']}' ya existe — omitiendo.", ok=False)
            result.append(existing)
        else:
            customer = Customer(id=uuid.uuid4(), **data)
            session.add(customer)
            await session.flush()
            _print(f"Customer '{data['name']}' creado.")
            result.append(customer)
    return result


async def seed_vehicles(
    session,
    customers: list[Customer],
    vehicle_types: dict[str, VehicleType],
) -> None:
    for data in VEHICLES:
        existing = await session.scalar(
            select(Vehicle).where(Vehicle.plate == data["plate"])
        )
        if existing:
            _print(f"Vehicle placa '{data['plate']}' ya existe — omitiendo.", ok=False)
            continue

        customer = customers[data["customer_index"]]
        vtype = vehicle_types.get(data["vehicle_type_name"])

        vehicle = Vehicle(
            id=uuid.uuid4(),
            customer_id=customer.id,
            vehicle_type_id=vtype.id if vtype else None,
            brand=data["brand"],
            model=data["model"],
            year=data["year"],
            plate=data["plate"],
        )
        session.add(vehicle)
        await session.flush()
        _print(f"Vehicle '{data['brand']} {data['model']}' placa '{data['plate']}' creado.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_seed() -> None:
    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  MicroTaller — Seed Data")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    async with AsyncSessionLocal() as session:
        try:
            print("\n[ Currencies ]")
            await seed_currencies(session)

            print("\n[ Vehicle Types ]")
            vehicle_types = await seed_vehicle_types(session)

            print("\n[ Customers ]")
            customers = await seed_customers(session)

            print("\n[ Vehicles ]")
            await seed_vehicles(session, customers, vehicle_types)

            await session.commit()
            print()
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print("  [OK] Seed completado exitosamente.")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print()
        except Exception:
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(run_seed())

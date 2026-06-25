# Core Mobile — Banco Andino (FastAPI)

Capa operacional de canales moviles. La consumen la **app Flutter de fuerza de
ventas** y la **app de clientes (appbanco_s8)**. Alimenta al nucleo
`bd_core_financiero` via servicio de promocion (tabla `sync_outbox`).

- DB: `bd_core_mobile` (PostgreSQL) · Puerto API: **8003**
- Stack: FastAPI · SQLAlchemy 2 · JWT (python-jose) · bcrypt (passlib)

## Puesta en marcha

```powershell
# 1) Entorno virtual
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 2) Crear el esquema en la BD (ya creada en PostgreSQL)
psql -U postgres -d bd_core_mobile -f sql/01_schema_bd_core_mobile.sql

# 3) Datos demo (asesor 0001 / clave 1234)
python -m scripts.seed_bd_core_mobile

# 4) Levantar el API (escuchando en toda la red para que el telefono lo alcance)
uvicorn main:app --reload --host 0.0.0.0 --port 8003
```

Docs interactivas: http://localhost:8003/docs

### Acceso desde el telefono fisico
- PC y telefono en la **misma red WiFi**.
- La app Flutter apunta a `http://192.168.1.35:8003` (IP LAN de la PC; ver
  `lib/core/network/api_client.dart`). Si tu IP cambia, actualiza ese valor.
- Abrir el puerto 8003 en el Firewall de Windows (una sola vez, como admin):
  ```powershell
  netsh advfirewall firewall add rule name="FastAPI Mobile 8003" ^
    dir=in action=allow protocol=TCP localport=8003
  ```

## Endpoints (slice inicial: Auth + Cartera)

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| POST | `/auth/login` | Login del asesor (codigo_empleado + password) -> JWT |
| GET  | `/cartera` | Cartera del dia del asesor autenticado (Bearer token) |
| POST | `/cartera/{id}/visita` | Registrar resultado de visita |

### Prueba rapida
```bash
# login
curl -X POST http://localhost:8003/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"codigo_empleado\":\"0001\",\"password\":\"1234\"}"

# cartera (usar el access_token devuelto)
curl http://localhost:8003/cartera -H "Authorization: Bearer <TOKEN>"
```

## Estructura
```
app/
  core/        cfg_config, cfg_database, cfg_security, cfg_auth
  models/      mdl_asesores, mdl_clientes, mdl_cartera  (SQLAlchemy)
  schemas/     sch_auth, sch_cartera                    (Pydantic)
  repositories/rep_asesores, rep_cartera
  controllers/ ctl_auth
  routes/      rtr_auth, rtr_cartera
sql/           01_schema_bd_core_mobile.sql
scripts/       seed_bd_core_mobile.py
```

## Pendiente (siguientes etapas)
- Modulos M2–M11 (solicitudes, documentos, buro, cobranza, reportes).
- Tablas espejo `cr_*` (sync core -> mobile) y servicio de promocion `sync_outbox` -> core.
- Endpoints para la app de clientes (cuentas, tarjetas, prestamos, movimientos).
- Migrar la capa de datos de la app Flutter de Supabase a REST contra este API.

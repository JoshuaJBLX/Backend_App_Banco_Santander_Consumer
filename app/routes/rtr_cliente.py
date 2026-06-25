from typing import Optional
"""
Rutas de la **app de clientes** (appbanco / Flutter clientes).

Login con DNI (usuarios_cliente) y consulta de productos del cliente
autenticado: cuentas de ahorro, créditos + cronograma, movimientos,
tarjetas y notificaciones. Todas (excepto login) requieren Bearer token.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.cfg_database import get_db
from app.core.cfg_auth import get_current_cliente
from app.schemas.sch_cliente import (
    LoginClienteIn, TokenClienteOut, ClienteOut, CuentaAhorroOut, CreditoOut,
    CuotaOut, MovimientoOut, TarjetaOut, NotificacionOut, OperacionIn, OperacionOut,
    SolicitudClienteIn, SolicitudClienteOut,
)
from app.controllers import ctl_auth_cliente
from app.repositories import rep_cliente

router = APIRouter()


@router.post("/login", response_model=TokenClienteOut)
def login(data: LoginClienteIn, db: Session = Depends(get_db)):
    """Login del cliente (numero_documento + password) -> JWT."""
    result = ctl_auth_cliente.login(db, data.numero_documento, data.password)
    if result and result.get("_bloqueado"):
        raise HTTPException(status_code=423, detail="Usuario bloqueado por intentos fallidos")
    if not result:
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    return result


@router.get("/perfil", response_model=ClienteOut)
def perfil(db: Session = Depends(get_db), cli: dict = Depends(get_current_cliente)):
    cliente = rep_cliente.get_cliente(db, cli["cliente_id"])
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente


@router.get("/cuentas", response_model=list[CuentaAhorroOut])
def cuentas(db: Session = Depends(get_db), cli: dict = Depends(get_current_cliente)):
    return rep_cliente.cuentas_ahorro(db, cli["cliente_id"])


@router.get("/creditos", response_model=list[CreditoOut])
def creditos(db: Session = Depends(get_db), cli: dict = Depends(get_current_cliente)):
    return rep_cliente.creditos(db, cli["cliente_id"])


@router.get("/creditos/{cod_cuenta_credito}/cronograma", response_model=list[CuotaOut])
def cronograma(
    cod_cuenta_credito: str,
    db: Session = Depends(get_db),
    cli: dict = Depends(get_current_cliente),
):
    return rep_cliente.cronograma(db, cod_cuenta_credito)


@router.get("/movimientos", response_model=list[MovimientoOut])
def movimientos(
    limit: int = 20,
    db: Session = Depends(get_db),
    cli: dict = Depends(get_current_cliente),
):
    return rep_cliente.movimientos(db, cli["cliente_id"], limit)


@router.get("/tarjetas", response_model=list[TarjetaOut])
def tarjetas(db: Session = Depends(get_db), cli: dict = Depends(get_current_cliente)):
    return rep_cliente.tarjetas(db, cli["cliente_id"])


@router.get("/notificaciones", response_model=list[NotificacionOut])
def notificaciones(db: Session = Depends(get_db), cli: dict = Depends(get_current_cliente)):
    return rep_cliente.notificaciones(db, cli["cliente_id"])


@router.post("/operaciones", response_model=OperacionOut)
def crear_operacion(
    data: OperacionIn,
    db: Session = Depends(get_db),
    cli: dict = Depends(get_current_cliente),
):
    """Registra una operación iniciada por el cliente (transferencia / pago)."""
    return rep_cliente.crear_operacion(db, cli["cliente_id"], data.model_dump())


@router.post("/solicitudes", response_model=SolicitudClienteOut)
def crear_solicitud(
    data: SolicitudClienteIn,
    db: Session = Depends(get_db),
    cli: dict = Depends(get_current_cliente),
):
    """Permite al cliente registrar una solicitud de crédito (E2E Paso 1)."""
    return rep_cliente.crear_solicitud_cliente(db, cli["cliente_id"], data.model_dump())



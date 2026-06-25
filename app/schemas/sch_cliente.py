from typing import Optional
"""Schemas Pydantic del lado app de clientes."""
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict


# ── Autenticación ──────────────────────────────────────────────
class LoginClienteIn(BaseModel):
    numero_documento: str   # DNI (= usuarios_cliente.username)
    password: str


class ClienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    cod_cliente: Optional[str] = None
    numero_documento: str
    nombres: str
    apellidos: str
    email: Optional[str] = None
    telefono: Optional[str] = None


class TokenClienteOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    cliente: ClienteOut


# ── Productos ──────────────────────────────────────────────────
class CuentaAhorroOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    cod_cuenta_ahorro: str
    tipo_cuenta: Optional[str] = None
    moneda: Optional[str] = None
    saldo_capital: Optional[float] = None
    saldo_interes: Optional[float] = None
    tea: Optional[float] = None
    estado: Optional[str] = None


class CreditoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    cod_cuenta_credito: str
    producto: Optional[str] = None
    monto_desembolsado: Optional[float] = None
    saldo_capital: Optional[float] = None
    saldo_total: Optional[float] = None
    dias_mora: int = 0
    calificacion_interna: Optional[str] = None
    estado: Optional[str] = None
    fecha_desembolso: Optional[date] = None
    tea: Optional[float] = None
    cuotas_total: Optional[int] = None
    cuotas_pagadas: Optional[int] = None


class CuotaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    cod_cuenta_credito: str
    nro_cuota: int
    fecha_vencimiento: date
    monto_cuota: Optional[float] = None
    monto_capital: Optional[float] = None
    monto_interes: Optional[float] = None
    saldo: Optional[float] = None
    estado_cuota: Optional[str] = None
    fecha_pago: Optional[date] = None


class MovimientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    cod_operacion: str
    cod_cuenta: Optional[str] = None
    tipo: Optional[str] = None      # DEB / CRE / TRF
    concepto: Optional[str] = None
    canal: Optional[str] = None
    monto: float
    moneda: Optional[str] = None
    fecha_operacion: datetime


class TarjetaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    numero_enmascarado: str
    marca: Optional[str] = None
    linea_credito: Optional[float] = None
    saldo_utilizado: Optional[float] = None
    fecha_corte: Optional[date] = None
    fecha_pago: Optional[date] = None
    estado: Optional[str] = None


class NotificacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    titulo: str
    cuerpo: Optional[str] = None
    tipo: Optional[str] = None
    leida: bool = False
    created_at: datetime


# ── Operaciones iniciadas por el cliente ───────────────────────
class OperacionIn(BaseModel):
    cod_cuenta_origen: str
    cod_cuenta_destino: Optional[str] = None
    tipo: str   # pago_cuota / transferencia / recarga
    monto: float
    moneda: str = "PEN"


class OperacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    cod_cuenta_origen: Optional[str] = None
    cod_cuenta_destino: Optional[str] = None
    tipo: Optional[str] = None
    monto: float
    moneda: Optional[str] = None
    estado: str
    created_at: datetime


# ── Solicitudes de crédito por el cliente ──────────────────
class SolicitudClienteIn(BaseModel):
    monto_solicitado: float
    plazo_meses: int
    destino_credito: str
    garantia: Optional[str] = "sin_garantia"


class SolicitudClienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    numero_expediente: Optional[str] = None
    estado: str
    canal: str
    monto_solicitado: float
    plazo_meses: int
    destino_credito: Optional[str] = None
    garantia: Optional[str] = None



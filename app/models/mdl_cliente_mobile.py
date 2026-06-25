from typing import Optional
"""
Modelos SQLAlchemy del lado **app de clientes** (appbanco / Flutter clientes).

Mapean las tablas ya existentes en bd_core_mobile:
usuarios_cliente, cr_cuentas_ahorro, cr_creditos, cr_cronograma_pagos,
cr_movimientos, tarjetas, operaciones_cliente, notificaciones.
"""
import uuid
from sqlalchemy import (
    Column, String, Boolean, Integer, Numeric, Date, DateTime, Text, ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.core.cfg_database import Base


class UsuarioCliente(Base):
    __tablename__ = "usuarios_cliente"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_id        = Column(UUID(as_uuid=True), ForeignKey("clientes.id"), nullable=False, unique=True)
    username          = Column(String(50), unique=True, nullable=False)  # = numero_documento (DNI)
    password_hash     = Column(Text, nullable=False)
    token_fcm         = Column(Text)
    activo            = Column(Boolean, nullable=False, default=True)
    bloqueado         = Column(Boolean, nullable=False, default=False)
    intentos_fallidos = Column(Integer, nullable=False, default=0)
    ultimo_acceso     = Column(DateTime(timezone=True))
    created_at        = Column(DateTime(timezone=True), server_default=func.now())


class CrCuentaAhorro(Base):
    __tablename__ = "cr_cuentas_ahorro"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cod_cuenta_ahorro = Column(String(30), unique=True, nullable=False)
    cliente_id        = Column(UUID(as_uuid=True), ForeignKey("clientes.id"), nullable=False)
    tipo_cuenta       = Column(String(40))
    moneda            = Column(String(3), default="PEN")
    saldo_capital     = Column(Numeric(12, 2))
    saldo_interes     = Column(Numeric(12, 2))
    tea               = Column(Numeric(5, 2))
    estado            = Column(String(20))
    sync_at           = Column(DateTime(timezone=True), server_default=func.now())


class CrCredito(Base):
    __tablename__ = "cr_creditos"

    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cod_cuenta_credito   = Column(String(30), unique=True, nullable=False)
    cliente_id           = Column(UUID(as_uuid=True), ForeignKey("clientes.id"), nullable=False)
    producto             = Column(String(40))
    monto_desembolsado   = Column(Numeric(12, 2))
    saldo_capital        = Column(Numeric(12, 2))
    saldo_total          = Column(Numeric(12, 2))
    dias_mora            = Column(Integer, nullable=False, default=0)
    calificacion_interna = Column(String(20))
    estado               = Column(String(20))
    fecha_desembolso     = Column(Date)
    tea                  = Column(Numeric(5, 2))
    cuotas_total         = Column(Integer)
    cuotas_pagadas       = Column(Integer)
    sync_at              = Column(DateTime(timezone=True), server_default=func.now())


class CrCronogramaPago(Base):
    __tablename__ = "cr_cronograma_pagos"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cod_cuenta_credito = Column(String(30), ForeignKey("cr_creditos.cod_cuenta_credito"), nullable=False)
    nro_cuota          = Column(Integer, nullable=False)
    fecha_vencimiento  = Column(Date, nullable=False)
    monto_cuota        = Column(Numeric(10, 2))
    monto_capital      = Column(Numeric(10, 2))
    monto_interes      = Column(Numeric(10, 2))
    saldo              = Column(Numeric(12, 2))
    estado_cuota       = Column(String(20))
    fecha_pago         = Column(Date)
    sync_at            = Column(DateTime(timezone=True), server_default=func.now())


class CrMovimiento(Base):
    __tablename__ = "cr_movimientos"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cod_operacion   = Column(String(40), unique=True, nullable=False)
    cliente_id      = Column(UUID(as_uuid=True), ForeignKey("clientes.id"), nullable=False)
    cod_cuenta      = Column(String(30))
    tipo            = Column(String(10))   # DEB / CRE / TRF
    concepto        = Column(String(60))
    canal           = Column(String(20))   # APP / WEB / CAJA
    monto           = Column(Numeric(12, 2), nullable=False)
    moneda          = Column(String(3), default="PEN")
    fecha_operacion = Column(DateTime(timezone=True), nullable=False)
    sync_at         = Column(DateTime(timezone=True), server_default=func.now())


class Tarjeta(Base):
    __tablename__ = "tarjetas"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_id         = Column(UUID(as_uuid=True), ForeignKey("clientes.id"), nullable=False)
    numero_enmascarado = Column(String(25), nullable=False)
    marca              = Column(String(20))
    linea_credito      = Column(Numeric(12, 2))
    saldo_utilizado    = Column(Numeric(12, 2))
    fecha_corte        = Column(Date)
    fecha_pago         = Column(Date)
    estado             = Column(String(20), default="activa")
    created_at         = Column(DateTime(timezone=True), server_default=func.now())


class OperacionCliente(Base):
    __tablename__ = "operaciones_cliente"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_id         = Column(UUID(as_uuid=True), ForeignKey("clientes.id"), nullable=False)
    cod_cuenta_origen  = Column(String(30))
    cod_cuenta_destino = Column(String(30))
    tipo               = Column(String(20))  # pago_cuota / transferencia / recarga
    monto              = Column(Numeric(12, 2), nullable=False)
    moneda             = Column(String(3), default="PEN")
    estado             = Column(String(20), nullable=False, default="pendiente")
    cod_operacion_core = Column(String(40))
    created_at         = Column(DateTime(timezone=True), server_default=func.now())


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    destinatario_tipo = Column(String(10), nullable=False)  # asesor / cliente
    asesor_id         = Column(UUID(as_uuid=True), ForeignKey("asesores.id"))
    cliente_id        = Column(UUID(as_uuid=True), ForeignKey("clientes.id"))
    titulo            = Column(String(120), nullable=False)
    cuerpo            = Column(Text)
    tipo              = Column(String(40))
    data_json         = Column(JSONB)
    leida             = Column(Boolean, nullable=False, default=False)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())


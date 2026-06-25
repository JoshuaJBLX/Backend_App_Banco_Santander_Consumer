from typing import Optional
import uuid
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.cfg_database import Base

class Agencia(Base):
    __tablename__ = "agencias"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cod_agencia = Column(String(20), unique=True, nullable=False)
    nombre      = Column(String(100), nullable=False)
    region      = Column(String(50))
    activa      = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

class Asesor(Base):
    __tablename__ = "asesores"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cod_asesor        = Column(String(20), unique=True)
    codigo_empleado   = Column(String(10), unique=True, nullable=False)
    nombres           = Column(String(100), nullable=False)
    apellidos         = Column(String(100), nullable=False)
    agencia_id        = Column(UUID(as_uuid=True), ForeignKey("agencias.id"))
    perfil            = Column(String(20), nullable=False, default="operador")
    password_hash     = Column(String, nullable=False)
    token_fcm         = Column(String)
    intentos_fallidos = Column(Integer, default=0)
    bloqueado_hasta   = Column(DateTime(timezone=True))
    activo            = Column(Boolean, default=True)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())


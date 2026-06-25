from typing import Optional
import uuid
from sqlalchemy import Column, String, Boolean, Integer, Date, Numeric, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.cfg_database import Base

class Cliente(Base):
    __tablename__ = "clientes"

    id                       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cod_cliente              = Column(String(20), unique=True)
    numero_documento         = Column(String(15), unique=True, nullable=False)
    tipo_documento           = Column(String(5), default="DNI")
    nombres                  = Column(String(100), nullable=False)
    apellidos                = Column(String(100), nullable=False)
    fecha_nacimiento         = Column(Date)
    estado_civil             = Column(String(15))
    telefono                 = Column(String(15))
    email                    = Column(String(100))
    direccion                = Column(String)
    tipo_negocio             = Column(String(30))
    nombre_negocio           = Column(String(100))
    antiguedad_negocio_meses = Column(Integer)
    ingresos_estimados       = Column(Numeric(12, 2))
    lat                      = Column(Numeric(10, 7))
    lng                      = Column(Numeric(10, 7))
    calificacion_sbs         = Column(String(15))
    es_prospecto             = Column(Boolean, default=False)
    created_at               = Column(DateTime(timezone=True), server_default=func.now())
    updated_at               = Column(DateTime(timezone=True), server_default=func.now())


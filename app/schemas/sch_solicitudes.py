from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SolicitudIn(BaseModel):
    # Solicitante / negocio
    numero_documento: str
    nombres: str = ""
    apellidos: str = ""
    telefono: Optional[str] = None
    tipo_negocio: Optional[str] = None
    nombre_negocio: Optional[str] = None
    ingresos_estimados: Optional[float] = None
    # Condiciones
    monto_solicitado: float
    plazo_meses: int
    moneda: str = "PEN"
    tipo_cuota: str = "mensual"
    garantia: str = "sin_garantia"
    destino_credito: Optional[str] = None
    cuota_estimada: Optional[float] = None
    tea_referencial: Optional[float] = None
    firma_cliente_base64: Optional[str] = None


class SolicitudCreada(BaseModel):
    id: str
    numero_expediente: str
    estado: str


class SolicitudResumen(BaseModel):
    id: str
    numero_expediente: str
    cliente_nombre: str
    monto_solicitado: float
    monto_aprobado: float
    estado: str
    created_at: Optional[str] = None


class DocumentoIn(BaseModel):
    tipo_documento: str
    storage_url: str
    tamanio_kb: Optional[int] = None
    nitidez_score: Optional[float] = None


class DocumentoRequest(BaseModel):
    """Payload para adjuntar documento a una solicitud."""
    solicitud_id: str
    tipo_documento: str
    storage_url: str
    tamanio_kb: Optional[float] = None


class FirmaRequest(BaseModel):
    """Payload para capturar firma del cliente."""
    solicitud_id: str
    firma_base64: str


class DecisionRequest(BaseModel):
    """Payload para registrar decision del comite."""
    decision: str  # APROBADO / CONDICIONADO / RECHAZADO
    monto_aprobado: Optional[float] = None
    condicion_adicional: Optional[str] = None
    motivo_rechazo: Optional[str] = None


class DesembolsoRequest(BaseModel):
    """Payload para registrar desembolso y generar cronograma."""
    fecha_desembolso: Optional[str] = None  # YYYY-MM-DD; default hoy


class DecisionComiteIn(BaseModel):
    decision: str  # aprobado / condicionado / rechazado
    motivo_rechazo: Optional[str] = None
    condicion_adicional: Optional[str] = None
    tiene_seguro: bool = True


class FirmaIn(BaseModel):
    firma_cliente_base64: str


from pydantic import BaseModel
from typing import Optional


class UbicacionIn(BaseModel):
    """Coordenadas del negocio del cliente (HU-10 / RF-25/26)."""
    lat: float
    lng: float
    direccion: Optional[str] = None


class ClienteFicha(BaseModel):
    id: str
    numero_documento: str
    nombres: str
    apellidos: str
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    tipo_negocio: Optional[str] = None
    nombre_negocio: Optional[str] = None
    antiguedad_negocio_meses: Optional[int] = None
    calificacion_sbs: str = "NORMAL"


class PosicionCliente(BaseModel):
    deuda_total: float
    cuentas_vigentes: int
    cuentas_mora: int
    dias_mayor_mora: int


class CreditoHistorial(BaseModel):
    producto: Optional[str] = None
    monto_desembolsado: float
    plazo_meses: Optional[int] = None
    tea: float
    estado: Optional[str] = None
    dias_mora: int
    cuotas_total: int
    cuotas_pagadas: int


class OfertaPreaprobada(BaseModel):
    monto_maximo: float
    plazo_sugerido_meses: Optional[int] = None
    tea_referencial: float
    score_confianza: int
    fecha_vencimiento: Optional[str] = None


class IndicadoresComportamiento(BaseModel):
    pct_puntual: float
    dias_prom_mora: int
    monto_pagado: float


class FichaOut(BaseModel):
    cliente: ClienteFicha
    posicion: PosicionCliente
    historial: list[CreditoHistorial]
    oferta: Optional[OfertaPreaprobada] = None
    comportamiento: list[int] = []
    indicadores: Optional[IndicadoresComportamiento] = None


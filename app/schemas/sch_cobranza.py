from pydantic import BaseModel
from typing import Optional


class MoraItemOut(BaseModel):
    id: str
    cod_cuenta_credito: str
    cliente_id: str
    cliente_nombre: str
    documento: str
    telefono: Optional[str] = None
    dias_mora: int
    monto_vencido: float


class AccionCobranzaIn(BaseModel):
    cliente_id: str
    cod_cuenta_credito: Optional[str] = None
    tipo_gestion: str            # visita / llamada / mensaje
    resultado: str               # compromiso_pago / pago_parcial / sin_contacto / se_niega
    monto_pagado: Optional[float] = None
    fecha_compromiso: Optional[str] = None
    monto_compromiso: Optional[float] = None
    observaciones: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None


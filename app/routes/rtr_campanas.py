from datetime import date
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.cfg_database import get_db
from app.core.cfg_auth import get_current_asesor

router = APIRouter()


class CampanaOut(BaseModel):
    id: str
    cliente_id: str
    cliente_nombre: str
    tipo: Optional[str] = None
    monto_ofertado: float
    fecha_vencimiento: Optional[str] = None
    dias_restantes: int


@router.get("", response_model=list[CampanaOut])
def listar(
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Campanas activas del asesor, mas proximas a vencer primero (HU-16/RF-40)."""
    rows = db.execute(
        text(
            """
            SELECT ca.id, ca.cliente_id, ca.tipo, ca.monto_ofertado,
                   ca.fecha_vencimiento, c.nombres, c.apellidos
            FROM campanas_activas ca
            JOIN clientes c ON c.id = ca.cliente_id
            WHERE ca.asesor_id = :asesor AND ca.activa = TRUE
              AND (ca.fecha_vencimiento IS NULL OR ca.fecha_vencimiento >= :hoy)
            ORDER BY ca.fecha_vencimiento ASC NULLS LAST
            """
        ),
        {"asesor": asesor["asesor_id"], "hoy": date.today()},
    ).mappings().all()
    hoy = date.today()
    return [
        CampanaOut(
            id=str(r["id"]),
            cliente_id=str(r["cliente_id"]),
            cliente_nombre=f"{r['nombres']} {r['apellidos']}",
            tipo=r["tipo"],
            monto_ofertado=float(r["monto_ofertado"] or 0),
            fecha_vencimiento=r["fecha_vencimiento"].isoformat()
            if r["fecha_vencimiento"]
            else None,
            dias_restantes=(r["fecha_vencimiento"] - hoy).days
            if r["fecha_vencimiento"]
            else 0,
        )
        for r in rows
    ]


from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.cfg_database import get_db
from app.core.cfg_auth import get_current_asesor

router = APIRouter()


class ProductividadAsesor(BaseModel):
    asesor_nombre: str
    enviadas: int
    aprobadas: int
    desembolsadas: int
    monto_total: float
    tasa_aprobacion: float


@router.get("/productividad", response_model=list[ProductividadAsesor])
def productividad(
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Reporte de productividad mensual por asesor (M11 / RF-80)."""
    rows = db.execute(
        text(
            """
            SELECT a.nombres || ' ' || a.apellidos AS asesor_nombre,
                   COUNT(*)                                            AS enviadas,
                   COUNT(*) FILTER (WHERE s.estado IN ('aprobado','desembolsado')) AS aprobadas,
                   COUNT(*) FILTER (WHERE s.estado = 'desembolsado')   AS desembolsadas,
                   COALESCE(SUM(s.monto_solicitado), 0)                AS monto_total
            FROM solicitudes_credito s
            JOIN asesores a ON a.id = s.asesor_id
            WHERE date_trunc('month', s.created_at) = date_trunc('month', now())
            GROUP BY a.nombres, a.apellidos
            ORDER BY enviadas DESC
            """
        )
    ).mappings().all()
    return [
        ProductividadAsesor(
            asesor_nombre=r["asesor_nombre"],
            enviadas=r["enviadas"],
            aprobadas=r["aprobadas"],
            desembolsadas=r["desembolsadas"],
            monto_total=float(r["monto_total"]),
            tasa_aprobacion=round(
                (r["aprobadas"] / r["enviadas"] * 100) if r["enviadas"] else 0, 1
            ),
        )
        for r in rows
    ]


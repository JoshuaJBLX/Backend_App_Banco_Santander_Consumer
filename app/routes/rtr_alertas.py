from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.cfg_database import get_db
from app.core.cfg_auth import get_current_asesor

router = APIRouter()


class AlertaOut(BaseModel):
    id: str
    cliente_id: str
    cliente_nombre: str
    tipo_alerta: str
    mensaje: Optional[str] = None
    leida: bool


@router.get("", response_model=list[AlertaOut])
def listar(
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Alertas de cartera del asesor, no leidas primero (HU-14)."""
    rows = db.execute(
        text(
            """
            SELECT a.id, a.cliente_id, a.tipo_alerta, a.mensaje, a.leida,
                   c.nombres, c.apellidos
            FROM alertas_cartera a
            JOIN clientes c ON c.id = a.cliente_id
            WHERE a.asesor_id = :asesor
            ORDER BY a.leida ASC, a.created_at DESC
            """
        ),
        {"asesor": asesor["asesor_id"]},
    ).mappings().all()
    return [
        AlertaOut(
            id=str(r["id"]),
            cliente_id=str(r["cliente_id"]),
            cliente_nombre=f"{r['nombres']} {r['apellidos']}",
            tipo_alerta=r["tipo_alerta"],
            mensaje=r["mensaje"],
            leida=r["leida"],
        )
        for r in rows
    ]


@router.get("/no-leidas")
def no_leidas(
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Conteo de alertas no leidas (insignia, RF-36)."""
    n = db.execute(
        text(
            "SELECT COUNT(*) FROM alertas_cartera "
            "WHERE asesor_id = :a AND leida = FALSE"
        ),
        {"a": asesor["asesor_id"]},
    ).scalar()
    return {"no_leidas": n or 0}


@router.post("/{alerta_id}/leer")
def marcar_leida(
    alerta_id: str,
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    db.execute(
        text("UPDATE alertas_cartera SET leida = TRUE WHERE id = :id"),
        {"id": alerta_id},
    )
    db.commit()
    return {"status": "ok"}


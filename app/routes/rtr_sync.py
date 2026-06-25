from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.cfg_database import get_db
from app.core.cfg_auth import get_current_asesor
from app.services import svc_promocion

router = APIRouter()


@router.post("/promover")
def promover(
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Promueve las solicitudes pendientes al nucleo bancario (bd_core_financiero)."""
    return svc_promocion.promover(db)


@router.get("/outbox")
def outbox(
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Estado de la cola de sincronizacion al core."""
    rows = db.execute(
        text(
            """SELECT entidad, operacion, estado, core_ref, intentos, ultimo_error,
                      created_at, procesado_at
               FROM sync_outbox ORDER BY created_at DESC LIMIT 50"""
        )
    ).mappings().all()
    return [dict(r) for r in rows]


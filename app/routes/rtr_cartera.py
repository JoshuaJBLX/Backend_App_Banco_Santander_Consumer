from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.cfg_database import get_db
from app.core.cfg_auth import get_current_asesor
from app.schemas.sch_cartera import CarteraItemOut, MarcarVisitaIn
from app.repositories import rep_cartera

router = APIRouter()

@router.get("", response_model=list[CarteraItemOut])
def listar_cartera(
    fecha: Optional[date] = None,
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Cartera del dia del asesor autenticado (RF-04/RF-09)."""
    f = fecha or date.today()
    return rep_cartera.listar_por_asesor(db, asesor["asesor_id"], f)

@router.post("/{cartera_id}/visita")
def marcar_visita(
    cartera_id: str,
    data: MarcarVisitaIn,
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Registra el resultado de una visita (RF-07/RF-17)."""
    ok = rep_cartera.marcar_visita(db, asesor["asesor_id"], cartera_id, data.model_dump())
    if not ok:
        raise HTTPException(status_code=404, detail="Item de cartera no encontrado")
    return {"status": "ok", "cartera_id": cartera_id, "estado_visita": data.resultado}


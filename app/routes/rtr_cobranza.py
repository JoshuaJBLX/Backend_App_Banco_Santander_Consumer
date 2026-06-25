from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.cfg_database import get_db
from app.core.cfg_auth import get_current_asesor
from app.schemas.sch_cobranza import MoraItemOut, AccionCobranzaIn
from app.repositories import rep_cobranza

router = APIRouter()


@router.get("/mora", response_model=list[MoraItemOut])
def listar_mora(
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Listado de mora diaria (M10 / HU-30)."""
    return rep_cobranza.listar_mora(db)


@router.post("/accion")
def registrar_accion(
    data: AccionCobranzaIn,
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Registra una gestion de cobranza (M10 / HU-31)."""
    rep_cobranza.registrar_accion(db, asesor["asesor_id"], data.model_dump())
    return {"status": "ok"}


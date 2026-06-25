from typing import Optional
from sqlalchemy.orm import Session
from app.models.mdl_asesores import Asesor

def get_by_codigo(db: Session, codigo_empleado: str) -> Optional[Asesor]:
    return db.query(Asesor).filter(
        Asesor.codigo_empleado == codigo_empleado
    ).first()

def get_by_id(db: Session, asesor_id: str) -> Optional[Asesor]:
    return db.query(Asesor).filter(Asesor.id == asesor_id).first()


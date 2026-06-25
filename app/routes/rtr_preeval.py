from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.cfg_database import get_db
from app.core.cfg_auth import get_current_asesor
import uuid

router = APIRouter()


# ── Schema exacto que la App Fuerza de Ventas envia al presionar "Pre-evaluar" ──
class PreEvalIn(BaseModel):
    numero_documento: str          # la app envia "numero_documento"
    nombres: str = ""
    apellidos: str = ""
    fecha_nacimiento: Optional[str] = None
    tipo_negocio: str = ""
    antiguedad_negocio_meses: int = 0   # la app envia "antiguedad_negocio_meses"
    ingresos_estimados: float = 0       # la app envia "ingresos_estimados"
    monto_solicitado: float = 0
    destino_credito: str = ""


class PreEvalOut(BaseModel):
    apto: bool
    puntaje: int
    capacidad_pago: float = 0.0
    cuota: float = 0.0
    ratio: float = 0.0
    recomendacion: str = "Revisar"
    calificacion_sbs: str = "NORMAL"
    entidades_deuda: int = 0
    deuda_total: float = 0.0
    dias_mora: int = 0
    lista_negra: bool = False


# ── Perfiles SBS simulados por ultimo digito del DNI ──
_SBS_PROFILES = {
    0: ("NORMAL", 1, 4500.0, 0, False),
    1: ("NORMAL", 2, 12000.0, 0, False),
    2: ("CPP", 2, 18000.0, 15, False),
    3: ("NORMAL", 0, 0.0, 0, False),
    4: ("DUDOSO", 3, 25000.0, 95, False),
    5: ("DEFICIENTE", 2, 16000.0, 45, False),
    6: ("NORMAL", 1, 6000.0, 0, False),
    7: ("PERDIDA", 4, 40000.0, 210, True),
    8: ("CPP", 1, 9000.0, 20, False),
    9: ("NORMAL", 2, 14000.0, 0, False),
}

# ── Casos especiales por DNI exacto (para coincidir con los datos de prueba) ──
_CASOS_ESPECIALES = {
    "40550055": {"calificacion": "DEFICIENTE", "entidades": 2, "deuda": 16000.00, "dias": 45},
    "43880088": {"calificacion": "CPP", "entidades": 1, "deuda": 9000.00, "dias": 20},
    "41552052": {"calificacion": "CPP", "entidades": 2, "deuda": 18000.00, "dias": 15},
    "41888088": {"calificacion": "CPP", "entidades": 1, "deuda": 9000.00, "dias": 20},
    "42220022": {"calificacion": "CPP", "entidades": 2, "deuda": 18000.00, "dias": 15},
    "43337037": {"calificacion": "PERDIDA", "entidades": 4, "deuda": 40000.00, "dias": 210, "lista_negra": True},
    "41884084": {"calificacion": "DUDOSO", "entidades": 3, "deuda": 25000.00, "dias": 95},
    "43334034": {"calificacion": "DUDOSO", "entidades": 3, "deuda": 25000.00, "dias": 95},
}


def _obtener_calificacion_sbs(dni: str) -> dict:
    """Retorna calificacion SBS segun DNI (caso especial o ultimo digito)."""
    if dni in _CASOS_ESPECIALES:
        caso = _CASOS_ESPECIALES[dni]
        return {
            "calificacion_sbs": caso["calificacion"],
            "entidades_con_deuda": caso["entidades"],
            "deuda_total": caso["deuda"],
            "dias_mayor_mora": caso["dias"],
            "en_lista_negra": caso.get("lista_negra", False),
        }
    ultimo = int(dni[-1]) if dni and dni[-1].isdigit() else 0
    sbs, entidades, deuda, mora, lista_negra = _SBS_PROFILES.get(ultimo, _SBS_PROFILES[0])
    return {
        "calificacion_sbs": sbs,
        "entidades_con_deuda": entidades,
        "deuda_total": deuda,
        "dias_mayor_mora": mora,
        "en_lista_negra": lista_negra,
    }


# ── ENDPOINT PRINCIPAL: POST /pre-evaluar ──
@router.post("", response_model=PreEvalOut)
def pre_evaluar(
    data: PreEvalIn,
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """
    Pre-evaluacion crediticia (M4 / RF-38).
    - Busca cliente por numero_documento; si no existe, crea prospecto.
    - Obtiene la solicitud activa del cliente.
    - Consulta SBS (por DNI exacto o ultimo digito) y guarda en consultas_buro.
    - Calcula capacidad de pago y ratio cuota/ingresos.
    """
    # 1. Buscar o crear cliente
    cliente_row = db.execute(
        text("SELECT id, nombres, apellidos, ingresos_estimados FROM clientes WHERE numero_documento = :doc"),
        {"doc": data.numero_documento},
    ).first()

    if not cliente_row:
        # Crear cliente como prospecto
        cliente_id = str(uuid.uuid4())
        db.execute(
            text(
                """INSERT INTO clientes (id, numero_documento, nombres, apellidos,
                       tipo_negocio, antiguedad_negocio_meses, ingresos_estimados, es_prospecto)
                   VALUES (:id, :doc, :nom, :ape, :tn, :ant, :ing, TRUE)"""
            ),
            {
                "id": cliente_id,
                "doc": data.numero_documento,
                "nom": data.nombres,
                "ape": data.apellidos,
                "tn": data.tipo_negocio,
                "ant": data.antiguedad_negocio_meses,
                "ing": data.ingresos_estimados,
            },
        )
        db.commit()
        cliente_id_str = cliente_id
        ingresos_db = data.ingresos_estimados
    else:
        cliente_id_str = str(cliente_row[0])
        ingresos_db = float(cliente_row[3] or 0)

    # 2. Obtener solicitud activa del cliente
    solicitud_row = db.execute(
        text(
            """SELECT id, monto_solicitado, cuota_estimada,
                      asesor_id, estado
               FROM solicitudes_credito
               WHERE cliente_id = :cli
                 AND estado IN ('enviado', 'recibido_comite', 'en_evaluacion')
               ORDER BY created_at DESC
               LIMIT 1"""
        ),
        {"cli": cliente_id_str},
    ).first()

    solicitud_id = str(solicitud_row[0]) if solicitud_row else None
    # Usar ingresos del payload (vienen del formulario en la app)
    ingresos = data.ingresos_estimados if data.ingresos_estimados > 0 else ingresos_db

    # 3. Calcular capacidad de pago
    # gatos_mensuales no existe en BD, se asume 0 (la capacidad se evalua solo con ingresos)
    capacidad_pago = ingresos

    # 4. Obtener cuota estimada
    cuota = float(solicitud_row[2] or 0) if solicitud_row else (
        data.monto_solicitado * 0.05  # estimacion simple si no hay cuota
    )
    if cuota <= 0:
        cuota = data.monto_solicitado * 0.05

    # 5. Calcular ratio
    ratio = (cuota / capacidad_pago) * 100 if capacidad_pago > 0 else 999

    # 6. Determinar aptitud
    apto = ratio < 30
    puntaje = 85 if apto else 60

    # 7. Consultar SBS
    sbs = _obtener_calificacion_sbs(data.numero_documento)

    # 8. Guardar en consultas_buro
    consulta_id = str(uuid.uuid4())
    asesor_id = asesor["asesor_id"]
    db.execute(
        text(
            """INSERT INTO consultas_buro
                 (id, asesor_id, cliente_id, solicitud_id, dni_consultado,
                  calificacion_sbs, entidades_con_deuda, deuda_total_pen,
                  mayor_deuda, dias_mayor_mora, en_lista_negra)
               VALUES
                 (:id, :asesor, :cli, :sol, :dni, :sbs, :ent, :deuda,
                  :mayor, :mora, :ln)"""
        ),
        {
            "id": consulta_id,
            "asesor": asesor_id,
            "cli": cliente_id_str,
            "sol": solicitud_id,
            "dni": data.numero_documento,
            "sbs": sbs["calificacion_sbs"],
            "ent": sbs["entidades_con_deuda"],
            "deuda": sbs["deuda_total"],
            "mayor": sbs["deuda_total"],
            "mora": sbs["dias_mayor_mora"],
            "ln": sbs["en_lista_negra"],
        },
    )

    # 9. Actualizar estado de la solicitud si existe
    if solicitud_id:
        db.execute(
            text("UPDATE solicitudes_credito SET estado = 'recibido_comite', updated_at = now() WHERE id = :id"),
            {"id": solicitud_id},
        )

    db.commit()

    return PreEvalOut(
        apto=apto,
        puntaje=puntaje,
        capacidad_pago=round(capacidad_pago, 2),
        cuota=round(cuota, 2),
        ratio=round(ratio, 2),
        recomendacion="Aprobado" if apto else "Revisar",
        calificacion_sbs=sbs["calificacion_sbs"],
        entidades_deuda=sbs["entidades_con_deuda"],
        deuda_total=sbs["deuda_total"],
        dias_mora=sbs["dias_mayor_mora"],
        lista_negra=sbs["en_lista_negra"],
    )
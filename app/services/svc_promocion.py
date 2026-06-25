from typing import Optional
"""
Puente bd_core_mobile -> bd_core_financiero (nucleo bancario).

Lee la cola sync_outbox (solicitudes creadas en campo) y las PROMUEVE al core:
crea/ubica dcliente y registra dsolicitud (estado "En Evaluacion"). Reutiliza
valores de FK validos del core para no romper la integridad referencial.
"""
from datetime import date, datetime, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.cfg_database import SessionLocalCore

# FKs de referencia (existentes en bd_core_financiero):
_PK_CLASE_PERSONA = 3            # Persona Natural con Negocio
_COD_CLASE = "03"
_DES_CLASE = "Persona Natural con Negocio"
_PK_TIPO_DOC = 1                 # DNI
_COD_TIPO_DOC = "01"
_DES_TIPO_DOC = "DNI"
_PK_ESTADO_EVALUACION = 1        # En Evaluacion
_PK_MONEDA = 1                   # PEN
_PK_PRODUCTO = 1
_PK_AGENCIA = 64
_PK_ASESOR = 70


def _upsert_dcliente(core: Session, p: dict) -> int:
    doc = p["numero_documento"]
    row = core.execute(
        text("SELECT pkcliente FROM dcliente WHERE numerodocumentoidentidad = :d"),
        {"d": doc},
    ).first()
    if row:
        return int(row[0])

    nombre = f"{p.get('nombres', '')} {p.get('apellidos', '')}".strip()[:100]
    pk = core.execute(
        text(
            """
            INSERT INTO dcliente
              (codcliente, nomcliente, pkclasepersona, codclasepersona,
               desclasepersona, fechaingresocaja, pktipodocumentoidentidad,
               codtipodocumentoidentidad, destipodocumentoidentidad,
               numerodocumentoidentidad)
            VALUES
              (:cod, :nom, :pkclase, :codclase, :desclase, :fec, :pktipo,
               :codtipo, :destipo, :doc)
            RETURNING pkcliente
            """
        ),
        {
            "cod": ("MOB" + doc)[:12],
            "nom": nombre or "Cliente Movil",
            "pkclase": _PK_CLASE_PERSONA,
            "codclase": _COD_CLASE,
            "desclase": _DES_CLASE,
            "fec": date.today(),
            "pktipo": _PK_TIPO_DOC,
            "codtipo": _COD_TIPO_DOC,
            "destipo": _DES_TIPO_DOC,
            "doc": doc,
        },
    ).scalar()
    return int(pk)


def _insert_dsolicitud(core: Session, pkcliente: int, p: dict, entidad_id: str) -> str:
    cod = ("SOLM" + entidad_id.replace("-", "")[:8]).upper()[:20]
    plazo = int(p.get("plazo_meses", 12))
    core.execute(
        text(
            """
            INSERT INTO dsolicitud
              (codsolicitud, pkcliente, pksolicitudestado, pkmoneda, pkproducto,
               montosolicitudcredito, nrocuotasolicitud, plazosolicitudcredito,
               fechasolicitudcredito, pkagencia, pkasesor)
            VALUES
              (:cod, :cli, :estado, :moneda, :producto, :monto, :cuotas,
               :plazo, :fecha, :agencia, :asesor)
            """
        ),
        {
            "cod": cod,
            "cli": pkcliente,
            "estado": _PK_ESTADO_EVALUACION,
            "moneda": _PK_MONEDA,
            "producto": _PK_PRODUCTO,
            "monto": float(p.get("monto_solicitado", 0)),
            "cuotas": plazo,
            "plazo": plazo,
            "fecha": date.today(),
            "agencia": _PK_AGENCIA,
            "asesor": _PK_ASESOR,
        },
    )
    return cod


def promover(db: Session) -> dict:
    """Procesa la cola sync_outbox pendiente. Devuelve conteos."""
    pendientes = db.execute(
        text(
            """SELECT id, entidad_id, payload FROM sync_outbox
               WHERE estado = 'pendiente' AND entidad = 'solicitudes_credito'
               ORDER BY created_at"""
        )
    ).mappings().all()

    aplicados, errores = 0, 0
    core = SessionLocalCore()
    try:
        for o in pendientes:
            p = o["payload"]  # JSONB -> dict
            try:
                pkcliente = _upsert_dcliente(core, p)
                cod = _insert_dsolicitud(core, pkcliente, p, str(o["entidad_id"]))
                core.commit()
                db.execute(
                    text(
                        """UPDATE sync_outbox SET estado='aplicado', core_ref=:ref,
                           procesado_at=:ts WHERE id=:id"""
                    ),
                    {"ref": cod, "ts": datetime.now(timezone.utc), "id": o["id"]},
                )
                db.execute(
                    text(
                        "UPDATE solicitudes_credito SET cod_solicitud_core=:ref "
                        "WHERE id=:eid"
                    ),
                    {"ref": cod, "eid": o["entidad_id"]},
                )
                db.execute(
                    text(
                        """INSERT INTO sync_log (id, direccion, entidad, referencia, resultado, detalle)
                           VALUES (gen_random_uuid(),'mobile_a_core','solicitudes_credito',:ref,'ok','Promovida al core')"""
                    ),
                    {"ref": cod},
                )
                db.commit()
                aplicados += 1
            except Exception as e:  # noqa: BLE001
                core.rollback()
                db.execute(
                    text(
                        """UPDATE sync_outbox SET estado='error', intentos=intentos+1,
                           ultimo_error=:err WHERE id=:id"""
                    ),
                    {"err": str(e)[:500], "id": o["id"]},
                )
                db.execute(
                    text(
                        """INSERT INTO sync_log (id, direccion, entidad, referencia, resultado, detalle)
                           VALUES (gen_random_uuid(),'mobile_a_core','solicitudes_credito',NULL,'error',:err)"""
                    ),
                    {"err": str(e)[:500]},
                )
                db.commit()
                errores += 1
    finally:
        core.close()
    return {"aplicados": aplicados, "errores": errores, "total": len(pendientes)}


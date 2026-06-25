from typing import Optional
import json
import uuid
import calendar
from datetime import date, datetime, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.cfg_database import SessionLocalCore
from app.services import svc_promocion



def _upsert_cliente(db: Session, d: dict) -> str:
    """Devuelve el cliente_id; lo crea si no existe (por numero_documento)."""
    row = db.execute(
        text("SELECT id FROM clientes WHERE numero_documento = :doc"),
        {"doc": d["numero_documento"]},
    ).first()
    if row:
        return str(row[0])
    cid = str(uuid.uuid4())
    db.execute(
        text(
            """INSERT INTO clientes (id, numero_documento, nombres, apellidos,
                   telefono, tipo_negocio, nombre_negocio, es_prospecto)
               VALUES (:id,:doc,:nom,:ape,:tel,:tn,:nn,TRUE)"""
        ),
        {
            "id": cid,
            "doc": d["numero_documento"],
            "nom": d.get("nombres", ""),
            "ape": d.get("apellidos", ""),
            "tel": d.get("telefono"),
            "tn": d.get("tipo_negocio"),
            "nn": d.get("nombre_negocio"),
        },
    )
    return cid


def crear(db: Session, asesor_id: str, agencia_id: Optional[str], d: dict) -> dict:
    """Crea una solicitud de credito (M5 / HU-17)."""
    cliente_id = _upsert_cliente(db, d)
    sol_id = str(uuid.uuid4())
    expediente = "EXP-" + sol_id.replace("-", "")[:8].upper()
    db.execute(
        text(
            """INSERT INTO solicitudes_credito
                 (id, numero_expediente, asesor_id, cliente_id, agencia_id,
                  canal, tipo_negocio, nombre_negocio, ingresos_estimados,
                  monto_solicitado, plazo_meses, moneda, tipo_cuota, garantia,
                  destino_credito, cuota_estimada, tea_referencial,
                  firma_cliente_base64, estado)
               VALUES
                 (:id,:exp,:asesor,:cli,:ag,'asesor',:tn,:nn,:ing,
                  :monto,:plazo,:mon,:tc,:gar,:dest,:cuota,:tea,:firma,'enviado')"""
        ),
        {
            "id": sol_id,
            "exp": expediente,
            "asesor": asesor_id,
            "cli": cliente_id,
            "ag": agencia_id,
            "tn": d.get("tipo_negocio"),
            "nn": d.get("nombre_negocio"),
            "ing": d.get("ingresos_estimados"),
            "monto": d["monto_solicitado"],
            "plazo": d["plazo_meses"],
            "mon": d.get("moneda", "PEN"),
            "tc": d.get("tipo_cuota", "mensual"),
            "gar": d.get("garantia", "sin_garantia"),
            "dest": d.get("destino_credito"),
            "cuota": d.get("cuota_estimada"),
            "tea": d.get("tea_referencial"),
            "firma": d.get("firma_cliente_base64"),
        },
    )

    # Encola para promover al nucleo bancario (puente sync_outbox -> core).
    payload = {
        "numero_documento": d["numero_documento"],
        "nombres": d.get("nombres", ""),
        "apellidos": d.get("apellidos", ""),
        "monto_solicitado": float(d["monto_solicitado"]),
        "plazo_meses": int(d["plazo_meses"]),
        "numero_expediente": expediente,
    }
    db.execute(
        text(
            """INSERT INTO sync_outbox (id, entidad, entidad_id, operacion, payload, estado)
               VALUES (:id, 'solicitudes_credito', :eid, 'create', CAST(:payload AS jsonb), 'pendiente')"""
        ),
        {
            "id": str(uuid.uuid4()),
            "eid": sol_id,
            "payload": json.dumps(payload),
        },
    )
    db.commit()
    return {"id": sol_id, "numero_expediente": expediente, "estado": "enviado"}


def agregar_nota(db: Session, solicitud_id: str, asesor_id: str, contenido: str) -> dict:
    """Agrega una nota interna a una solicitud (RF-72)."""
    nid = str(uuid.uuid4())
    db.execute(
        text(
            """INSERT INTO solicitudes_notas_internas
                 (id, solicitud_id, asesor_id, contenido)
               VALUES (:id,:sol,:asesor,:cont)"""
        ),
        {"id": nid, "sol": solicitud_id, "asesor": asesor_id, "cont": contenido[:500]},
    )
    db.commit()
    return {"id": nid}


def listar_notas(db: Session, solicitud_id: str) -> list[dict]:
    """Notas internas de una solicitud, recientes primero (RF-72)."""
    rows = db.execute(
        text(
            """SELECT contenido, created_at
               FROM solicitudes_notas_internas
               WHERE solicitud_id = :sol
               ORDER BY created_at DESC"""
        ),
        {"sol": solicitud_id},
    ).mappings().all()
    return [
        {
            "contenido": r["contenido"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


def listar(db: Session, asesor_id: str) -> list[dict]:
    """Solicitudes del asesor en el mes actual (HU-20), recientes primero."""
    rows = db.execute(
        text(
            """
            SELECT s.id, s.numero_expediente, s.monto_solicitado, s.monto_aprobado,
                   s.estado, s.created_at, c.nombres, c.apellidos
            FROM solicitudes_credito s
            JOIN clientes c ON c.id = s.cliente_id
            WHERE s.asesor_id = :asesor
              AND date_trunc('month', s.created_at) = date_trunc('month', now())
            ORDER BY s.created_at DESC
            """
        ),
        {"asesor": asesor_id},
    ).mappings().all()
    return [
        {
            "id": str(r["id"]),
            "numero_expediente": r["numero_expediente"],
            "cliente_nombre": f"{r['nombres']} {r['apellidos']}",
            "monto_solicitado": float(r["monto_solicitado"] or 0),
            "monto_aprobado": float(r["monto_aprobado"] or 0),
            "estado": r["estado"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


def evaluar_solicitud(db: Session, solicitud_id: str, asesor_id: str) -> dict:
    # 1. Fetch DNI from the credit application
    row = db.execute(
        text(
            """SELECT s.cliente_id, c.numero_documento
               FROM solicitudes_credito s
               JOIN clientes c ON c.id = s.cliente_id
               WHERE s.id = :id"""
        ),
        {"id": solicitud_id}
    ).first()
    if not row:
        raise ValueError("Solicitud no encontrada.")
    cliente_id, dni = row

    # 2. Bureau simulation based on last digit of DNI
    ultimo = int(dni[-1]) if dni and dni[-1].isdigit() else 0
    
    # Perfil mapping
    perfiles = {
        0: ("NORMAL", 1, 4500.0, 4500.0, 0, False),
        1: ("NORMAL", 2, 12000.0, 8000.0, 0, False),
        2: ("CPP", 2, 18000.0, 12000.0, 15, False),
        3: ("NORMAL", 0, 0.0, 0.0, 0, False),
        4: ("DUDOSO", 3, 25000.0, 15000.0, 95, False),
        5: ("DEFICIENTE", 2, 16000.0, 10000.0, 45, False),
        6: ("NORMAL", 1, 6000.0, 6000.0, 0, False),
        7: ("PERDIDA", 4, 40000.0, 22000.0, 210, True),
        8: ("CPP", 1, 9000.0, 9000.0, 20, False),
        9: ("NORMAL", 2, 14000.0, 9000.0, 0, False),
    }
    
    sbs, entidades, deudas, mayor, mora, lista_negra = perfiles[ultimo]
    motivo = "Registrado en lista de restriccion del sistema financiero." if lista_negra else None

    # Save to consultas_buro
    db.execute(
        text(
            """INSERT INTO consultas_buro
                 (id, asesor_id, cliente_id, solicitud_id, dni_consultado,
                  calificacion_sbs, entidades_con_deuda, deuda_total_pen,
                  mayor_deuda, dias_mayor_mora, en_lista_negra, motivo_bloqueo)
               VALUES
                 (:id, :asesor, :cli, :sol, :dni, :sbs, :ent, :deuda, :mayor, :mora, :ln, :mot)"""
        ),
        {
            "id": str(uuid.uuid4()),
            "asesor": asesor_id,
            "cli": cliente_id,
            "sol": solicitud_id,
            "dni": dni,
            "sbs": sbs,
            "ent": entidades,
            "deuda": deudas,
            "mayor": mayor,
            "mora": mora,
            "ln": lista_negra,
            "mot": motivo
        }
    )

    # 3. Enforce restricted-list blocking: if blacklisted, reject immediately
    if lista_negra:
        db.execute(
            text(
                """UPDATE solicitudes_credito
                   SET estado = 'rechazado', motivo_rechazo = :mot, updated_at = now()
                   WHERE id = :id"""
            ),
            {"mot": motivo, "id": solicitud_id}
        )
        db.commit()
        return {
            "calificacion_sbs": sbs,
            "en_lista_negra": True,
            "bloqueado": True,
            "motivo_bloqueo": motivo
        }
        
    db.commit()
    return {
        "calificacion_sbs": sbs,
        "en_lista_negra": False,
        "bloqueado": False,
        "motivo_bloqueo": None
    }


def guardar_documento(db: Session, solicitud_id: str, data: dict) -> dict:
    doc_id = str(uuid.uuid4())
    db.execute(
        text(
            """INSERT INTO solicitudes_documentos
                 (id, solicitud_id, tipo_documento, storage_url, tamanio_kb, nitidez_score)
               VALUES (:id, :sol, :tipo, :url, :tam, :score)"""
        ),
        {
            "id": doc_id,
            "sol": solicitud_id,
            "tipo": data["tipo_documento"],
            "url": data["storage_url"],
            "tam": data.get("tamanio_kb", 100),
            "score": data.get("nitidez_score", 95.0),
        }
    )
    db.commit()
    return {"id": doc_id, "status": "uploaded"}


def guardar_firma(db: Session, solicitud_id: str, firma_base64: str) -> dict:
    db.execute(
        text(
            """UPDATE solicitudes_credito
               SET firma_cliente_base64 = :firma, updated_at = now()
               WHERE id = :id"""
        ),
        {"firma": firma_base64, "id": solicitud_id}
    )
    db.commit()
    return {"status": "signed"}


def promover_solicitud(db: Session, solicitud_id: str) -> dict:
    # 1. Fetch application details
    row = db.execute(
        text("SELECT estado, firma_cliente_base64, numero_expediente FROM solicitudes_credito WHERE id = :id"),
        {"id": solicitud_id}
    ).first()
    if not row:
        raise ValueError("Solicitud no encontrada.")
    estado, firma, expediente = row

    if estado == "rechazado":
        raise ValueError("La solicitud ha sido rechazada y no puede promoverse.")

    # 2. Check documentation completeness (Step 6 validation)
    docs = db.execute(
        text("SELECT tipo_documento FROM solicitudes_documentos WHERE solicitud_id = :sol"),
        {"sol": solicitud_id}
    ).scalars().all()
    
    requeridos = {'dni_anverso', 'dni_reverso', 'foto_negocio', 'foto_visita'}
    obtenidos = set(docs)
    faltantes = requeridos - obtenidos
    
    if faltantes:
        raise ValueError(f"Documentación incompleta. Falta: {', '.join(faltantes)}")
        
    if not firma:
        raise ValueError("Falta la firma del cliente.")

    # 3. Transition status: enviado -> recibido_comite -> en_evaluacion
    db.execute(
        text("UPDATE solicitudes_credito SET estado = 'recibido_comite', updated_at = now() WHERE id = :id"),
        {"id": solicitud_id}
    )
    db.commit()

    db.execute(
        text("UPDATE solicitudes_credito SET estado = 'en_evaluacion', updated_at = now() WHERE id = :id"),
        {"id": solicitud_id}
    )
    db.commit()

    # 4. Trigger sync / promotion
    res = svc_promocion.promover(db)
    return {"status": "promoted", "expediente": expediente, "sync_result": res}


def add_months(sourcedate, months):
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def registrar_decision_comite(db: Session, solicitud_id: str, data: dict) -> dict:
    # 1. Fetch application details
    row = db.execute(
        text("SELECT estado, cliente_id, monto_solicitado, plazo_meses, cod_solicitud_core, numero_expediente FROM solicitudes_credito WHERE id = :id"),
        {"id": solicitud_id}
    ).first()
    if not row:
        raise ValueError("Solicitud no encontrada.")
    estado, cliente_id, monto, plazo, cod_core, expediente = row

    decision = data["decision"]
    motivo = data.get("motivo_rechazo")
    condicion = data.get("condicion_adicional")

    # 2. Update bd_core_mobile solicitudes_credito
    if decision == "rechazado":
        db.execute(
            text(
                """UPDATE solicitudes_credito
                   SET estado = 'rechazado', motivo_rechazo = :mot, updated_at = now()
                   WHERE id = :id"""
            ),
            {"mot": motivo, "id": solicitud_id}
        )
    elif decision == "condicionado":
        db.execute(
            text(
                """UPDATE solicitudes_credito
                   SET estado = 'condicionado', condicion_adicional = :cond, updated_at = now()
                   WHERE id = :id"""
            ),
            {"cond": condicion, "id": solicitud_id}
        )
    elif decision == "aprobado":
        # Aprobado automatically moves to desembolsado
        db.execute(
            text(
                """UPDATE solicitudes_credito
                   SET estado = 'desembolsado', monto_aprobado = :monto, updated_at = now()
                   WHERE id = :id"""
            ),
            {"monto": monto, "id": solicitud_id}
        )
    else:
        raise ValueError("Decisión inválida.")

    # 3. Sync decision to Financial Core (bd_core_financiero) if promoted
    if cod_core:
        core = SessionLocalCore()
        try:
            core.execute(
                text(
                    """UPDATE dsolicitud
                       SET estado = :est, motivo_rechazo = :mot, condicion_adicional = :cond
                       WHERE codsolicitud = :cod"""
                ),
                {
                    "est": "Desembolsado" if decision == "aprobado" else decision.title(),
                    "mot": motivo,
                    "cond": condicion,
                    "cod": cod_core
                }
            )
            core.commit()
        except Exception as e:
            core.rollback()
            print(f"Error updating Financial Core: {e}")
        finally:
            core.close()

    # 4. If approved, execute disbursement and French amortization schedule
    if decision == "aprobado":
        # TEA rules
        tea = 40.92 if data.get("tiene_seguro", True) else 43.92
        # Monthly rate: TEM = (1 + TEA)^(1/12) - 1
        tem = (1 + tea / 100.0) ** (1.0 / 12.0) - 1
        # Fixed monthly installment formula (French method): R = (P * TEM) / (1 - (1 + TEM)^-n)
        installment = (float(monto) * tem) / (1 - (1 + tem) ** (-int(plazo)))
        
        # Insert credit into cr_creditos (mobile replica)
        cred_id = str(uuid.uuid4())
        cod_credito = "CRE-" + cred_id.replace("-", "")[:8].upper()
        
        db.execute(
            text(
                """INSERT INTO cr_creditos
                     (id, cod_cuenta_credito, cliente_id, producto, monto_desembolsado,
                      saldo_capital, saldo_total, dias_mora, estado, fecha_desembolso,
                      tea, cuotas_total, cuotas_pagadas)
                   VALUES
                     (:id, :cod, :cli, 'Business Loan - Microenterprise', :monto,
                      :monto, :total_deuda, 0, 'vigente', :fec, :tea, :cuotas, 0)"""
            ),
            {
                "id": cred_id,
                "cod": cod_credito,
                "cli": cliente_id,
                "monto": monto,
                "total_deuda": installment * int(plazo),
                "fec": date.today(),
                "tea": tea,
                "cuotas": plazo
            }
        )

        # Generate and insert cronograma cuotas
        balance = float(monto)
        hoy = date.today()
        for idx in range(1, int(plazo) + 1):
            fec_venc = add_months(hoy, idx)
            interes = balance * tem
            principal = installment - interes
            balance -= principal
            if balance < 0 or idx == int(plazo):
                balance = 0.0

            db.execute(
                text(
                    """INSERT INTO cr_cronograma_pagos
                         (id, cod_cuenta_credito, nro_cuota, fecha_vencimiento,
                          monto_cuota, monto_capital, monto_interes, saldo, estado_cuota)
                       VALUES
                         (:id, :cod, :nro, :venc, :cuota, :cap, :int, :saldo, 'pendiente')"""
                ),
                {
                    "id": str(uuid.uuid4()),
                    "cod": cod_credito,
                    "nro": idx,
                    "venc": venc,
                    "cuota": round(installment, 2),
                    "cap": round(principal, 2),
                    "int": round(interes, 2),
                    "saldo": round(balance, 2)
                }
            )

        # Send push/in-app notification to customer
        db.execute(
            text(
                """INSERT INTO notificaciones (id, destinatario_tipo, cliente_id, titulo, cuerpo, tipo)
                   VALUES (:id, 'cliente', :cli, 'Crédito Desembolsado', :cuerpo, 'desembolso')"""
            ),
            {
                "id": str(uuid.uuid4()),
                "cli": cliente_id,
                "cuerpo": f"¡Felicidades! Tu crédito {cod_credito} ha sido desembolsado por S/{float(monto):,.2f}.",
            }
        )

    db.commit()
    return {
        "status": "ok",
        "decision": decision,
        "nuevo_estado": "desembolsado" if decision == "aprobado" else decision
    }



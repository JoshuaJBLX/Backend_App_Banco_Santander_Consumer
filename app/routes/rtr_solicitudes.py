from typing import Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.cfg_database import get_db
from app.core.cfg_auth import get_current_asesor
from app.schemas.sch_solicitudes import (
    SolicitudIn, SolicitudCreada, SolicitudResumen,
    DocumentoRequest, FirmaRequest,
    DecisionRequest, DesembolsoRequest,
)
from app.repositories import rep_solicitudes
import uuid, json, calendar

router = APIRouter()


class NotaIn(BaseModel):
    contenido: str


class NotaOut(BaseModel):
    contenido: str
    created_at: Optional[str] = None


# ── ENDPOINTS EXISTENTES (MANTENIDOS) ────────────────────────────────────────

@router.post("", response_model=SolicitudCreada)
def crear_solicitud(
    data: SolicitudIn,
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Registra una solicitud de credito (M5 / HU-17)."""
    return rep_solicitudes.crear(
        db, asesor["asesor_id"], asesor.get("agencia_id"), data.model_dump()
    )


@router.get("", response_model=list[SolicitudResumen])
def listar_solicitudes(
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Historial de solicitudes del mes (HU-20) y tablero de estado (M9)."""
    return rep_solicitudes.listar(db, asesor["asesor_id"])


@router.post("/{solicitud_id}/notas")
def agregar_nota(
    solicitud_id: str,
    data: NotaIn,
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Agrega una nota interna a la solicitud (RF-72)."""
    return rep_solicitudes.agregar_nota(
        db, solicitud_id, asesor["asesor_id"], data.contenido
    )


@router.get("/{solicitud_id}/notas", response_model=list[NotaOut])
def listar_notas(
    solicitud_id: str,
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Notas internas de la solicitud (RF-72)."""
    return rep_solicitudes.listar_notas(db, solicitud_id)


# ── 1. ENDPOINT: ADJUNTAR DOCUMENTOS ─────────────────────────────────────────

@router.post("/documentos")
def adjuntar_documento(
    data: DocumentoRequest,
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """
    POST /solicitudes/documentos
    Adjunta un documento a una solicitud de credito.
    """
    # Verificar solicitud
    sol_row = db.execute(
        text("SELECT id FROM solicitudes_credito WHERE id = :id"),
        {"id": data.solicitud_id},
    ).first()
    if not sol_row:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    # Guardar documento
    doc_id = str(uuid.uuid4())
    db.execute(
        text(
            """INSERT INTO solicitudes_documentos
                 (id, solicitud_id, tipo_documento, storage_url, tamanio_kb)
               VALUES (:id, :sol, :tipo, :url, :tam)"""
        ),
        {
            "id": doc_id,
            "sol": data.solicitud_id,
            "tipo": data.tipo_documento,
            "url": data.storage_url,
            "tam": data.tamanio_kb or 0,
        },
    )
    db.commit()

    return {
        "success": True,
        "message": "Documento adjuntado exitosamente",
        "documento_id": doc_id,
    }


# ── 2. ENDPOINT: CAPTURAR FIRMA ──────────────────────────────────────────────

@router.put("/firma")
def capturar_firma(
    data: FirmaRequest,
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """
    PUT /solicitudes/firma
    Captura la firma del cliente en base64.
    """
    # Verificar solicitud
    sol_row = db.execute(
        text("SELECT id FROM solicitudes_credito WHERE id = :id"),
        {"id": data.solicitud_id},
    ).first()
    if not sol_row:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    # Guardar firma
    db.execute(
        text(
            """UPDATE solicitudes_credito
               SET firma_cliente_base64 = :firma, updated_at = now()
               WHERE id = :id"""
        ),
        {"firma": data.firma_base64, "id": data.solicitud_id},
    )
    db.commit()

    return {"success": True, "message": "Firma capturada exitosamente"}


# ── 3. ENDPOINT: PROMOVER AL COMITÉ ──────────────────────────────────────────

@router.put("/{solicitud_id}/promover")
def promover_solicitud(
    solicitud_id: str,
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """
    PUT /solicitudes/{solicitud_id}/promover
    Avanza la solicitud: enviado -> recibido_comite -> en_evaluacion
    """
    # Obtener solicitud
    row = db.execute(
        text("SELECT id, estado, numero_expediente FROM solicitudes_credito WHERE id = :id"),
        {"id": solicitud_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    estado_actual = row[1]
    expediente = row[2]

    # Validar estado actual
    if estado_actual not in ("enviado", "recibido_comite"):
        raise HTTPException(
            status_code=400,
            detail=f"Estado actual '{estado_actual}' no permite promover. Debe ser 'enviado' o 'recibido_comite'.",
        )

    # Verificar documentacion completa si viene de enviado
    if estado_actual == "enviado":
        docs = db.execute(
            text("SELECT tipo_documento FROM solicitudes_documentos WHERE solicitud_id = :sol"),
            {"sol": solicitud_id},
        ).scalars().all()

        requeridos = {"dni_anverso", "dni_reverso", "foto_negocio", "foto_visita"}
        obtenidos = set(docs)
        faltantes = requeridos - obtenidos
        if faltantes:
            raise HTTPException(
                status_code=400,
                detail=f"Documentacion incompleta. Faltan: {', '.join(faltantes)}",
            )

        # Verificar firma
        firma_row = db.execute(
            text("SELECT firma_cliente_base64 FROM solicitudes_credito WHERE id = :id"),
            {"id": solicitud_id},
        ).first()
        if not firma_row or not firma_row[0]:
            raise HTTPException(
                status_code=400,
                detail="Falta la firma del cliente para promover.",
            )

    # Avanzar estado
    if estado_actual == "enviado":
        nuevo_estado = "recibido_comite"
    else:
        nuevo_estado = "en_evaluacion"

    db.execute(
        text("UPDATE solicitudes_credito SET estado = :est, updated_at = now() WHERE id = :id"),
        {"est": nuevo_estado, "id": solicitud_id},
    )

    # Crear sync_outbox
    db.execute(
        text(
            """INSERT INTO sync_outbox (id, entidad, entidad_id, operacion, payload, estado)
               VALUES (:id, 'solicitudes_credito', :eid, 'update', CAST(:payload AS jsonb), 'pendiente')"""
        ),
        {
            "id": str(uuid.uuid4()),
            "eid": solicitud_id,
            "payload": json.dumps({
                "numero_expediente": expediente,
                "estado": nuevo_estado,
                "fecha_cambio": datetime.now().isoformat(),
            }),
        },
    )
    db.commit()

    return {"success": True, "estado": nuevo_estado}


# ── 4. ENDPOINT: REGISTRAR DECISIÓN DEL COMITÉ ──────────────────────────────

@router.put("/{solicitud_id}/decision")
def registrar_decision(
    solicitud_id: str,
    data: DecisionRequest,
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """
    PUT /solicitudes/{solicitud_id}/decision
    Registra la decision del comite: APROBADO / CONDICIONADO / RECHAZADO
    """
    # Obtener solicitud
    row = db.execute(
        text("SELECT id, estado, monto_solicitado, plazo_meses, cliente_id, tea_referencial, numero_expediente FROM solicitudes_credito WHERE id = :id"),
        {"id": solicitud_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    estado_actual = row[1]
    monto_solicitado = float(row[2] or 0)
    plazo_meses = row[3] or 12
    cliente_id = str(row[4])
    tea = float(row[5] or 43.92)
    expediente = row[6]

    if estado_actual != "en_evaluacion":
        raise HTTPException(
            status_code=400,
            detail=f"La solicitud debe estar en 'en_evaluacion'. Estado actual: {estado_actual}",
        )

    decision = data.decision.upper()
    if decision not in ("APROBADO", "CONDICIONADO", "RECHAZADO"):
        raise HTTPException(
            status_code=400,
            detail="Decision invalida. Use: APROBADO, CONDICIONADO o RECHAZADO",
        )

    monto_aprobado = data.monto_aprobado or monto_solicitado

    if decision == "RECHAZADO":
        if not data.motivo_rechazo:
            raise HTTPException(status_code=400, detail="motivo_rechazo es obligatorio para RECHAZADO")
        db.execute(
            text("UPDATE solicitudes_credito SET estado = 'rechazado', motivo_rechazo = :mot, updated_at = now() WHERE id = :id"),
            {"mot": data.motivo_rechazo, "id": solicitud_id},
        )
    elif decision == "CONDICIONADO":
        db.execute(
            text("UPDATE solicitudes_credito SET estado = 'condicionado', monto_aprobado = :monto, condicion_adicional = :cond, updated_at = now() WHERE id = :id"),
            {"monto": monto_aprobado, "cond": data.condicion_adicional or "", "id": solicitud_id},
        )
    elif decision == "APROBADO":
        # Aprobado → desembolsado automaticamente con generacion de creditos y cronograma
        _generar_desembolso_y_cronograma(
            db, solicitud_id, cliente_id, monto_aprobado, plazo_meses,
            tea, expediente, date.today(),
        )
        db.commit()
        return {
            "success": True,
            "estado": "desembolsado",
            "monto_aprobado": monto_aprobado,
        }

    # Para RECHAZADO / CONDICIONADO, sincronizar con core
    db.commit()
    return {
        "success": True,
        "estado": decision.lower(),
        "monto_aprobado": monto_aprobado if decision == "CONDICIONADO" else None,
    }


# ── 5. ENDPOINT: REGISTRAR DESEMBOLSO (separado del comite) ─────────────────

@router.post("/{solicitud_id}/desembolso")
def registrar_desembolso(
    solicitud_id: str,
    data: DesembolsoRequest,
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """
    POST /solicitudes/{solicitud_id}/desembolso
    Registra desembolso para una solicitud aprobada y genera cronograma.
    """
    row = db.execute(
        text("SELECT id, estado, monto_aprobado, monto_solicitado, plazo_meses, cliente_id, tea_referencial, numero_expediente FROM solicitudes_credito WHERE id = :id"),
        {"id": solicitud_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    estado_actual = row[1]
    if estado_actual != "aprobado":
        raise HTTPException(
            status_code=400,
            detail=f"La solicitud debe estar 'aprobado'. Estado actual: {estado_actual}",
        )

    monto = float(row[2] or row[3] or 0)
    plazo = row[4] or 12
    cliente_id = str(row[5])
    tea = float(row[6] or 43.92)
    expediente = row[7]

    fecha_des = date.today()
    if data.fecha_desembolso:
        try:
            fecha_des = date.fromisoformat(data.fecha_desembolso)
        except ValueError:
            raise HTTPException(status_code=400, detail="fecha_desembolso debe ser YYYY-MM-DD")

    _generar_desembolso_y_cronograma(
        db, solicitud_id, cliente_id, monto, plazo, tea, expediente, fecha_des,
    )
    db.commit()

    # Calcular TEM y cuota para respuesta
    tem = pow(1 + tea / 100.0, 1.0 / 12.0) - 1
    cuota = (monto * tem * pow(1 + tem, plazo)) / (pow(1 + tem, plazo) - 1)

    return {
        "success": True,
        "cod_cuenta_credito": f"CR-{fecha_des.strftime('%Y%m%d')}-{solicitud_id[:6].upper()}",
        "monto_desembolsado": monto,
        "cuotas": plazo,
        "monto_cuota": round(cuota, 2),
    }


# ── FUNCION AUXILIAR: generar desembolso + cronograma ───────────────────────

def _generar_desembolso_y_cronograma(
    db: Session,
    solicitud_id: str,
    cliente_id: str,
    monto: float,
    plazo: int,
    tea: float,
    expediente: str,
    fecha_des: date,
):
    """Genera credito, cronograma y notificacion para una solicitud aprobada."""
    # 1. Insertar en cr_creditos
    cred_id = str(uuid.uuid4())
    cod_credito = f"CR-{fecha_des.strftime('%Y%m%d')}-{cred_id[:6].upper()}"

    # Calcular TEM y cuota (amortizacion francesa)
    tem = pow(1 + tea / 100.0, 1.0 / 12.0) - 1
    cuota = round((monto * tem * pow(1 + tem, plazo)) / (pow(1 + tem, plazo) - 1), 2)
    total_deuda = round(cuota * plazo, 2)

    db.execute(
        text(
            """INSERT INTO cr_creditos
                 (id, cod_cuenta_credito, cliente_id, producto, monto_desembolsado,
                  saldo_capital, saldo_total, dias_mora, estado, fecha_desembolso,
                  tea, cuotas_total, cuotas_pagadas)
               VALUES
                 (:id, :cod, :cli, 'Credito Empresarial - Microempresa', :monto,
                  :monto, :total, 0, 'vigente', :fec, :tea, :cuotas, 0)"""
        ),
        {
            "id": cred_id,
            "cod": cod_credito,
            "cli": cliente_id,
            "monto": monto,
            "total": total_deuda,
            "fec": fecha_des,
            "tea": tea,
            "cuotas": plazo,
        },
    )

    # 2. Generar cronograma de cuotas
    balance = monto
    for idx in range(1, plazo + 1):
        # Calcular fecha vencimiento: dia 03 del mes siguiente
        mes = fecha_des.month + idx
        anio = fecha_des.year + (mes - 1) // 12
        mes = ((mes - 1) % 12) + 1
        dia = min(3, calendar.monthrange(anio, mes)[1])
        fec_venc = date(anio, mes, dia)

        interes = round(balance * tem, 2)
        principal = round(cuota - interes, 2)

        if idx == plazo:
            principal = balance
            cuota_real = round(principal + interes, 2)
        else:
            cuota_real = cuota

        balance = round(balance - principal, 2)
        if balance < 0:
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
                "venc": fec_venc,
                "cuota": cuota_real,
                "cap": principal,
                "int": interes,
                "saldo": balance,
            },
        )

    # 3. Actualizar solicitud
    db.execute(
        text("UPDATE solicitudes_credito SET estado = 'desembolsado', monto_aprobado = :monto, updated_at = now() WHERE id = :id"),
        {"monto": monto, "id": solicitud_id},
    )

    # 4. Enviar notificacion
    db.execute(
        text(
            """INSERT INTO notificaciones (id, destinatario_tipo, cliente_id, titulo, cuerpo, tipo)
               VALUES (:id, 'cliente', :cli, 'Credito Desembolsado', :cuerpo, 'desembolso')"""
        ),
        {
            "id": str(uuid.uuid4()),
            "cli": cliente_id,
            "cuerpo": f"Felicidades! Tu credito {cod_credito} ha sido desembolsado por S/{monto:,.2f}.",
        },
    )

    # 5. Sync outbox
    db.execute(
        text(
            """INSERT INTO sync_outbox (id, entidad, entidad_id, operacion, payload, estado)
               VALUES (:id, 'cr_creditos', :eid, 'insert', CAST(:payload AS jsonb), 'pendiente')"""
        ),
        {
            "id": str(uuid.uuid4()),
            "eid": cred_id,
            "payload": json.dumps({
                "cod_cuenta_credito": cod_credito,
                "cliente_id": cliente_id,
                "monto": monto,
                "fecha_desembolso": fecha_des.isoformat(),
            }),
        },
    )
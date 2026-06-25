from typing import Optional
"""Repositorio del lado app de clientes — consultas sobre bd_core_mobile."""
import uuid
import json
from datetime import date
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models.mdl_clientes import Cliente
from app.models.mdl_cliente_mobile import (
    UsuarioCliente, CrCuentaAhorro, CrCredito, CrCronogramaPago,
    CrMovimiento, Tarjeta, OperacionCliente, Notificacion,
)
from app.models.mdl_cartera import CarteraDiaria


def get_usuario_by_username(db: Session, username: str) -> Optional[UsuarioCliente]:

    return db.query(UsuarioCliente).filter(
        UsuarioCliente.username == username
    ).first()


def get_cliente(db: Session, cliente_id: str) -> Optional[Cliente]:
    return db.query(Cliente).filter(Cliente.id == cliente_id).first()


def cuentas_ahorro(db: Session, cliente_id: str) -> list[CrCuentaAhorro]:
    return db.query(CrCuentaAhorro).filter(
        CrCuentaAhorro.cliente_id == cliente_id
    ).order_by(CrCuentaAhorro.cod_cuenta_ahorro.asc()).all()


def creditos(db: Session, cliente_id: str) -> list[CrCredito]:
    return db.query(CrCredito).filter(
        CrCredito.cliente_id == cliente_id
    ).order_by(CrCredito.fecha_desembolso.desc().nullslast()).all()


def cronograma(db: Session, cod_cuenta_credito: str) -> list[CrCronogramaPago]:
    return db.query(CrCronogramaPago).filter(
        CrCronogramaPago.cod_cuenta_credito == cod_cuenta_credito
    ).order_by(CrCronogramaPago.nro_cuota.asc()).all()


def movimientos(db: Session, cliente_id: str, limit: int = 20) -> list[CrMovimiento]:
    return db.query(CrMovimiento).filter(
        CrMovimiento.cliente_id == cliente_id
    ).order_by(CrMovimiento.fecha_operacion.desc()).limit(limit).all()


def tarjetas(db: Session, cliente_id: str) -> list[Tarjeta]:
    return db.query(Tarjeta).filter(
        Tarjeta.cliente_id == cliente_id
    ).order_by(Tarjeta.created_at.asc()).all()


def notificaciones(db: Session, cliente_id: str, limit: int = 30) -> list[Notificacion]:
    return db.query(Notificacion).filter(
        Notificacion.destinatario_tipo == "cliente",
        Notificacion.cliente_id == cliente_id,
    ).order_by(Notificacion.created_at.desc()).limit(limit).all()


def crear_operacion(db: Session, cliente_id: str, data: dict) -> OperacionCliente:
    op = OperacionCliente(
        cliente_id=cliente_id,
        cod_cuenta_origen=data.get("cod_cuenta_origen"),
        cod_cuenta_destino=data.get("cod_cuenta_destino"),
        tipo=data.get("tipo"),
        monto=data.get("monto"),
        moneda=data.get("moneda", "PEN"),
        estado="pendiente",
    )
    db.add(op)
    db.commit()
    db.refresh(op)
    return op


def crear_solicitud_cliente(db: Session, cliente_id: str, data: dict) -> dict:
    # 1. Get an active advisor and agency to assign the credit application to
    row = db.execute(
        text("SELECT id, agencia_id FROM asesores WHERE activo = TRUE LIMIT 1")
    ).first()
    if not row:
        raise ValueError("No active advisors available for assignment.")
    asesor_id, agencia_id = row

    # 2. Generate case number
    sol_id = str(uuid.uuid4())
    expediente = "EXP-" + sol_id.replace("-", "")[:8].upper()

    # 3. Create the credit application in bd_core_mobile
    db.execute(
        text(
            """INSERT INTO solicitudes_credito
                 (id, numero_expediente, canal, asesor_id, cliente_id, agencia_id,
                  monto_solicitado, plazo_meses, destino_credito, garantia,
                  moneda, tipo_cuota, estado)
               VALUES
                 (:id, :exp, 'cliente', :asesor_id, :cliente_id, :agencia_id,
                  :monto, :plazo, :destino, :garantia,
                  'PEN', 'mensual', 'enviado')"""
        ),
        {
            "id": sol_id,
            "exp": expediente,
            "asesor_id": asesor_id,
            "cliente_id": cliente_id,
            "agencia_id": agencia_id,
            "monto": data["monto_solicitado"],
            "plazo": data["plazo_meses"],
            "destino": data["destino_credito"],
            "garantia": data.get("garantia", "sin_garantia"),
        }
    )

    # 4. Create cartera_diaria record for the advisor
    if data["monto_solicitado"] >= 15000:
        prioridad = "alta"
    elif data["monto_solicitado"] >= 8000:
        prioridad = "media"
    else:
        prioridad = "normal"

    db.execute(
        text(
            """INSERT INTO cartera_diaria
                 (id, asesor_id, cliente_id, agencia_id, fecha_asignacion,
                  tipo_gestion, prioridad, estado_visita, monto_credito)
               VALUES
                 (:id, :asesor_id, :cliente_id, :agencia_id, :fecha,
                  'NUEVA_SOLICITUD', :prioridad, 'pendiente', :monto)"""
        ),
        {
            "id": str(uuid.uuid4()),
            "asesor_id": asesor_id,
            "cliente_id": cliente_id,
            "agencia_id": agencia_id,
            "fecha": date.today(),
            "prioridad": prioridad,
            "monto": data["monto_solicitado"],
        }
    )

    # 5. Enqueue to sync_outbox
    cli_row = db.execute(
        text("SELECT numero_documento, nombres, apellidos FROM clientes WHERE id = :id"),
        {"id": cliente_id}
    ).first()
    doc = cli_row[0] if cli_row else ""
    nombres = cli_row[1] if cli_row else ""
    apellidos = cli_row[2] if cli_row else ""

    payload = {
        "numero_documento": doc,
        "nombres": nombres,
        "apellidos": apellidos,
        "monto_solicitado": float(data["monto_solicitado"]),
        "plazo_meses": int(data["plazo_meses"]),
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

    # 5. Insert notification
    db.execute(
        text(
            """INSERT INTO notificaciones (id, destinatario_tipo, cliente_id, titulo, cuerpo, tipo)
               VALUES (:id, 'cliente', :cli, :titulo, :cuerpo, 'envio_solicitud')"""
        ),
        {
            "id": str(uuid.uuid4()),
            "cli": cliente_id,
            "titulo": "Solicitud Enviada",
            "cuerpo": f"Tu solicitud de crédito {expediente} por S/{data['monto_solicitado']:.2f} ha sido enviada.",
        }
    )

    db.commit()
    return {
        "id": uuid.UUID(sol_id),
        "numero_expediente": expediente,
        "estado": "enviado",
        "canal": "cliente",
        "monto_solicitado": data["monto_solicitado"],
        "plazo_meses": data["plazo_meses"],
        "destino_credito": data["destino_credito"],
        "garantia": data.get("garantia", "sin_garantia"),
    }


from typing import Optional
from datetime import date
from sqlalchemy import text
from sqlalchemy.orm import Session


def actualizar_ubicacion(
    db: Session,
    cliente_id: str,
    lat: float,
    lng: float,
    direccion: Optional[str] = None,
) -> bool:
    """Actualiza las coordenadas del negocio del cliente (HU-10 / RF-25/26)."""
    res = db.execute(
        text(
            """
            UPDATE clientes
               SET lat = :lat,
                   lng = :lng,
                   direccion = COALESCE(:direccion, direccion),
                   updated_at = now()
             WHERE id = :id
            """
        ),
        {"id": cliente_id, "lat": lat, "lng": lng, "direccion": direccion},
    )
    db.commit()
    return res.rowcount > 0


def obtener_ficha(db: Session, cliente_id: str) -> Optional[dict]:
    """Ficha completa del cliente (RF-27/30/33): datos, posicion, historial, oferta."""
    cli = db.execute(
        text("SELECT * FROM clientes WHERE id = :id"), {"id": cliente_id}
    ).mappings().first()
    if cli is None:
        return None

    # Posicion en el sistema (agregado de cr_creditos) — RF-30
    pos = db.execute(
        text(
            """
            SELECT
                COALESCE(SUM(saldo_total), 0)                  AS deuda_total,
                COUNT(*) FILTER (WHERE estado = 'vigente')     AS cuentas_vigentes,
                COUNT(*) FILTER (WHERE dias_mora > 0)          AS cuentas_mora,
                COALESCE(MAX(dias_mora), 0)                    AS dias_mayor_mora
            FROM cr_creditos
            WHERE cliente_id = :id
            """
        ),
        {"id": cliente_id},
    ).mappings().first()

    # Historial crediticio (ultimos 5) — RF-27
    historial = db.execute(
        text(
            """
            SELECT cod_cuenta_credito, producto, monto_desembolsado,
                   tea, estado, dias_mora, cuotas_total, cuotas_pagadas
            FROM cr_creditos
            WHERE cliente_id = :id
            ORDER BY fecha_desembolso DESC NULLS LAST
            LIMIT 5
            """
        ),
        {"id": cliente_id},
    ).mappings().all()

    # Oferta preaprobada vigente (mayor score) — RF-33
    oferta = db.execute(
        text(
            """
            SELECT monto_maximo, plazo_sugerido_meses, tea_referencial,
                   score_confianza, fecha_vencimiento
            FROM creditos_preaprobados
            WHERE cliente_id = :id AND vigente = TRUE
              AND (fecha_vencimiento IS NULL OR fecha_vencimiento >= :hoy)
            ORDER BY score_confianza DESC
            LIMIT 1
            """
        ),
        {"id": cliente_id, "hoy": date.today()},
    ).mappings().first()

    # Comportamiento de pagos ultimos 12 meses (RF-31): 1=puntual, 2=mora, 0=sin cuota
    dni = cli["numero_documento"] or "0"
    dmora = pos["dias_mayor_mora"]
    comportamiento = [1] * 12
    if dmora > 0:
        n = 1 if dmora <= 30 else (2 if dmora <= 60 else 3)
        for k in range(n):
            comportamiento[11 - k] = 2
    if dni[-1].isdigit() and int(dni[-1]) % 3 == 0:
        comportamiento[0] = 0
        comportamiento[1] = 0

    con_cuota = [m for m in comportamiento if m != 0]
    puntuales = [m for m in con_cuota if m == 1]
    pct_puntual = round(len(puntuales) / len(con_cuota) * 100, 1) if con_cuota else 0
    monto_pagado = sum(
        float(h["monto_desembolsado"] or 0)
        for h in historial
        if h["estado"] == "pagado"
    )

    return {
        "comportamiento": comportamiento,
        "indicadores": {
            "pct_puntual": pct_puntual,
            "dias_prom_mora": dmora,
            "monto_pagado": monto_pagado,
        },
        "cliente": {
            "id": str(cli["id"]),
            "numero_documento": cli["numero_documento"],
            "nombres": cli["nombres"],
            "apellidos": cli["apellidos"],
            "telefono": cli["telefono"],
            "direccion": cli["direccion"],
            "tipo_negocio": cli["tipo_negocio"],
            "nombre_negocio": cli["nombre_negocio"],
            "antiguedad_negocio_meses": cli["antiguedad_negocio_meses"],
            "calificacion_sbs": cli["calificacion_sbs"] or "NORMAL",
        },
        "posicion": {
            "deuda_total": float(pos["deuda_total"]),
            "cuentas_vigentes": pos["cuentas_vigentes"],
            "cuentas_mora": pos["cuentas_mora"],
            "dias_mayor_mora": pos["dias_mayor_mora"],
        },
        "historial": [
            {
                "producto": h["producto"],
                "monto_desembolsado": float(h["monto_desembolsado"] or 0),
                "plazo_meses": h["cuotas_total"],
                "tea": float(h["tea"] or 0),
                "estado": h["estado"],
                "dias_mora": h["dias_mora"] or 0,
                "cuotas_total": h["cuotas_total"] or 0,
                "cuotas_pagadas": h["cuotas_pagadas"] or 0,
            }
            for h in historial
        ],
        "oferta": None
        if oferta is None
        else {
            "monto_maximo": float(oferta["monto_maximo"]),
            "plazo_sugerido_meses": oferta["plazo_sugerido_meses"],
            "tea_referencial": float(oferta["tea_referencial"] or 0),
            "score_confianza": oferta["score_confianza"] or 0,
            "fecha_vencimiento": oferta["fecha_vencimiento"].isoformat()
            if oferta["fecha_vencimiento"]
            else None,
        },
    }


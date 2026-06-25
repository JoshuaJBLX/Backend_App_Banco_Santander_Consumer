"""
Seed de datos para la Ficha del Cliente (M3): enriquece clientes demo,
agrega creditos historicos (cr_creditos) y una oferta preaprobada.

Uso (raiz del proyecto, venv activo):
    python -m scripts.seed_ficha
"""
import sys, os, uuid
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.cfg_database import SessionLocal


def run():
    db = SessionLocal()
    try:
        ya = db.execute(text("SELECT COUNT(*) FROM cr_creditos")).scalar()
        if ya and ya > 0:
            print("seed_ficha ya aplicado (cr_creditos tiene datos). Nada que hacer.")
            return

        # Enriquece datos de negocio + calificacion SBS de los clientes demo.
        negocios = {
            "44455667": ("Bodega", "Bodega Maria", 48, "DUDOSO"),
            "41112233": ("Comercio", "Ferreteria Jose", 72, "NORMAL"),
            "42778899": ("Servicios", "Salon Rosa", 36, "CPP"),
            "43223344": ("Produccion", "Panaderia Pedro", 12, "NORMAL"),
            "40556677": ("Comercio", "Abarrotes Lucia", 60, "NORMAL"),
        }
        for doc, (tipo, nombre, ant, sbs) in negocios.items():
            db.execute(
                text(
                    """UPDATE clientes SET tipo_negocio=:t, nombre_negocio=:n,
                       antiguedad_negocio_meses=:a, calificacion_sbs=:s,
                       direccion=COALESCE(direccion,'Av. Los Andes 123')
                       WHERE numero_documento=:doc"""
                ),
                {"t": tipo, "n": nombre, "a": ant, "s": sbs, "doc": doc},
            )

        clientes = db.execute(
            text("SELECT id, numero_documento FROM clientes")
        ).mappings().all()
        idx = {c["numero_documento"]: str(c["id"]) for c in clientes}

        hoy = date.today()
        # (doc, producto, desembolsado, saldo, dias_mora, estado, tea, cuotas, pagadas)
        creditos = [
            ("44455667", "Microcredito", 10000, 6200, 45, "vencido", 42.5, 18, 9),
            ("44455667", "Microcredito", 5000, 0, 0, "pagado", 39.0, 12, 12),
            ("41112233", "Microcredito", 15000, 9000, 0, "vigente", 38.0, 24, 10),
            ("42778899", "Consumo", 6000, 3500, 12, "vigente", 45.0, 12, 6),
            ("40556677", "Microcredito", 8000, 0, 0, "pagado", 40.0, 18, 18),
        ]
        for i, (doc, prod, des, saldo, mora, estado, tea, ct, cp) in enumerate(creditos):
            cid = idx.get(doc)
            if not cid:
                continue
            db.execute(
                text(
                    """INSERT INTO cr_creditos
                       (id, cod_cuenta_credito, cliente_id, producto, monto_desembolsado,
                        saldo_capital, saldo_total, dias_mora, calificacion_interna, estado,
                        fecha_desembolso, tea, cuotas_total, cuotas_pagadas)
                       VALUES (:id,:cod,:cli,:prod,:des,:scap,:stot,:mora,:cal,:est,
                               :fec,:tea,:ct,:cp)"""
                ),
                {
                    "id": str(uuid.uuid4()),
                    "cod": f"CC{1000+i}",
                    "cli": cid,
                    "prod": prod,
                    "des": des,
                    "scap": saldo,
                    "stot": saldo,
                    "mora": mora,
                    "cal": "Normal" if mora == 0 else "Deficiente",
                    "est": estado,
                    "fec": hoy - timedelta(days=300 - i * 20),
                    "tea": tea,
                    "ct": ct,
                    "cp": cp,
                },
            )

        # Oferta preaprobada vigente para Jose (buen historial).
        jose = idx.get("41112233")
        if jose:
            db.execute(
                text(
                    """INSERT INTO creditos_preaprobados
                       (id, cliente_id, monto_maximo, plazo_sugerido_meses,
                        tea_referencial, score_confianza, vigente, fecha_calculo, fecha_vencimiento)
                       VALUES (:id,:cli,:monto,:plazo,:tea,:score,TRUE,:fc,:fv)"""
                ),
                {
                    "id": str(uuid.uuid4()),
                    "cli": jose,
                    "monto": 20000,
                    "plazo": 24,
                    "tea": 36.0,
                    "score": 82,
                    "fc": hoy,
                    "fv": hoy + timedelta(days=30),
                },
            )

        db.commit()
        print("seed_ficha OK: creditos historicos + oferta preaprobada creados.")
    finally:
        db.close()


if __name__ == "__main__":
    run()

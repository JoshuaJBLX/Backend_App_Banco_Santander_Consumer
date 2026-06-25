"""
Seed de un segundo asesor de prueba para bd_core_mobile.
Crea: asesor 0002 / clave 1234 (perfil SUPERVISOR, ve Reportes) + 4 clientes y
su cartera del dia. Reutiliza la agencia existente.

Uso (desde la raiz del proyecto, con venv):
    ./venv/Scripts/python.exe -m scripts.seed_asesor_0002
"""
import sys, os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.cfg_database import SessionLocal
from app.core.cfg_security import hash_password
from app.models.mdl_asesores import Agencia, Asesor
from app.models.mdl_clientes import Cliente
from app.models.mdl_cartera import CarteraDiaria


def run():
    db = SessionLocal()
    try:
        if db.query(Asesor).filter(Asesor.codigo_empleado == "0002").first():
            print("El asesor 0002 ya existe. Nada que hacer.")
            return

        agencia = db.query(Agencia).first()
        if agencia is None:
            agencia = Agencia(cod_agencia="0001", nombre="Agencia Central",
                              region="Lima")
            db.add(agencia)
            db.flush()

        asesor = Asesor(
            cod_asesor="A002",
            codigo_empleado="0002",
            nombres="Ana",
            apellidos="Torres",
            agencia_id=agencia.id,
            perfil="supervisor",  # ve Reportes y supervision (M11)
            password_hash=hash_password("1234"),
        )
        db.add(asesor)
        db.flush()

        demo = [
            ("Juan Perez Lopez",      "45667788", "RENOVACION",       "alta",   80, 15000),
            ("Carmen Diaz Rojas",     "46778899", "AMPLIACION",       "media",  60, 7000),
            ("Luis Huaman Ccopa",     "47889900", "RECUPERACION_MORA","alta",   90, 9500),
            ("Sofia Mendoza Quispe",  "48990011", "NUEVA_SOLICITUD",  "normal", 25, 4000),
        ]
        hoy = date.today()
        for i, (nombre, doc, tipo, prio, score, monto) in enumerate(demo):
            nombres, apellidos = nombre.split(" ", 1)
            existente = db.query(Cliente).filter(
                Cliente.numero_documento == doc).first()
            if existente is None:
                cli = Cliente(numero_documento=doc, nombres=nombres,
                              apellidos=apellidos, telefono="9" + doc)
                db.add(cli)
                db.flush()
            else:
                cli = existente
            db.add(CarteraDiaria(
                asesor_id=asesor.id,
                cliente_id=cli.id,
                agencia_id=agencia.id,
                fecha_asignacion=hoy,
                tipo_gestion=tipo,
                prioridad=prio,
                score_prioridad=score,
                monto_credito=monto,
                estado_visita="pendiente",
                orden_manual=i,
            ))

        db.commit()
        print("Seed OK. Login: codigo_empleado=0002  password=1234  (supervisor)")
    finally:
        db.close()


if __name__ == "__main__":
    run()

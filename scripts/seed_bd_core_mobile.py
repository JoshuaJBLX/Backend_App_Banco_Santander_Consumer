"""
Seed de datos demo para bd_core_mobile.
Crea: 1 agencia, 1 asesor (login 0001 / clave 1234), 5 clientes y su cartera del dia.

Uso (desde la raiz del proyecto, con venv activo):
    python -m scripts.seed_bd_core_mobile
"""
import sys, os, uuid
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
        if db.query(Asesor).filter(Asesor.codigo_empleado == "0001").first():
            print("El seed ya fue aplicado (asesor 0001 existe). Nada que hacer.")
            return

        agencia = Agencia(cod_agencia="0001", nombre="Agencia Central", region="Lima")
        db.add(agencia)
        db.flush()

        asesor = Asesor(
            cod_asesor="A001",
            codigo_empleado="0001",
            nombres="Carlos",
            apellidos="Ramirez",
            agencia_id=agencia.id,
            perfil="operador",
            password_hash=hash_password("1234"),
        )
        db.add(asesor)
        db.flush()

        demo = [
            ("Maria Quispe Huaman",  "44455667", "RECUPERACION_MORA", "alta",   88, 8500),
            ("Jose Mamani Flores",   "41112233", "RENOVACION",        "alta",   72, 12000),
            ("Rosa Condori Apaza",   "42778899", "AMPLIACION",        "media",  55, 5000),
            ("Pedro Ccahua Ramos",   "43223344", "NUEVA_SOLICITUD",   "normal", 30, 3000),
            ("Lucia Vargas Soto",    "40556677", "SEGUIMIENTO",       "normal", 15, 4500),
        ]
        hoy = date.today()
        for i, (nombre, doc, tipo, prio, score, monto) in enumerate(demo):
            nombres, apellidos = nombre.split(" ", 1)
            cli = Cliente(
                numero_documento=doc,
                nombres=nombres,
                apellidos=apellidos,
                telefono="9" + doc,
            )
            db.add(cli)
            db.flush()
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
        print("Seed OK. Login: codigo_empleado=0001  password=1234")
    finally:
        db.close()

if __name__ == "__main__":
    run()

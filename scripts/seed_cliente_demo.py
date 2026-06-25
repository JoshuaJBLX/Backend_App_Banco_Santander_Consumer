"""
Seed demo para la APP DE CLIENTES sobre bd_core_mobile.

Crea un cliente con acceso, su cuenta de ahorro, un crédito con cronograma,
movimientos, una tarjeta y notificaciones — para probar la app Flutter.

Uso (desde la raíz del proyecto, con venv activo):
    python -m scripts.seed_cliente_demo

Login en la app:  DNI = 12345678   ·   password = 1234
"""
import sys, os
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.cfg_database import SessionLocal
from app.core.cfg_security import hash_password
from app.models.mdl_asesores import Agencia, Asesor  # noqa: F401 (registra tablas FK)
from app.models.mdl_clientes import Cliente
from app.models.mdl_cliente_mobile import (
    UsuarioCliente, CrCuentaAhorro, CrCredito, CrCronogramaPago,
    CrMovimiento, Tarjeta, Notificacion,
)

DNI = "12345678"
COD_CREDITO = "CRED-8863"
COD_AHORRO = "0011-0235-0201436719"


def run():
    db = SessionLocal()
    try:
        usuario_existente = db.query(UsuarioCliente).filter(UsuarioCliente.username == DNI).first()
        if usuario_existente:
            print(f"El seed de cliente ya fue aplicado (DNI {DNI} existe). Nada que hacer.")
            return

        # ── Cliente + acceso ───────────────────────────────────
        cliente = db.query(Cliente).filter(Cliente.numero_documento == DNI).first()
        if not cliente:
            # Puede que exista C0001 de una corrida anterior fallida
            cliente = db.query(Cliente).filter(Cliente.cod_cliente == "C0001").first()
            if not cliente:
                cliente = Cliente(
                    cod_cliente="C0001",
                    numero_documento=DNI,
                    tipo_documento="DNI",
                    nombres="Guillermo Eduardo",
                    apellidos="Peña Garcia",
                    telefono="999993868",
                    email="nag@pucp.edu.pe",
                    tipo_negocio="bodega",
                    nombre_negocio="Bodega Independencia",
                    ingresos_estimados=11032.62,
                )
                db.add(cliente)
                db.flush()
            else:
                print(f"Cliente C0001 ya existe (de corrida anterior), se reutiliza.")
        else:
            print(f"Cliente {DNI} ya existe, se reutiliza.")

        # Verificar si este cliente ya tiene UsuarioCliente
        usuario_cliente = db.query(UsuarioCliente).filter(UsuarioCliente.cliente_id == cliente.id).first()
        if usuario_cliente:
            # Actualizar el hash de password para que sea válido
            usuario_cliente.password_hash = hash_password("1234")
            usuario_cliente.username = DNI
            usuario_cliente.activo = True
            usuario_cliente.intentos_fallidos = 0
            usuario_cliente.bloqueado = False
            print(f"UsuarioCliente para cliente_id {cliente.id} actualizado con password hash válido.")
        else:
            db.add(UsuarioCliente(
                cliente_id=cliente.id,
                username=DNI,
                password_hash=hash_password("1234"),
                activo=True,
            ))

        # ── Cuenta de ahorro ───────────────────────────────────
        db.add(CrCuentaAhorro(
            cod_cuenta_ahorro=COD_AHORRO,
            cliente_id=cliente.id,
            tipo_cuenta="Cuenta Independencia Andino",
            moneda="PEN",
            saldo_capital=24.64,
            saldo_interes=0.10,
            tea=0.50,
            estado="activa",
        ))

        # ── Crédito de consumo ─────────────────────────────────
        db.add(CrCredito(
            cod_cuenta_credito=COD_CREDITO,
            cliente_id=cliente.id,
            producto="Crédito Consumo",
            monto_desembolsado=102122.43,
            saldo_capital=68238.06,
            saldo_total=70238.06,
            dias_mora=0,
            calificacion_interna="normal",
            estado="vigente",
            fecha_desembolso=date(2023, 10, 10),
            tea=18.50,
            cuotas_total=72,
            cuotas_pagadas=30,
        ))

        # Cronograma: cuotas 29..38 (29-30 pagadas, 31 próxima)
        cuota_total = 1999.96
        capital = 1324.09
        interes = 638.26
        saldo = 69562.15
        for nro in range(29, 39):
            saldo = round(saldo - capital, 2)
            pagada = nro <= 30
            db.add(CrCronogramaPago(
                cod_cuenta_credito=COD_CREDITO,
                nro_cuota=nro,
                fecha_vencimiento=date(2026, 3 + (nro - 29), 10) if (3 + (nro - 29)) <= 12
                else date(2027, (3 + (nro - 29)) - 12, 10),
                monto_cuota=cuota_total,
                monto_capital=capital,
                monto_interes=interes,
                saldo=saldo,
                estado_cuota="pagada" if pagada else "pendiente",
                fecha_pago=date(2026, 1 + (nro - 29), 8) if pagada else None,
            ))

        # ── Movimientos ────────────────────────────────────────
        movs = [
            ("MOV-0001", "CRE", "Abono inmediato 808 guillermo",     "APP", 106.00, datetime(2026, 4, 30, 9, 5, tzinfo=timezone.utc)),
            ("MOV-0002", "DEB", "Transf inmediata al 808 852979",    "APP", 160.00, datetime(2026, 4, 29, 18, 20, tzinfo=timezone.utc)),
            ("MOV-0003", "DEB", "Electrocentro",                      "APP", 55.90,  datetime(2026, 4, 28, 11, 0, tzinfo=timezone.utc)),
            ("MOV-0004", "DEB", "Movistar cuenta financiera",        "APP", 83.90,  datetime(2026, 4, 28, 10, 45, tzinfo=timezone.utc)),
            ("MOV-0005", "DEB", "Movistar movil",                     "APP", 39.90,  datetime(2026, 4, 28, 10, 30, tzinfo=timezone.utc)),
            ("MOV-0006", "DEB", "ITF",                                "APP", 0.15,   datetime(2026, 4, 27, 9, 0, tzinfo=timezone.utc)),
            ("MOV-0007", "CRE", "Yape Pena Garcia",                   "APP", 150.00, datetime(2026, 4, 18, 14, 10, tzinfo=timezone.utc)),
        ]
        for cod, tipo, concepto, canal, monto, fecha in movs:
            db.add(CrMovimiento(
                cod_operacion=cod,
                cliente_id=cliente.id,
                cod_cuenta=COD_AHORRO,
                tipo=tipo,
                concepto=concepto,
                canal=canal,
                monto=monto,
                moneda="PEN",
                fecha_operacion=fecha,
            ))

        # ── Tarjeta ────────────────────────────────────────────
        db.add(Tarjeta(
            cliente_id=cliente.id,
            numero_enmascarado="**** **** **** 1649",
            marca="visa",
            linea_credito=5000.00,
            saldo_utilizado=0.00,
            fecha_corte=date(2026, 5, 18),
            fecha_pago=date(2026, 6, 5),
            estado="apagada",
        ))

        # ── Notificaciones ─────────────────────────────────────
        notifs = [
            ("Compra con tarjeta", "Consumo Claude.ai por S/ 72.57 (pendiente de procesar).", "compra"),
            ("Recordatorio de pago", "Tu cuota 31 de 72 vence el 10 may 2026 por S/ 1,999.96.", "recordatorio"),
            ("Oferta para ti", "Depósito a plazo hasta 3.85% TREA a 6 meses. ¡Haz crecer tus ahorros!", "oferta"),
        ]
        for titulo, cuerpo, tipo in notifs:
            db.add(Notificacion(
                destinatario_tipo="cliente",
                cliente_id=cliente.id,
                titulo=titulo,
                cuerpo=cuerpo,
                tipo=tipo,
                leida=False,
            ))

        db.commit()
        print(f"Seed cliente OK. Login en la app:  DNI={DNI}  password=1234")
    finally:
        db.close()


if __name__ == "__main__":
    run()

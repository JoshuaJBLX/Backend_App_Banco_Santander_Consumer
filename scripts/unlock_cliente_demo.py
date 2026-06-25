"""Unlock the demo cliente user and reset failed attempts."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.cfg_database import SessionLocal
from app.models.mdl_cliente_mobile import UsuarioCliente

db = SessionLocal()

DNI = "12345678"
usuario = db.query(UsuarioCliente).filter(UsuarioCliente.username == DNI).first()

if usuario:
    usuario.intentos_fallidos = 0
    usuario.bloqueado = False
    db.commit()
    print(f"Usuario {DNI} desbloqueado. intentos_fallidos=0, bloqueado=False")
else:
    print(f"Usuario {DNI} no encontrado")

db.close()
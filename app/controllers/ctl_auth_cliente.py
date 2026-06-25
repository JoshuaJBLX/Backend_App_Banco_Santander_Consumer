from typing import Optional
"""Controlador de autenticación de la app de clientes (login con DNI)."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.core.cfg_security import verify_password, create_access_token
from app.repositories import rep_cliente

MAX_INTENTOS = 5


def login(db: Session, numero_documento: str, password: str) -> Optional[dict]:
    usuario = rep_cliente.get_usuario_by_username(db, numero_documento)
    if not usuario or not usuario.activo:
        return None

    # Bloqueo por intentos fallidos (RF-04)
    if usuario.bloqueado:
        return {"_bloqueado": True}

    if not verify_password(password, usuario.password_hash):
        usuario.intentos_fallidos = (usuario.intentos_fallidos or 0) + 1
        if usuario.intentos_fallidos >= MAX_INTENTOS:
            usuario.bloqueado = True
        db.commit()
        return None

    # Login correcto: resetea contador y marca último acceso
    usuario.intentos_fallidos = 0
    usuario.ultimo_acceso = datetime.now(timezone.utc)
    db.commit()

    cliente = rep_cliente.get_cliente(db, usuario.cliente_id)
    token = create_access_token({
        "sub": usuario.username,
        "cliente_id": str(usuario.cliente_id),
        "nombre": f"{cliente.nombres} {cliente.apellidos}" if cliente else usuario.username,
    })
    return {
        "access_token": token,
        "token_type": "bearer",
        "cliente": cliente,
    }


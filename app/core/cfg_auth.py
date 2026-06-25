from typing import Optional
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.cfg_security import decode_token

bearer = HTTPBearer(auto_error=True)

def get_current_asesor(
    cred: HTTPAuthorizationCredentials = Depends(bearer),
) -> dict:
    """Devuelve el payload del asesor autenticado a partir del token Bearer."""
    payload = decode_token(cred.credentials)
    if not payload or "asesor_id" not in payload:
        raise HTTPException(status_code=401, detail="Token invalido o expirado")
    return payload


def get_current_cliente(
    cred: HTTPAuthorizationCredentials = Depends(bearer),
) -> dict:
    """Devuelve el payload del cliente autenticado (app de clientes)."""
    payload = decode_token(cred.credentials)
    if not payload or "cliente_id" not in payload:
        raise HTTPException(status_code=401, detail="Token invalido o expirado")
    return payload


"""Quick script to check client info in BD."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.cfg_database import SessionLocal
from app.models.mdl_clientes import Cliente
from app.models.mdl_cliente_mobile import UsuarioCliente

db = SessionLocal()

# Check clients
print("=== CLIENTES ===")
for c in db.query(Cliente).all():
    print(f"id={c.id} cod={c.cod_cliente} dni={c.numero_documento} nombres={c.nombres}")

# Check usuarios_cliente
print("\n=== USUARIOS_CLIENTE ===")
for u in db.query(UsuarioCliente).all():
    print(f"id={u.id} cliente_id={u.cliente_id} username={u.username} hash={repr(u.password_hash[:50])}...")

db.close()
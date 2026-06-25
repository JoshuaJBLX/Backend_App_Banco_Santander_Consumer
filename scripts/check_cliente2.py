"""Quick script to check client DNI=12345678 info."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.cfg_database import SessionLocal
from app.models.mdl_clientes import Cliente
from app.models.mdl_cliente_mobile import UsuarioCliente
from app.core.cfg_security import hash_password

db = SessionLocal()

# Find client by DNI
c = db.query(Cliente).filter(Cliente.numero_documento == '12345678').first()
if c:
    print(f"Cliente encontrado: id={c.id} cod={c.cod_cliente} dni={c.numero_documento}")
    
    # Check if UsuarioCliente exists
    u = db.query(UsuarioCliente).filter(UsuarioCliente.cliente_id == c.id).first()
    if u:
        print(f"UsuarioCliente existe: username={u.username} hash={repr(u.password_hash[:60])}")
    else:
        print("UsuarioCliente NO existe. Creando...")
        hashed = hash_password("1234")
        print(f"Hash generado: {repr(hashed)}")
        u = UsuarioCliente(
            cliente_id=c.id,
            username="12345678",
            password_hash=hashed,
            activo=True,
        )
        db.add(u)
        db.commit()
        print("UsuarioCliente creado OK!")
else:
    print("Cliente con DNI 12345678 NO encontrado en BD")

db.close()
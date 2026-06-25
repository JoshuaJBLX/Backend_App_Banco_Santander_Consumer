import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def run():
    # 1. Connect to default postgres DB to create the new database
    conn = psycopg2.connect(
        dbname="postgres",
        user="postgres",
        password="postgres",
        host="localhost",
        port="5432"
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    # Check if bd_core_financiero exists
    cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'bd_core_financiero';")
    exists = cursor.fetchone()
    if not exists:
        print("Creating database bd_core_financiero...")
        cursor.execute("CREATE DATABASE bd_core_financiero;")
    else:
        print("Database bd_core_financiero already exists.")
    
    cursor.close()
    conn.close()

    # 2. Connect to bd_core_financiero to create the schema
    conn = psycopg2.connect(
        dbname="bd_core_financiero",
        user="postgres",
        password="postgres",
        host="localhost",
        port="5432"
    )
    cursor = conn.cursor()

    # Create dcliente table
    create_dcliente = """
    CREATE TABLE IF NOT EXISTS dcliente (
        pkcliente SERIAL PRIMARY KEY,
        codcliente VARCHAR(20) UNIQUE NOT NULL,
        nomcliente VARCHAR(100) NOT NULL,
        pkclasepersona INTEGER,
        codclasepersona VARCHAR(10),
        desclasepersona VARCHAR(100),
        fechaingresocaja DATE,
        pktipodocumentoidentidad INTEGER,
        codtipodocumentoidentidad VARCHAR(10),
        destipodocumentoidentidad VARCHAR(100),
        numerodocumentoidentidad VARCHAR(15) UNIQUE NOT NULL
    );
    """
    cursor.execute(create_dcliente)

    # Create dsolicitud table
    create_dsolicitud = """
    CREATE TABLE IF NOT EXISTS dsolicitud (
        pksolicitud SERIAL PRIMARY KEY,
        codsolicitud VARCHAR(20) UNIQUE NOT NULL,
        pkcliente INTEGER REFERENCES dcliente(pkcliente),
        pksolicitudestado INTEGER,
        pkmoneda INTEGER,
        pkproducto INTEGER,
        montosolicitudcredito NUMERIC(12,2),
        nrocuotasolicitud INTEGER,
        plazosolicitudcredito INTEGER,
        fechasolicitudcredito DATE,
        pkagencia INTEGER,
        pkasesor INTEGER,
        estado VARCHAR(30) DEFAULT 'En Evaluacion',
        motivo_rechazo TEXT,
        condicion_adicional TEXT
    );
    """
    cursor.execute(create_dsolicitud)

    # Commit and close
    conn.commit()
    cursor.close()
    conn.close()
    print("Database bd_core_financiero setup completed successfully!")

if __name__ == "__main__":
    run()

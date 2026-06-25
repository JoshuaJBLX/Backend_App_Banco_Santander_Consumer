-- ============================================================================
-- bd_core_mobile — Capa operacional de canales moviles (Banco Andino)
-- ----------------------------------------------------------------------------
-- Base PostgreSQL servida por un backend FastAPI "mobile" (puerto sugerido 8003).
-- La consumen DOS apps moviles:
--   - App Fuerza de Ventas (Flutter)   -> originacion en campo (escritura)
--   - App Clientes appbanco_s8 (Kotlin) -> autoservicio (consulta + solicitudes)
--
-- Relacion con el nucleo bd_core_financiero (core 8001 + homebanking 8002):
--   - mobile -> core : solicitudes capturadas se PROMUEVEN al core via servicio
--                      (cola sync_outbox -> dsolicitud / dcliente del core).
--   - core -> mobile : estados, saldos, cronograma y movimientos se REPLICAN a
--                      las tablas espejo (prefijo cr_) para consulta offline.
--
-- Convencion de nombres: snake_case OLTP, PK UUID, FKs con sufijo _id.
-- Puente al core: columnas cod_* que mapean a los cod* del core
-- (codcliente, codsolicitud, codcuentacredito...). NO se comparten PKs.
-- ============================================================================

-- Requiere PostgreSQL 13+ (gen_random_uuid en pgcrypto / nativo en PG18).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================================
-- GRUPO 1 — IDENTIDAD / CATALOGOS  (referencia, algunos espejo del core)
-- ============================================================================

CREATE TABLE agencias (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cod_agencia     VARCHAR(20) UNIQUE NOT NULL,   -- = dagencia.codagencia (core)
    nombre          VARCHAR(100) NOT NULL,
    region          VARCHAR(50),
    lat             DECIMAL(10,7),
    lng             DECIMAL(10,7),
    activa          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Asesores de negocio (usuarios de la app de fuerza de ventas).
CREATE TABLE asesores (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cod_asesor        VARCHAR(20) UNIQUE,           -- = dasesor.codasesor (core)
    codigo_empleado   VARCHAR(10) UNIQUE NOT NULL,  -- login (RF-01)
    nombres           VARCHAR(100) NOT NULL,
    apellidos         VARCHAR(100) NOT NULL,
    agencia_id        UUID REFERENCES agencias(id),
    perfil            VARCHAR(20) NOT NULL DEFAULT 'operador'
                      CHECK (perfil IN ('operador','super_operador','supervisor','administrador')),
    password_hash     TEXT NOT NULL,
    token_fcm         TEXT,                          -- notificaciones push (RF-73)
    intentos_fallidos INTEGER NOT NULL DEFAULT 0,    -- bloqueo (RF-04)
    bloqueado_hasta   TIMESTAMPTZ,
    activo            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Clientes. Espejo del core (dcliente) + datos capturados en campo.
CREATE TABLE clientes (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cod_cliente              VARCHAR(20) UNIQUE,      -- = dcliente.codcliente (core); NULL si es prospecto nuevo
    numero_documento         VARCHAR(15) UNIQUE NOT NULL,
    tipo_documento           VARCHAR(5) NOT NULL DEFAULT 'DNI' CHECK (tipo_documento IN ('DNI','RUC','CE')),
    nombres                  VARCHAR(100) NOT NULL,
    apellidos                VARCHAR(100) NOT NULL,
    fecha_nacimiento         DATE,
    estado_civil             VARCHAR(15),
    telefono                 VARCHAR(15),
    email                    VARCHAR(100),
    direccion                TEXT,
    tipo_negocio             VARCHAR(30),
    nombre_negocio           VARCHAR(100),
    antiguedad_negocio_meses INTEGER,
    ingresos_estimados       DECIMAL(12,2),
    lat                      DECIMAL(10,7),
    lng                      DECIMAL(10,7),
    calificacion_sbs         VARCHAR(15),             -- Normal/CPP/Deficiente/Dudoso/Perdida
    es_prospecto             BOOLEAN NOT NULL DEFAULT FALSE, -- aun no existe en el core
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- GRUPO 2 — ESPEJO DEL CORE (read-only en mobile; sync core -> mobile)
--   Prefijo cr_ (core-replica). Se actualizan por el servicio de sync.
-- ============================================================================

-- Espejo de dcuentacredito + fagcuentacredito (posicion del credito).
CREATE TABLE cr_creditos (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cod_cuenta_credito   VARCHAR(30) UNIQUE NOT NULL,  -- = dcuentacredito.codcuentacredito
    cliente_id           UUID NOT NULL REFERENCES clientes(id),
    producto             VARCHAR(40),
    monto_desembolsado   DECIMAL(12,2),
    saldo_capital        DECIMAL(12,2),
    saldo_total          DECIMAL(12,2),
    dias_mora            INTEGER NOT NULL DEFAULT 0,
    calificacion_interna VARCHAR(20),
    estado               VARCHAR(20),                 -- vigente/pagado/vencido/castigado
    fecha_desembolso     DATE,
    tea                  DECIMAL(5,2),
    cuotas_total         INTEGER,
    cuotas_pagadas       INTEGER,
    sync_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Espejo de fplanpagomes (cronograma de cuotas).
CREATE TABLE cr_cronograma_pagos (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cod_cuenta_credito  VARCHAR(30) NOT NULL REFERENCES cr_creditos(cod_cuenta_credito) ON DELETE CASCADE,
    nro_cuota           INTEGER NOT NULL,
    fecha_vencimiento   DATE NOT NULL,
    monto_cuota         DECIMAL(10,2),
    monto_capital       DECIMAL(10,2),
    monto_interes       DECIMAL(10,2),
    saldo               DECIMAL(12,2),
    estado_cuota        VARCHAR(20),                 -- pendiente/pagada/vencida
    fecha_pago          DATE,
    sync_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cod_cuenta_credito, nro_cuota)
);

-- Espejo de dcuentaahorro + fcuentaahorro (para app de clientes).
CREATE TABLE cr_cuentas_ahorro (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cod_cuenta_ahorro   VARCHAR(30) UNIQUE NOT NULL,  -- = dcuentaahorro.codcuentaahorro
    cliente_id          UUID NOT NULL REFERENCES clientes(id),
    tipo_cuenta         VARCHAR(40),
    moneda              VARCHAR(3) DEFAULT 'PEN',
    saldo_capital       DECIMAL(12,2),
    saldo_interes       DECIMAL(12,2),
    tea                 DECIMAL(5,2),
    estado              VARCHAR(20),
    sync_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Espejo de foperaciones (movimientos: pagos, transferencias) para app clientes.
CREATE TABLE cr_movimientos (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cod_operacion       VARCHAR(40) UNIQUE NOT NULL,  -- = foperaciones.codkardex
    cliente_id          UUID NOT NULL REFERENCES clientes(id),
    cod_cuenta          VARCHAR(30),                  -- credito o ahorro
    tipo                VARCHAR(10),                  -- DEB/CRE/TRF
    concepto            VARCHAR(60),
    canal               VARCHAR(20),                  -- APP/WEB/CAJA
    monto               DECIMAL(12,2) NOT NULL,
    moneda              VARCHAR(3) DEFAULT 'PEN',
    fecha_operacion     TIMESTAMPTZ NOT NULL,
    sync_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- GRUPO 3 — OPERACION FUERZA DE VENTAS (origen; escribe la app Flutter)
-- ============================================================================

CREATE TABLE creditos_preaprobados (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id           UUID NOT NULL REFERENCES clientes(id),
    asesor_id            UUID REFERENCES asesores(id),
    monto_maximo         DECIMAL(12,2) NOT NULL,
    plazo_sugerido_meses INTEGER,
    tea_referencial      DECIMAL(5,2),
    score_confianza      INTEGER CHECK (score_confianza BETWEEN 0 AND 100),
    vigente              BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_calculo        DATE,
    fecha_vencimiento    DATE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Cartera asignada del dia (RF-09). UNIQUE evita duplicar cliente por dia.
CREATE TABLE cartera_diaria (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asesor_id          UUID NOT NULL REFERENCES asesores(id),
    cliente_id         UUID NOT NULL REFERENCES clientes(id),
    agencia_id         UUID REFERENCES agencias(id),
    fecha_asignacion   DATE NOT NULL,
    tipo_gestion       VARCHAR(30) NOT NULL
                       CHECK (tipo_gestion IN ('RENOVACION','AMPLIACION','NUEVA_SOLICITUD',
                                               'SEGUIMIENTO','RECUPERACION_MORA','DESERTOR')),
    prioridad          VARCHAR(10) DEFAULT 'normal' CHECK (prioridad IN ('alta','media','normal')),
    score_prioridad    INTEGER DEFAULT 0,
    monto_credito      DECIMAL(12,2),
    estado_visita      VARCHAR(20) DEFAULT 'pendiente'
                       CHECK (estado_visita IN ('pendiente','visitado','no_encontrado','reagendado','negocio_cerrado')),
    resultado_visita   VARCHAR(30),
    observacion_visita TEXT,
    timestamp_visita   TIMESTAMPTZ,
    lat_visita         DECIMAL(10,7),
    lng_visita         DECIMAL(10,7),
    orden_manual       INTEGER,
    UNIQUE (asesor_id, cliente_id, fecha_asignacion)
);

CREATE TABLE campanas_activas (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asesor_id         UUID NOT NULL REFERENCES asesores(id),
    cliente_id        UUID NOT NULL REFERENCES clientes(id),
    tipo              VARCHAR(30),                 -- renovacion/ampliacion/producto_paralelo
    monto_ofertado    DECIMAL(12,2),
    fecha_vencimiento DATE,
    activa            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Solicitud de credito capturada en campo (M5). Se promueve al core (dsolicitud).
CREATE TABLE solicitudes_credito (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    numero_expediente        VARCHAR(20) UNIQUE,        -- asignado por el core al promover
    cod_solicitud_core       VARCHAR(20),               -- = dsolicitud.codsolicitud tras promocion
    asesor_id                UUID NOT NULL REFERENCES asesores(id),
    cliente_id               UUID NOT NULL REFERENCES clientes(id),
    agencia_id               UUID REFERENCES agencias(id),
    canal                    VARCHAR(15) NOT NULL DEFAULT 'asesor'  -- asesor | cliente (appbanco)
                             CHECK (canal IN ('asesor','cliente')),
    -- negocio
    tipo_negocio             VARCHAR(30),
    nombre_negocio           VARCHAR(100),
    actividad_economica      VARCHAR(10),               -- CIIU
    antiguedad_negocio_meses INTEGER,
    ingresos_estimados       DECIMAL(12,2),
    gastos_mensuales         DECIMAL(12,2),
    patrimonio_estimado      DECIMAL(12,2),
    -- co-deudores
    tiene_conyuge            BOOLEAN DEFAULT FALSE,
    conyuge_json             JSONB,
    tiene_garante            BOOLEAN DEFAULT FALSE,
    garante_json             JSONB,
    -- condiciones
    monto_solicitado         DECIMAL(12,2) NOT NULL,
    plazo_meses              INTEGER,
    moneda                   VARCHAR(3) DEFAULT 'PEN',
    tipo_cuota               VARCHAR(10) DEFAULT 'mensual',
    garantia                 VARCHAR(20),
    destino_credito          TEXT,
    cuota_estimada           DECIMAL(10,2),
    tea_referencial          DECIMAL(5,2),
    -- ciclo de estado (mobile + reflejo del core)
    estado                   VARCHAR(30) NOT NULL DEFAULT 'borrador'
                             CHECK (estado IN ('borrador','enviado','recibido_comite','en_evaluacion',
                                               'aprobado','condicionado','rechazado','desembolsado')),
    monto_aprobado           DECIMAL(12,2),
    motivo_rechazo           TEXT,
    condicion_adicional      TEXT,
    analista_asignado        VARCHAR(100),
    firma_cliente_base64     TEXT,
    lat_captura              DECIMAL(10,7),
    lng_captura              DECIMAL(10,7),
    pendiente_sync           BOOLEAN NOT NULL DEFAULT FALSE,  -- offline-first (RF-17)
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE solicitudes_documentos (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solicitud_id    UUID NOT NULL REFERENCES solicitudes_credito(id) ON DELETE CASCADE,
    tipo_documento  VARCHAR(40) NOT NULL,    -- dni_anverso/dni_reverso/ruc/recibo_servicios/foto_negocio/foto_visita/contrato_arrendamiento
    storage_url     TEXT,                    -- ruta en almacenamiento de archivos
    tamanio_kb      INTEGER,
    nitidez_score   DECIMAL(5,2),            -- varianza de Laplaciano (RF-54)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE consultas_buro (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asesor_id                   UUID NOT NULL REFERENCES asesores(id),
    cliente_id                  UUID NOT NULL REFERENCES clientes(id),
    solicitud_id                UUID REFERENCES solicitudes_credito(id),
    dni_consultado              VARCHAR(15) NOT NULL,
    calificacion_sbs            VARCHAR(20),
    entidades_con_deuda         INTEGER,
    deuda_total_pen             DECIMAL(12,2),
    mayor_deuda                 DECIMAL(12,2),
    dias_mayor_mora             INTEGER,
    en_lista_negra              BOOLEAN NOT NULL DEFAULT FALSE,
    motivo_bloqueo              TEXT,
    resultado_json             JSONB,
    firma_consentimiento_base64 TEXT,        -- Ley 29733 (RF-57)
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE acciones_cobranza (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asesor_id         UUID NOT NULL REFERENCES asesores(id),
    cliente_id        UUID NOT NULL REFERENCES clientes(id),
    cod_cuenta_credito VARCHAR(30) REFERENCES cr_creditos(cod_cuenta_credito),
    tipo_gestion      VARCHAR(20) CHECK (tipo_gestion IN ('visita','llamada','mensaje')),
    resultado         VARCHAR(30) CHECK (resultado IN ('compromiso_pago','pago_parcial','sin_contacto','se_niega')),
    monto_pagado      DECIMAL(12,2),
    fecha_compromiso  DATE,
    monto_compromiso  DECIMAL(12,2),
    observaciones     TEXT,
    lat               DECIMAL(10,7),
    lng               DECIMAL(10,7),
    timestamp_gestion TIMESTAMPTZ NOT NULL DEFAULT now(),
    pendiente_sync    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE alertas_cartera (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asesor_id   UUID NOT NULL REFERENCES asesores(id),
    cliente_id  UUID NOT NULL REFERENCES clientes(id),
    tipo_alerta VARCHAR(30) CHECK (tipo_alerta IN ('primer_dia_mora','mora_30d','mora_60d','pago_parcial','pago_total')),
    mensaje     TEXT,
    leida       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE solicitudes_notas_internas (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solicitud_id UUID NOT NULL REFERENCES solicitudes_credito(id) ON DELETE CASCADE,
    asesor_id    UUID NOT NULL REFERENCES asesores(id),
    contenido    TEXT NOT NULL CHECK (char_length(contenido) <= 500),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- GRUPO 4 — APP DE CLIENTES (autoservicio appbanco_s8)
-- ============================================================================

-- Credenciales del cliente (equivalente a usuarios_homebanking del core).
CREATE TABLE usuarios_cliente (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id        UUID NOT NULL UNIQUE REFERENCES clientes(id),
    username          VARCHAR(50) UNIQUE NOT NULL,   -- normalmente el numero_documento
    password_hash     TEXT NOT NULL,
    token_fcm         TEXT,
    activo            BOOLEAN NOT NULL DEFAULT TRUE,
    bloqueado         BOOLEAN NOT NULL DEFAULT FALSE,
    intentos_fallidos INTEGER NOT NULL DEFAULT 0,
    ultimo_acceso     TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Tarjetas de credito (la app appbanco_s8 las muestra; el core no las modela aun).
CREATE TABLE tarjetas (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id          UUID NOT NULL REFERENCES clientes(id),
    numero_enmascarado  VARCHAR(25) NOT NULL,         -- **** **** **** 1234
    marca               VARCHAR(20),                  -- visa/mastercard
    linea_credito       DECIMAL(12,2),
    saldo_utilizado     DECIMAL(12,2),
    fecha_corte         DATE,
    fecha_pago          DATE,
    estado              VARCHAR(20) DEFAULT 'activa',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Operaciones iniciadas por el cliente (pago de cuota, transferencia).
-- Se PROMUEVEN al core (foperaciones) via sync_outbox.
CREATE TABLE operaciones_cliente (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id         UUID NOT NULL REFERENCES clientes(id),
    cod_cuenta_origen  VARCHAR(30),
    cod_cuenta_destino VARCHAR(30),
    tipo               VARCHAR(20) CHECK (tipo IN ('pago_cuota','transferencia','recarga')),
    monto              DECIMAL(12,2) NOT NULL,
    moneda             VARCHAR(3) DEFAULT 'PEN',
    estado             VARCHAR(20) NOT NULL DEFAULT 'pendiente'
                       CHECK (estado IN ('pendiente','enviada','confirmada','rechazada')),
    cod_operacion_core VARCHAR(40),                   -- = foperaciones.codkardex tras promocion
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Notificaciones para ambas apps (push / centro de notificaciones).
CREATE TABLE notificaciones (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    destinatario_tipo VARCHAR(10) NOT NULL CHECK (destinatario_tipo IN ('asesor','cliente')),
    asesor_id    UUID REFERENCES asesores(id),
    cliente_id   UUID REFERENCES clientes(id),
    titulo       VARCHAR(120) NOT NULL,
    cuerpo       TEXT,
    tipo         VARCHAR(40),    -- recibido_comite/aprobado/rechazado/desembolsado/mora/...
    data_json    JSONB,
    leida        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- GRUPO 5 — PUENTE DE SINCRONIZACION mobile <-> core
-- ============================================================================

-- Cola de salida: entidades de mobile que deben promoverse/aplicarse al core.
-- El servicio de promocion (FastAPI/worker) la lee, escribe en bd_core_financiero
-- y marca el resultado.
CREATE TABLE sync_outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entidad         VARCHAR(40) NOT NULL,   -- solicitudes_credito / clientes / operaciones_cliente / acciones_cobranza
    entidad_id      UUID NOT NULL,          -- id local de la fila
    operacion       VARCHAR(10) NOT NULL CHECK (operacion IN ('create','update','delete')),
    payload         JSONB NOT NULL,         -- snapshot a enviar al core
    estado          VARCHAR(15) NOT NULL DEFAULT 'pendiente'
                    CHECK (estado IN ('pendiente','procesando','aplicado','error')),
    intentos        INTEGER NOT NULL DEFAULT 0,
    core_ref        VARCHAR(40),            -- cod* devuelto por el core (codsolicitud, codkardex...)
    ultimo_error    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    procesado_at    TIMESTAMPTZ
);

-- Bitacora de sincronizacion (auditoria de ambas direcciones).
CREATE TABLE sync_log (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    direccion    VARCHAR(15) NOT NULL CHECK (direccion IN ('mobile_a_core','core_a_mobile')),
    entidad      VARCHAR(40) NOT NULL,
    referencia   VARCHAR(60),
    resultado    VARCHAR(15) NOT NULL CHECK (resultado IN ('ok','error')),
    detalle      TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- INDICES recomendados
-- ============================================================================
CREATE INDEX idx_cartera_asesor_fecha   ON cartera_diaria (asesor_id, fecha_asignacion);
CREATE INDEX idx_cartera_score          ON cartera_diaria (score_prioridad DESC);
CREATE INDEX idx_solicitudes_asesor     ON solicitudes_credito (asesor_id, created_at DESC);
CREATE INDEX idx_solicitudes_estado     ON solicitudes_credito (estado);
CREATE INDEX idx_solicitudes_pendsync   ON solicitudes_credito (pendiente_sync) WHERE pendiente_sync = TRUE;
CREATE INDEX idx_cronograma_credito     ON cr_cronograma_pagos (cod_cuenta_credito);
CREATE INDEX idx_movimientos_cliente    ON cr_movimientos (cliente_id, fecha_operacion DESC);
CREATE INDEX idx_alertas_asesor_noleida ON alertas_cartera (asesor_id) WHERE leida = FALSE;
CREATE INDEX idx_outbox_pendiente       ON sync_outbox (estado) WHERE estado = 'pendiente';

-- ============================================================================
-- FIN bd_core_mobile
-- ============================================================================

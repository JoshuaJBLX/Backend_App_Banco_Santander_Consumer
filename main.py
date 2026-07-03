from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.routes import (
    rtr_auth, rtr_cartera, rtr_ficha, rtr_cobranza, rtr_preeval, rtr_buro,
    rtr_solicitudes, rtr_reportes, rtr_alertas, rtr_campanas, rtr_sync,
    rtr_cliente,
)
from app.core.cfg_database import get_db
from app.core.cfg_auth import get_current_asesor
from app.routes.rtr_preeval import PreEvalIn, PreEvalOut, pre_evaluar

app = FastAPI(
    title="Core Mobile — Banco Andino",
    description="Capa operacional de canales moviles: fuerza de ventas en campo "
                "y app de clientes. Alimenta al core bd_core_financiero.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app-core-banco-santander.vercel.app",
        "https://app-core-banco-santander-git-main-bl-inderex.vercel.app",
        "https://app-core-banco-santander-ody11kr7n-bl-inderex.vercel.app",
        "http://localhost:5173",
        "http://localhost:8003",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rtr_auth.router,    prefix="/auth",     tags=["Auth"])
app.include_router(rtr_cartera.router, prefix="/cartera",  tags=["Cartera"])
app.include_router(rtr_ficha.router,   prefix="/clientes", tags=["Ficha"])
app.include_router(rtr_cobranza.router, prefix="/cobranza", tags=["Cobranza"])
app.include_router(rtr_preeval.router, prefix="/pre-evaluar", tags=["PreEvaluacion"])
app.include_router(rtr_buro.router,    prefix="/buro",      tags=["Buro"])
app.include_router(rtr_solicitudes.router, prefix="/solicitudes", tags=["Solicitudes"])
app.include_router(rtr_reportes.router, prefix="/reportes", tags=["Reportes"])
app.include_router(rtr_alertas.router, prefix="/alertas", tags=["Alertas"])
app.include_router(rtr_campanas.router, prefix="/campanas", tags=["Campanas"])
app.include_router(rtr_sync.router, prefix="/sync", tags=["Sync (Puente al Core)"])

# App de clientes (appbanco / Flutter clientes) — login DNI + productos
app.include_router(rtr_cliente.router, prefix="/cliente", tags=["Cliente (App)"])


# ── Alias de compatibilidad para la App Fuerza de Ventas ──────────────────────
# La app Flutter puede llamar a /pre-evaluacion o /solicitudes/pre-evaluacion
# en lugar de /pre-evaluar. Redirigimos al mismo handler de pre-evaluacion.

@app.post("/pre-evaluacion", response_model=PreEvalOut)
def pre_evaluacion_alias(
    data: PreEvalIn,
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Alias: POST /pre-evaluacion → pre-evaluar"""
    return pre_evaluar(data, db, asesor)


@app.post("/api/pre-evaluacion", response_model=PreEvalOut)
def api_pre_evaluacion_alias(
    data: PreEvalIn,
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Alias: POST /api/pre-evaluacion → pre-evaluar"""
    return pre_evaluar(data, db, asesor)


@app.post("/solicitudes/pre-evaluacion", response_model=PreEvalOut)
def solicitudes_pre_evaluacion_alias(
    data: PreEvalIn,
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Alias: POST /solicitudes/pre-evaluacion → pre-evaluar"""
    return pre_evaluar(data, db, asesor)


@app.get("/")
def root():
    return {"sistema": "Core Mobile Banco Andino", "version": "1.0.0", "status": "ok"}

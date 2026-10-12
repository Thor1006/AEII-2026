"""FastAPI control plane and WebSocket telemetry stream for the local prototype."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .engine import SimulationEngine
from .schemas import TelemetryFrame

PROJECT_ROOT = Path(__file__).resolve().parents[2]
engine = SimulationEngine()


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(engine.run())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="TrueRehab-RF Prototype API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "simulation", "stream": "websocket"}


@app.get("/api/state", response_model=TelemetryFrame)
def state() -> TelemetryFrame:
    return engine.snapshot()


@app.post("/api/session/start", response_model=TelemetryFrame)
def start_session() -> TelemetryFrame:
    return engine.start()


@app.post("/api/session/stop", response_model=TelemetryFrame)
def stop_session() -> TelemetryFrame:
    return engine.stop()


@app.post("/api/session/reset", response_model=TelemetryFrame)
def reset_session() -> TelemetryFrame:
    return engine.reset()


@app.get("/api/session/export.csv")
def export_session() -> Response:
    return Response(
        content=engine.export_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{engine.session_id}.csv"'},
    )


@app.post("/api/session/save")
def save_session() -> dict[str, str]:
    destination = engine.save_session(PROJECT_ROOT / "data")
    return {"status": "saved", "path": str(destination.relative_to(PROJECT_ROOT))}


@app.websocket("/ws/telemetry")
async def telemetry(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(engine.snapshot().model_dump())
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        return
    except (ConnectionError, RuntimeError):
        return


if (PROJECT_ROOT / "dist").is_dir():
    app.mount("/", StaticFiles(directory=PROJECT_ROOT / "dist", html=True), name="dashboard")

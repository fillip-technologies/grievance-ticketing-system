import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import AsyncSessionLocal, engine
from .routers import ai, auth, mailboxes, organizations, public, sections, superadmin, team, tickets
from .scheduler import start_scheduler, stop_scheduler
from .seed import ensure_superadmin

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("grievance_desk.startup")

settings = get_settings()

_KNOWN_PLACEHOLDER_SECRETS = {
    "jwt_secret": "CHANGE_ME_super_secret_grievance_jwt",
    "superadmin_password": "ChangeMe_SuperAdmin_2026!",
}


def _warn_on_placeholder_secrets() -> None:
    """Loudly flags default/placeholder secrets so they don't silently ship to production."""
    offenders = [name for name, placeholder in _KNOWN_PLACEHOLDER_SECRETS.items() if getattr(settings, name) == placeholder]
    if not settings.encryption_key.strip():
        offenders.append("encryption_key (unset — derived from jwt_secret)")
    if offenders and not settings.debug:
        logger.warning(
            "Starting with default/placeholder secret(s): %s. Set real values via environment "
            "variables before exposing this instance publicly.", ", ".join(offenders),
        )


def _run_migrations() -> None:
    """Runs `alembic upgrade head` synchronously. Alembic's async env.py drives its own
    asyncio.run() internally, so this must be called off the running event loop (see the
    run_in_threadpool call below) — calling it directly from the lifespan coroutine would
    raise "asyncio.run() cannot be called from a running event loop"."""
    backend_dir = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _warn_on_placeholder_secrets()
    # Schema is managed by Alembic migrations (backend/alembic/versions/), not create_all —
    # the baseline migration is checkfirst=True so this is also safe to run against an
    # existing pre-Alembic database (it stamps it as current instead of erroring).
    await run_in_threadpool(_run_migrations)
    async with AsyncSessionLocal() as session:
        await ensure_superadmin(session)
    start_scheduler()
    yield
    stop_scheduler()
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(organizations.router)
app.include_router(team.router)
app.include_router(sections.router)
app.include_router(superadmin.router)
app.include_router(tickets.router)
app.include_router(mailboxes.router)
app.include_router(ai.router)
app.include_router(public.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}



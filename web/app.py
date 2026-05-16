from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from web3_auditor.api.routes import router
from web3_auditor.db.database import init_db

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(asctime)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Initializing Institutional Web3 Auditor Protocol...")
    init_db()
    yield
    logger.info("Shutting down protocol...")


app = FastAPI(
    title="KhomDev Auditor",
    description="High-fidelity Web3 & Python security analysis — Vyper 0.4+ and Solidity 0.8.x.",
    version="1.0.0",
    lifespan=lifespan
)

BASE_DIR = Path(__file__).resolve().parent
app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)

app.include_router(router)

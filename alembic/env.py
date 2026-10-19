import os
import sys
from pathlib import Path

# Insert the project root onto sys.path so `app.db.models` is importable
# both inside Docker (where /app is the project root) and when running
# `alembic upgrade head` locally outside Docker.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.models import Base

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://medichain:medichain@db:5432/medichain"
)


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    connectable = create_async_engine(DB_URL)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


asyncio.run(run_migrations_online())

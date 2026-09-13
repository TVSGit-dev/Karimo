"""Environnement Alembic.

L'URL de la base vient de karimo.config, qui la lit dans l'environnement : elle
n'est jamais ecrite dans alembic.ini (SPEC 9, les secrets hors du depot).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from karimo.config import database_url
from karimo.db.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", database_url())

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite ne sait pas ALTER TABLE : le mode batch recree la table.
            # Indispensable des le jalon 2, quand le schema bougera.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

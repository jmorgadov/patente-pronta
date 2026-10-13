from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, SQLModel, create_engine

from patente_pronta import bank
from patente_pronta.settings import Settings, load_settings
from patente_pronta.web import PACKAGE_DIR, router


def create_app(settings: Settings) -> FastAPI:
    engine = create_engine(
        f"sqlite:///{settings.db_path}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        bank.load_if_empty(session, settings.data_dir)
    app = FastAPI(title="Patente Pronta")
    app.state.engine = engine
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
    app.mount("/figures", StaticFiles(directory=settings.data_dir / "figures"), name="figures")
    app.include_router(router)
    return app


def create_app_from_env() -> FastAPI:
    return create_app(load_settings())

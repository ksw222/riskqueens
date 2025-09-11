from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base

class Settings(BaseSettings):
    PG_USER: str
    PG_PASSWORD: str
    PG_HOST: str = "localhost"
    PG_PORT: int = 5432
    PG_DB: str

    class Config:
        env_file = ".env"

settings = Settings()

# 👇 URL.create가 username/password 등 안전하게 인코딩해줍니다.
db_url = URL.create(
    "postgresql+psycopg2",
    username=settings.PG_USER,
    password=settings.PG_PASSWORD,
    host=settings.PG_HOST,
    port=settings.PG_PORT,
    database=settings.PG_DB,
)

engine = create_engine(db_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

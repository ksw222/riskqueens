from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base
from pydantic import Field

class Settings(BaseSettings):
    PG_USER: str
    PG_PASSWORD: str
    PG_HOST: str = "localhost"
    PG_PORT: int = 5432
    PG_DB: str

        # --- OpenAI (여기 추가) ---
    OPENAI_API_KEY: str | None = None
    OPENAI_API_BASE: str | None = "https://api.openai.com/v1"
    OPENAI_MODEL: str | None = "gpt-4o-mini"

    # pydantic-settings v2 권장 구성
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

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

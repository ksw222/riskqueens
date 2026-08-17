from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base

class Settings(BaseSettings):
    # Vercel Marketplace/Neon commonly injects this as DATABASE_URL.
    DATABASE_URL: str | None = None
    # Defaults keep import/startup available before Vercel DB variables are configured.
    PG_USER: str = ""
    PG_PASSWORD: str = ""
    PG_HOST: str = "localhost"
    PG_PORT: int = 5432
    PG_DB: str = ""

        # --- OpenAI (여기 추가) ---
    OPENAI_API_KEY: str | None = None
    OPENAI_API_BASE: str | None = "https://api.openai.com/v1"
    OPENAI_MODEL: str | None = "gpt-4o-mini"

    # pydantic-settings v2 권장 구성
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

settings = Settings()

# 👇 URL.create가 username/password 등 안전하게 인코딩해줍니다.
def build_database_url(config: Settings) -> str | URL:
    """Prefer the Vercel/Neon connection string, with local PG_* fallback."""
    if config.DATABASE_URL:
        return config.DATABASE_URL
    return URL.create(
        "postgresql+psycopg2",
        username=config.PG_USER,
        password=config.PG_PASSWORD,
        host=config.PG_HOST,
        port=config.PG_PORT,
        database=config.PG_DB,
    )


db_url = build_database_url(settings)

engine = create_engine(db_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

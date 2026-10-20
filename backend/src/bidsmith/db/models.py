from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, Float, Index, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from bidsmith.settings import get_settings


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_company_id: Mapped[str] = mapped_column(String, index=True)
    source: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(Text)
    client: Mapped[str | None] = mapped_column(String, nullable=True)
    award_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    naics: Mapped[str | None] = mapped_column(String, nullable=True)
    psc: Mapped[str | None] = mapped_column(String, nullable=True)
    building_type: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    embedding = mapped_column(Vector(get_settings().embedding_dim))

    __table_args__ = (
        Index(
            "ix_projects_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

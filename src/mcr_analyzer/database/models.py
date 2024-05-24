"""Object Relational Models defining the database."""

from datetime import (
    datetime,  # noqa: TCH003  # - sqlalchemy.exc.ArgumentError: Could not resolve all types within mapped annotation: "sqlalchemy.orm.base.Mapped[ForwardRef('datetime | None')]".
)

from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, declared_attr, mapped_column
from sqlalchemy.types import BINARY

from mcr_analyzer.config.hash import HASH__DIGEST_SIZE


class Base(MappedAsDataclass, DeclarativeBase):
    @declared_attr.directive
    def __tablename__(self) -> str:  # noqa: PLW3201
        return self.__name__.lower()

    id: Mapped[int] = mapped_column(primary_key=True, init=False)


class Measurement(Base):
    date_time: Mapped[datetime] = mapped_column(index=True)
    device_id: Mapped[str]
    probe_id: Mapped[str]
    chip_id: Mapped[str]

    image_data: Mapped[bytes]
    image_height: Mapped[int]
    image_width: Mapped[int]
    checksum: Mapped[bytes] = mapped_column(BINARY(HASH__DIGEST_SIZE))

    row_count: Mapped[int]
    column_count: Mapped[int]
    spot_size: Mapped[int]

    spot_corner_top_left_x: Mapped[float]
    spot_corner_top_left_y: Mapped[float]

    spot_corner_top_right_x: Mapped[float]
    spot_corner_top_right_y: Mapped[float]

    spot_corner_bottom_right_x: Mapped[float]
    spot_corner_bottom_right_y: Mapped[float]

    spot_corner_bottom_left_x: Mapped[float]
    spot_corner_bottom_left_y: Mapped[float]

    notes: Mapped[str]

from datetime import (
    datetime,  # noqa: TCH003  # - sqlalchemy.exc.ArgumentError: Could not resolve all types within mapped annotation: "sqlalchemy.orm.base.Mapped[ForwardRef('datetime | None')]".
)
from typing import Annotated

from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, declared_attr, mapped_column, relationship
from sqlalchemy.schema import ForeignKey
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
    image_hash: Mapped[bytes] = mapped_column(BINARY(HASH__DIGEST_SIZE))

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

    groups: Mapped[list["Group"]] = relationship(back_populates="measurement", default_factory=list)


column_type__foreign_key__measurement = Annotated[int, mapped_column(ForeignKey(f"{Measurement.__tablename__}.id"))]


class Group(Base):
    measurement_id: Mapped[column_type__foreign_key__measurement] = mapped_column(init=False)
    measurement: Mapped["Measurement"] = relationship(back_populates="groups")

    name: Mapped[str]
    notes: Mapped[str]
    color_code_hex_rgb: Mapped[str]

    spots: Mapped[list["Spot"]] = relationship(back_populates="group", default_factory=list)


column_type__foreign_key__group = Annotated[int, mapped_column(ForeignKey(f"{Group.__tablename__}.id"))]


class Spot(Base):
    group_id: Mapped[column_type__foreign_key__group] = mapped_column(init=False)
    group: Mapped["Group"] = relationship(back_populates="spots")

    row: Mapped[int]
    column: Mapped[int]

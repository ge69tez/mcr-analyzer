"""Object Relational Models defining the database."""

from datetime import (
    datetime,  # noqa: TCH003  # - sqlalchemy.exc.ArgumentError: Could not resolve all types within mapped annotation: "sqlalchemy.orm.base.Mapped[ForwardRef('datetime | None')]".
)
from typing import Annotated

from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, declared_attr, mapped_column, relationship
from sqlalchemy.schema import ForeignKey
from sqlalchemy.types import BINARY, Text

from mcr_analyzer.config.hash import HASH__DIGEST_SIZE


class Base(MappedAsDataclass, DeclarativeBase):
    @declared_attr.directive
    def __tablename__(self) -> str:  # noqa: PLW3201
        return self.__name__.lower()

    id: Mapped[int] = mapped_column(primary_key=True, init=False)


class Chip(Base):
    chip_id: Mapped[str]
    """Chip ID assigned by user during measurement."""

    row_count: Mapped[int]
    """Number of rows, typically five. Used for redundancy and error reduction."""

    column_count: Mapped[int]
    """Number of columns. Different anti-bodies or anti-gens."""

    spot_size: Mapped[int]
    """Size (in pixels) of a single spot. Side length of the square used for processing."""

    spot_corner_top_left_x: Mapped[float]
    spot_corner_top_left_y: Mapped[float]

    spot_corner_top_right_x: Mapped[float]
    spot_corner_top_right_y: Mapped[float]

    spot_corner_bottom_right_x: Mapped[float]
    spot_corner_bottom_right_y: Mapped[float]

    spot_corner_bottom_left_x: Mapped[float]
    spot_corner_bottom_left_y: Mapped[float]

    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="chip", order_by="Measurement.timestamp", default_factory=list
    )
    """Many-to-One relationship referencing all measurements the chip was used for."""


column_type__foreign_key__chip = Annotated[int, mapped_column(ForeignKey(f"{Chip.__tablename__}.id"))]


class Device(Base):
    """Information about the MCR device used."""

    serial: Mapped[str] = mapped_column(unique=True)
    """Serial number of the device."""

    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="device", order_by="Measurement.timestamp", default_factory=list
    )
    """Many-to-One relationship referencing all measurements done with this device."""


column_type__foreign_key__device = Annotated[int, mapped_column(ForeignKey(f"{Device.__tablename__}.id"))]


class SampleType(Base):
    """Information about the kind of sample."""

    name: Mapped[str]
    """Name of the kind. For example full blood, serum, water, etc."""

    samples: Mapped[list["Sample"]] = relationship(
        back_populates="sample_type", order_by="Sample.id", default_factory=list
    )
    """Many-to-One relationship referencing all samples of this sample type."""


column_type__foreign_key__sample_type = Annotated[int, mapped_column(ForeignKey(f"{SampleType.__tablename__}.id"))]


class Sample(Base):
    """Information about the measured sample."""

    probe_id: Mapped[str]
    """Short description of the sample, entered as Probe ID during measurement."""

    known_positive: Mapped[bool | None] = mapped_column(default=None)
    """Is this a know positive sample? Makes use of the tri-state SQL bool `None`, `True`, or `False`."""

    sample_type_id: Mapped[column_type__foreign_key__sample_type | None] = mapped_column(init=False)
    """Refers to :class:`SampleType`."""

    timestamp: Mapped[datetime | None] = mapped_column(default=None)
    """Date and time of the sample taking."""

    sample_type: Mapped["SampleType"] = relationship(back_populates="samples", default=None)
    """One-to-Many relationship referencing the type of this sample."""

    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="sample", order_by="Measurement.timestamp", default_factory=list
    )
    """Many-to-One relationship referencing the measurements done with this sample."""


column_type__foreign_key__sample = Annotated[int, mapped_column(ForeignKey(f"{Sample.__tablename__}.id"))]


class Measurement(Base):
    """A single measurement. This is the central table everything is about."""

    chip_id: Mapped[column_type__foreign_key__chip] = mapped_column(init=False)
    """Refers to the used :class:`Chip`."""

    device_id: Mapped[column_type__foreign_key__device] = mapped_column(init=False)
    """Refers to the used :class:`Device`."""

    sample_id: Mapped[column_type__foreign_key__sample] = mapped_column(init=False)
    """Refers to the measured :class:`Sample`."""

    image_data: Mapped[bytes]
    """Raw 16-bit image data, big endian. (Numpy's ``uint16`` datatype, for compatibility with `Netpbm
    <https://netpbm.sourceforge.net/doc/pgm.html>`_). """  # cSpell:ignore netpbm
    image_height: Mapped[int]
    image_width: Mapped[int]

    checksum: Mapped[bytes] = mapped_column(BINARY(HASH__DIGEST_SIZE))
    """SHA256 hash of the raw 16-bit image data. Used for duplicate detection."""

    timestamp: Mapped[datetime] = mapped_column(index=True)
    """Date and time of the measurement."""

    chip_failure: Mapped[bool] = mapped_column(default=False)
    """Was there a failure during measurement (leaky chip). Defaults to `False`."""

    notes: Mapped[str | None] = mapped_column(Text, default=None)
    """Additional notes."""

    chip: Mapped["Chip"] = relationship(back_populates="measurements", default=None)
    """One-to-Many relationship referencing the used chip."""

    device: Mapped["Device"] = relationship(back_populates="measurements", default=None)
    """One-to-Many relationship referencing the used device."""

    sample: Mapped["Sample"] = relationship(back_populates="measurements", default=None)
    """One-to-Many relationship referencing the analyzed sample."""

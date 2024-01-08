"""Object Relational Models defining the database."""

from datetime import datetime
from typing import Annotated

from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, declared_attr, mapped_column, relationship
from sqlalchemy.schema import ForeignKey, UniqueConstraint
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

    margin_left: Mapped[int]
    """Distance between left border of the image and first column of spots."""

    margin_top: Mapped[int]
    """Distance between top border of the image and first row of spots."""

    spot_size: Mapped[int]
    """Size (in pixels) of a single spot. Side length of the square used for processing."""

    spot_margin_horizontal: Mapped[int]
    """Horizontal margin between two adjacent spots: skip N pixels before processing the next spot."""

    spot_margin_vertical: Mapped[int]
    """Vertical margin between two adjacent spots: skip N pixels before processing the next spot."""

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


class Reagent(Base):
    """Substance used on a chip.

    This class handles column specific information (for end-users), so depending on what information is more useful,
    this is about the reagent which should be detected or the reagent which is initially put on the chip.
    """

    name: Mapped[str]
    """Name of the substance."""

    results: Mapped[list["Result"]] = relationship(back_populates="reagent", order_by="Result.id", default_factory=list)
    """Many-to-One relationship referencing the Spots of this substance."""


column_type__foreign_key__reagent = Annotated[int, mapped_column(ForeignKey(f"{Reagent.__tablename__}.id"))]


class User(Base):
    """Researcher who did the measurement or took the sample."""

    name: Mapped[str]
    """Name of the researcher."""

    login_id: Mapped[str]
    """User ID of the researcher, to be used for automatic association."""

    samples: Mapped[list["Sample"]] = relationship(back_populates="user", order_by="Sample.id", default_factory=list)
    """Many-to-One relationship referencing all samples taken by a user."""

    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="user", order_by="Measurement.timestamp", default_factory=list
    )
    """Many-to-One relationship referencing all measurements done by a user."""


column_type__foreign_key__user = Annotated[int, mapped_column(ForeignKey(f"{User.__tablename__}.id"))]


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

    user_id: Mapped[column_type__foreign_key__user | None] = mapped_column(init=False)
    """Refers to the :class:`User` who took the sample."""

    timestamp: Mapped[datetime | None] = mapped_column(default=None)
    """Date and time of the sample taking."""

    sample_type: Mapped["SampleType"] = relationship(back_populates="samples", default=None)
    """One-to-Many relationship referencing the type of this sample."""

    user: Mapped["User"] = relationship(back_populates="samples", default=None)
    """One-to-Many relationship referencing the user who took this sample."""

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

    user_id: Mapped[column_type__foreign_key__user | None] = mapped_column(init=False)
    """Refers to the :class:`User` who did the measurement."""

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

    user: Mapped["User"] = relationship(back_populates="measurements", default=None)
    """One-to-Many relationship referencing the user who did the measurement."""

    results: Mapped[list["Result"]] = relationship(
        back_populates="measurement", order_by="Result.id", default_factory=list
    )
    """Many-to-One relationship referencing all results of this measurement."""


column_type__foreign_key__measurement = Annotated[int, mapped_column(ForeignKey(f"{Measurement.__tablename__}.id"))]


class Result(Base):
    """Analysis information about a single spot."""

    __table_args__ = (UniqueConstraint("measurement_id", "row", "column"),)

    measurement_id: Mapped[column_type__foreign_key__measurement] = mapped_column(init=False)
    """Reference to the :class:`Measurement` to which the result belongs."""

    row: Mapped[int]
    """Row index, counted from 0."""

    column: Mapped[int]
    """Column index, counted from 0."""

    value: Mapped[float | None] = mapped_column(default=None)
    """Calculated brightness of the spot."""

    reagent_id: Mapped[column_type__foreign_key__reagent | None] = mapped_column(init=False)
    """Reference to :class:`Reagent`."""

    concentration: Mapped[float | None] = mapped_column(default=None)
    """Additional concentration information to specify the :attr:`reagent` more precisely."""

    valid: Mapped[bool | None] = mapped_column(default=None)
    """Is this a valid result which can be used in calculations? Invalid results can be caused by the process (bleeding
    of nearby results, air bubbles, or dirt) or determination as an outlier (mathematical postprocessing)."""

    measurement: Mapped["Measurement"] = relationship(back_populates="results", default=None)
    """One-to-Many relationship referencing the measurement which yielded this result."""

    reagent: Mapped["Reagent"] = relationship(back_populates="results", default=None)
    """One-to-Many relationship referencing the substance of this spot."""

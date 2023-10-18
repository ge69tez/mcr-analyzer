"""Object Relational Models defining the database."""

import datetime

from typing import Optional

from sqlalchemy import (
    BINARY,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import (
    relationship,
    mapped_column,
    Mapped,
    DeclarativeBase
)

from mcr_analyzer.database.database import Base

class Base(DeclarativeBase):
    pass

class Chip(Base):
    """Information about the chip used."""
    
    __tablename__ = "chip"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    """Internal ID, used for cross-references."""
    name: Mapped[str] = mapped_column(String)
    """Chip ID assigned by user during measurement."""
    rowCount: Mapped[int] = mapped_column(Integer, nullable=False)  # noqa: N815
    """Number of rows, typically five. Used for redundancy and error
    reduction."""
    columnCount: Mapped[int] = mapped_column(Integer, nullable=False)  # noqa: N815
    """Number of columns. Different anti-bodies or anti-gens."""
    marginLeft: Mapped[int] = mapped_column(Integer, nullable=False)  # noqa: N815
    """Distance between left border of the image and first column of spots."""
    marginTop: Mapped[int] = mapped_column(Integer, nullable=False)  # noqa: N815
    """Distance between top border of the image and first row of spots."""
    spotSize: Mapped[int] = mapped_column(Integer, nullable=False)  # noqa: N815
    """Size (in pixels) of a single spot. Side length of the square used for
    processing."""
    spotMarginHorizontal: Mapped[int] = mapped_column(Integer, nullable=False)  # noqa: N815
    """Horizontal margin between two adjacent spots: skip N pixels before
    processing the next spot."""
    spotMarginVertical: Mapped[int] = mapped_column(Integer, nullable=False)  # noqa: N815
    """Vertical margin between two adjacent spots: skip N pixels before
    processing the next spot."""
    measurements: Mapped[relationship] = relationship(
        "Measurement",
        back_populates="chip",
        order_by="Measurement.timestamp",
    )
    """Many-to-One relationship referencing all measurements the chip was
    used for."""


class Device(Base):
    """Information about the MCR device used."""
    
    __tablename__ = "device"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    """Internal ID, used for cross-references."""
    serial: Mapped[str] = mapped_column(String(255), nullable=False)
    """Serial number of the device."""
    measurements: Mapped[relationship] = relationship(
        "Measurement",
        back_populates="device",
        order_by="Measurement.timestamp",
    )
    """Many-to-One relationship referencing all measurements done with this
    device."""


class Measurement(Base):
    """A single measurement. This is the central table everything is about."""
    
    __tablename__ = "measurement"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    """Internal ID, used for cross-references."""
    chipID: Mapped[int] = mapped_column(Integer, ForeignKey("chip.id"), index=True)  # noqa: N815
    """Refers to the used :class:`Chip`."""
    chip: Mapped[relationship] = relationship("Chip", back_populates="measurements")
    """One-to-Many relationship referencing the used chip."""
    deviceID: Mapped[int] = mapped_column(Integer, ForeignKey("device.id"), index=True)  # noqa: N815
    """Refers to the used :class:`Device`."""
    device: Mapped[relationship] = relationship("Device", back_populates="measurements")
    """One-to-Many relationship referencing the used device."""
    sampleID: Mapped[int] = mapped_column(Integer, ForeignKey("sample.id"), index=True)  # noqa: N815
    """Refers to the measured :class:`Sample`."""
    sample: Mapped[relationship] = relationship("Sample", back_populates="measurements")
    """One-to-Many relationship referencing the analyzed sample."""
    image: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    """Raw 16-bit image data, big endian. (Numpy's ``>u2`` datatype, for
    compatibility with `netpbm <http://netpbm.sourceforge.net/doc/pgm.html>`_).
    """  # cSpell:ignore netpbm
    checksum: Mapped[bytes] = mapped_column(BINARY(32), nullable=False)
    """SHA256 hash of the raw 16-bit image data. Used for duplicate detection."""
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, index=True)
    """Date and time of the measurement."""
    userID: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("user.id"), index=True)  # noqa: N815
    """Refers to the :class:`User` who did the measurement."""
    user: Mapped[relationship] = relationship("User", back_populates="measurements")
    """One-to-Many relationship referencing the user who did the
    measurement."""
    chipFailure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # noqa: N815
    """Was there a failure during measurement (leaky chip). Defaults to
    `False`."""
    notes: Mapped[Optional[str]] = mapped_column(Text)
    """Additional notes."""
    results: Mapped[relationship] = relationship(
        "Result",
        back_populates="measurement",
        order_by="Result.id",
    )
    """Many-to-One relationship referencing all results of this measurement."""


class Reagent(Base):
    """Substance used on a chip.

    This class handles column specific information (for end-users), so depending
    on what information is more useful, this is about the reagent which should
    be detected or the reagent which is initially put on the chip.
    """
    
    __tablename__ = "reagent"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    """Internal ID, used for cross-references."""
    name: Mapped[str] = mapped_column(String)
    """Name of the substance."""
    results: Mapped[relationship] = relationship("Result", back_populates="reagent", order_by="Result.id")
    """Many-to-One relationship referencing the Spots of this substance."""


class Result(Base):
    """Analysis information about a single spot."""
    
    __tablename__ = "result"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    """Internal ID, used for cross-references."""
    measurementID: Mapped[int] = mapped_column(Integer, ForeignKey("measurement.id"), index=True)  # noqa: N815
    """Reference to the :class:`Measurement` to which the result belongs."""
    measurement: Mapped[relationship] = relationship("Measurement", back_populates="results")
    """One-to-Many relationship referencing the measurement which yielded this
    result."""
    row: Mapped[int] = mapped_column(Integer)
    """Row index, counted from 0."""
    column: Mapped[int] = mapped_column(Integer)
    """Column index, counted from 0."""
    value: Mapped[Optional[float]] = mapped_column(Float)
    """Calculated brightness of the spot."""
    reagentID: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("reagent.id"), index=True)  # noqa: N815
    """Reference to :class:`Reagent`."""
    reagent: Mapped[relationship] = relationship("Reagent", back_populates="results")
    """One-to-Many relationship referencing the substance of this spot."""
    concentration: Mapped[Optional[float]] = mapped_column(Float)
    """Additional concentration information to specify the :attr:`reagent` more
    precisely."""
    valid: Mapped[Optional[bool]] = mapped_column(Boolean)
    """Is this a valid result which can be used in calculations? Invalid results
    can be caused by the process (bleeding of nearby results, air bubbles, or
    dirt) or determination as an outlier (mathematical postprocessing)."""


class Sample(Base):
    """Information about the measured sample."""
    
    __tablename__ = "sample"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    """Internal ID, used for cross-references."""
    name: Mapped[str] = mapped_column(String)
    """Short description of the sample, entered as Probe ID during
    measurement."""
    knownPositive: Mapped[Optional[bool]] = mapped_column(Boolean)  # noqa: N815
    """Is this a know positive sample? Makes use of the tri-state SQL bool
    `None`, `True`, or `False`."""
    typeID: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("sampleType.id"), index=True)  # noqa: N815
    """Refers to :class:`SampleType`."""
    type: Mapped[relationship] = relationship("SampleType", back_populates="samples")
    """One-to-Many relationship referencing the type of this sample."""
    takenByID: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("user.id"), index=True)  # noqa: N815
    """Refers to the :class:`User` who took the sample."""
    takenBy: Mapped[relationship] = relationship("User", back_populates="samples")  # noqa: N815
    """One-to-Many relationship referencing the user who took this sample."""
    timestamp: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    """Date and time of the sample taking."""
    measurements: Mapped[relationship] = relationship(
        "Measurement",
        back_populates="sample",
        order_by="Measurement.timestamp",
    )
    """Many-to-One relationship referencing the measurements done with this
    sample."""


class SampleType(Base):
    """Information about the kind of sample."""
    
    __tablename__ = "sampleType"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    """Internal ID, used for cross-references."""
    name: Mapped[Optional[str]] = mapped_column(String)
    """Name of the kind. For example full blood, serum, water, etc."""
    samples: Mapped[relationship] = relationship("Sample", back_populates="type", order_by="Sample.id")
    """Many-to-One relationship referencing all samples of this type."""


class User(Base):
    """Researcher who did the measurement or took the sample."""
    
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    """Internal ID, used for cross-references."""
    name: Mapped[str] = mapped_column(String, nullable=False)
    """Name of the researcher."""
    loginID: Mapped[str] = mapped_column(String)  # noqa: N815
    """User ID of the researcher, to be used for automatic association."""
    samples: Mapped[relationship] = relationship("Sample", back_populates="takenBy", order_by="Sample.id")
    """Many-to-One relationship referencing all samples taken by a user."""
    measurements: Mapped[relationship] = relationship(
        "Measurement",
        back_populates="user",
        order_by="Measurement.timestamp",
    )
    """Many-to-One relationship referencing all measurements done by a user."""

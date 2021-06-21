# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

""" Object Relational Models defining the database. """

import datetime

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
from sqlalchemy.orm import relationship

from mcr_analyser.database.database import Base


class Chip(Base):
    """Information about the chip used."""

    __tablename__ = "chip"
    id: int = Column(Integer, primary_key=True)
    """Internal ID, used for cross-references."""
    relationship("Measurement", back_populates="chip")
    name: str = Column(String)
    """Chip ID assigned by user during measurement."""
    rowCount: int = Column(Integer, nullable=False)
    """Number of rows, typically five. Used for redundancy and error
    reduction."""
    columnCount: int = Column(Integer, nullable=False)
    """Number of columns. Different anti-bodies or anti-gens."""
    spotSize: int = Column(Integer, nullable=False)
    """Size (in pixels) of a single spot. Side length of the square used for
    processing."""


class Device(Base):
    """Information about the MCR device used."""

    __tablename__ = "device"
    id: int = Column(Integer, primary_key=True)
    """Internal ID, used for cross-references."""
    relationship("Measurement", back_populates="device")
    serial: str = Column(String(255), nullable=False)
    """Serial number of the device."""


class Measurement(Base):
    """A single measurement. This is the central table everything is about."""

    __tablename__ = "measurement"
    id: str = Column(BINARY(32), primary_key=True)
    """SHA256 hash of the raw 16-bit image data. Used for duplicate detection
    and potential future database merges."""
    chipID: int = Column(Integer, ForeignKey("chip.id"))
    """Refers to the used :class:`Chip`."""
    relationship("Chip", back_populates="measurement")
    deviceID: int = Column(Integer, ForeignKey("device.id"))
    """Refers to the used :class:`Device`."""
    relationship("Device", back_populates="measurement")
    sampleID: int = Column(Integer, ForeignKey("sample.id"))
    """Refers to the measured :class:`Sample`."""
    relationship("Sample", back_populates="measurement")
    image: bytes = Column(LargeBinary, nullable=False)
    """Raw 16-bit image data, big endian. (Numpy's ``>u2`` datatype, for
    compatibility with `netpbm <http://netpbm.sourceforge.net/doc/pgm.html>`_).
    """
    timestamp: datetime.datetime = Column(DateTime)
    """Date and time of the measurement."""
    userID: int = Column(Integer, ForeignKey("user.id"))
    """Refers to the :class:`User` who did the measurement."""
    relationship("User", back_populates="measurement")
    chipFailure: bool = Column(Boolean, nullable=False, default=False)
    """Was there a failure during measurement (leaky chip). Defaults to
    `False`."""
    notes: str = Column(Text)
    """Additional notes."""


class Reagent(Base):
    """Substance used on a chip.

    Depending on the use case this could be a
    reagent which should be detected or a reagent put on the chip.
    """

    __tablename__ = "reagent"
    id: int = Column(Integer, primary_key=True)
    """Internal ID, used for cross-references."""
    relationship("Result", back_populates="reagent")
    name: str = Column(String)
    """ Name of the substance."""


class Result(Base):
    """Analysis information about a single spot."""

    __tablename__ = "result"
    id: int = Column(Integer, primary_key=True)
    """Internal ID, used for cross-references."""
    measurementID: int = Column(Integer, ForeignKey("measurement.id"))
    """Reference to the :class:`Measurement` to which the result belongs."""
    relationship("Measurement", back_populates="result")
    row: int = Column(Integer)
    """Row index, counted from 0."""
    column: int = Column(Integer)
    """Column index, counted from 0."""
    value: float = Column(Float)
    """Calculated brightness of the spot."""
    reagent: int = Column(Integer, ForeignKey("reagent.id"))
    """Reference to :class:`Reagent`."""
    relationship("Reagent", back_populates="result")
    concentration: float = Column(Float)
    """Additional concentration information to specify the :attr:`reagent` more
    precisely."""


class Sample(Base):
    """Information about the measured sample."""

    __tablename__ = "sample"
    id: int = Column(Integer, primary_key=True)
    """Internal ID, used for cross-references."""
    name: str = Column(String)
    """Short description of the sample, entered as Probe ID during
    measurement."""
    knownPositive: bool = Column(Boolean)
    """Is this a know positive sample? Makes use of the tri-state SQL bool
    `None`, `True`, or `False`."""
    type: int = Column(Integer, ForeignKey("sampleType.id"))
    """Refers to :class:`SampleType`."""
    relationship("SampleType", back_populates="sample")
    takenBy: int = Column(Integer, ForeignKey("user.id"))
    """Refers to the :class:`User` who took the sample."""
    relationship("User", back_populates="user")
    timestamp: datetime.datetime = Column(DateTime)
    """Date and time of the sample taking."""


class SampleType(Base):
    """Information about the kind of sample."""

    __tablename__ = "sampleType"
    id: int = Column(Integer, primary_key=True)
    """Internal ID, used for cross-references."""
    relationship("Sample", back_populates="sampleType")
    name: str = Column(String, nullable=False)
    """Name of the kind. For example full blood, serum, water, etc."""


class User(Base):
    """Researcher who did the measurement or took the sample."""

    __tablename__ = "user"
    id: str = Column(Integer, primary_key=True)
    """Internal ID, used for cross-references."""
    relationship("Sample", back_populates="user")
    name: str = Column(String, nullable=False)
    """Name of the researcher."""
    loginID: str = Column(String)
    """User ID of the researcher, to be used for automatic association."""

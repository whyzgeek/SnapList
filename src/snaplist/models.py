from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from .db import Base

# item.status values
DRAFT = "draft"
READY = "ready"
APPROVED = "approved"
LISTED = "listed"
SOLD = "sold"
PROCESSING = "processing"
FAILED = "failed"
ITEM_STATUSES = (PROCESSING, FAILED, DRAFT, READY, APPROVED, LISTED, SOLD)

# listing.status values (per channel; must not contradict item.status)
L_DRAFT = "draft"
L_PENDING = "pending"
L_POSTED = "posted"
L_FAILED = "failed"


class Batch(Base):
    __tablename__ = "batch"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="processing")

    items = relationship("Item", back_populates="batch", cascade="all, delete-orphan")


class Item(Base):
    __tablename__ = "item"

    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("batch.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    status = Column(String, default=DRAFT)
    facts = Column("facts_json", Text, default="{}")          # model output
    price = Column(Integer, nullable=True)                    # cents
    suggested_sites = Column("suggested_sites_json", Text, default="[]")
    chosen_sites = Column("chosen_sites_json", Text, default="[]")
    notes = Column(Text, default="")                          # seller-supplied context for the AI
    error = Column(Text, nullable=True)

    batch = relationship("Batch", back_populates="items")
    photos = relationship("Photo", back_populates="item", cascade="all, delete-orphan")
    questions = relationship(
        "ItemQuestion", back_populates="item", cascade="all, delete-orphan"
    )
    listings = relationship("Listing", back_populates="item", cascade="all, delete-orphan")
    price_comps = relationship(
        "PriceComp", back_populates="item", cascade="all, delete-orphan"
    )


class Photo(Base):
    __tablename__ = "photo"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("item.id"))
    path = Column(Text)                 # original on disk
    position = Column(Integer, default=0)
    is_cover = Column(Integer, default=0)
    cleaned_path = Column(Text, nullable=True)

    item = relationship("Item", back_populates="photos")


class ItemQuestion(Base):
    __tablename__ = "item_question"
    __table_args__ = (UniqueConstraint("item_id", "question"),)

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("item.id"))
    question = Column(Text)
    answer = Column(Text, nullable=True)
    answered_at = Column(DateTime, nullable=True)

    item = relationship("Item", back_populates="questions")


class Listing(Base):
    __tablename__ = "listing"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("item.id"))
    channel = Column(String)            # ebay, facebook, craigslist
    title = Column(Text)
    body = Column(Text)
    fields = Column("fields_json", Text, default="{}")
    external_id = Column(Text, nullable=True)   # SKU / offer id / listing id
    url = Column(Text, nullable=True)
    status = Column(String, default=L_DRAFT)
    posted_at = Column(DateTime, nullable=True)

    item = relationship("Item", back_populates="listings")


class PriceComp(Base):
    __tablename__ = "price_comp"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("item.id"))
    source = Column(String)
    title = Column(Text)
    price = Column(Integer)             # cents
    url = Column(Text, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    item = relationship("Item", back_populates="price_comps")


class Setting(Base):
    __tablename__ = "setting"
    __table_args__ = (UniqueConstraint("key"),)

    key = Column(String, primary_key=True)
    value = Column(Text)


class Job(Base):
    """Persisted job so a whole batch can be processed and resumed after a crash."""

    __tablename__ = "job"

    id = Column(String(36), primary_key=True)
    kind = Column(String)               # group, extract, price, write, etc.
    batch_id = Column(Integer, nullable=True)
    item_id = Column(Integer, nullable=True)
    status = Column(String, default="pending")   # pending, running, completed, failed, cancelled
    attempts = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    progress = Column(Integer, default=0)         # 0-100
    result = Column("result_json", Text, default="{}")
    params = Column(Text, default="{}")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

"""Pydantic models for Edinburgh Fringe data."""

import datetime

from pydantic import BaseModel, Field, HttpUrl


class Show(BaseModel):
    """A show listed on the Edinburgh Fringe."""

    name: str = Field(..., min_length=1, description="Show name")
    performer: str | None = Field(None, description="Performer or company name")
    url: HttpUrl = Field(..., description="Show page URL")
    venue: str | None = Field(None, description="Venue name")
    location: str | None = Field(None, description="Venue location/address")


class Performance(BaseModel):
    """A single performance of a show."""

    show_name: str = Field(..., min_length=1, description="Show name")
    show_url: HttpUrl = Field(..., description="Show page URL")
    date: datetime.date = Field(..., description="Performance date")
    time: datetime.time | None = Field(None, description="Performance time")
    availability: str | None = Field(None, description="Ticket availability status")
    venue: str | None = Field(None, description="Venue name")

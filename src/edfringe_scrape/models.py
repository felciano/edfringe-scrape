"""Pydantic models for Edinburgh Fringe data."""

import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Genre(StrEnum):
    """Edinburgh Fringe show genres matching website categories."""

    CABARET = "CABARET"
    CHILDRENS_SHOWS = "CHILDRENS_SHOWS"
    CIRCUS = "CIRCUS"
    COMEDY = "COMEDY"
    DANCE = "DANCE"
    EVENTS = "EVENTS"
    EXHIBITIONS = "EXHIBITIONS"
    MUSICALS = "MUSICALS"
    MUSIC = "MUSIC"
    OPERA = "OPERA"
    POETRY = "POETRY"
    THEATRE = "THEATRE"

    @property
    def url_param(self) -> str:
        """Get URL parameter value for this genre."""
        return self.value


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


class RawPerformanceRow(BaseModel):
    """Raw performance data matching the existing CSV format from Web Scraper.io.

    Field names use aliases to match the CSV column headers.
    """

    show_link_href: str = Field(..., alias="show-link-href")
    show_link: str = Field(..., alias="show-link")
    show_name: str = Field(..., alias="show-name")
    show_performer: str | None = Field(None, alias="show-performer")
    date: str = Field(..., description="Raw date string like 'Wednesday 30 July'")
    performance_time: str | None = Field(None, alias="performance-time")
    show_availability: str | None = Field(None, alias="show-availability")
    show_location: str | None = Field(None, alias="show-location")
    web_scraper_start_url: str | None = Field(None, alias="web-scraper-start-url")

    model_config = ConfigDict(populate_by_name=True)


class ShowCard(BaseModel):
    """A show card from search results listing page."""

    title: str = Field(..., description="Show title")
    url: str = Field(..., description="Show detail page URL")
    performer: str | None = Field(None, description="Performer or company name")
    duration: str | None = Field(None, description="Show duration like '1hr 15mins'")
    date_block_html: str | None = Field(None, description="Raw HTML of date/time block")


class PerformanceDetail(BaseModel):
    """Performance details from show detail page."""

    date: datetime.date = Field(..., description="Performance date")
    start_time: datetime.time | None = Field(None, description="Performance start")
    end_time: datetime.time | None = Field(None, description="Performance end")
    availability: str | None = Field(None, description="Ticket status")
    venue: str | None = Field(None, description="Venue name")
    location: str | None = Field(None, description="Venue location")


class ShowInfo(BaseModel):
    """Show metadata extracted from detail page."""

    show_url: str = Field(default="", description="Show page URL")
    show_name: str = Field(default="", description="Show name")
    genre: str = Field(default="", description="Primary genre (e.g. COMEDY)")
    subgenres: str = Field(default="", description="Comma-separated sub-genres")
    description: str = Field(default="", description="Show description")
    warnings: str = Field(default="", description="Content warnings")
    age_suitability: str = Field(default="", description="Age suitability guidance")
    image_url: str = Field(default="", description="Show image URL")
    website: str = Field(default="", description="Website link")
    facebook: str = Field(default="", description="Facebook link")
    instagram: str = Field(default="", description="Instagram link")
    tiktok: str = Field(default="", description="TikTok link")
    youtube: str = Field(default="", description="YouTube link")
    twitter: str = Field(default="", description="Twitter link")
    bluesky: str = Field(default="", description="Bluesky link")
    mastodon: str = Field(default="", description="Mastodon link")


class VenueInfo(BaseModel):
    """Venue information extracted from show and venue pages."""

    venue_code: str = Field(default="", description="Venue code (e.g. 'V123')")
    venue_name: str = Field(default="", description="Venue name")
    address: str = Field(default="", description="Full address")
    postcode: str = Field(default="", description="Postcode")
    geolocation: str = Field(default="", description="Lat,lng coordinates")
    google_maps_url: str = Field(default="", description="Google Maps directions URL")
    venue_page_url: str = Field(default="", description="Venue detail page URL")
    description: str = Field(default="", description="Venue description")
    contact_phone: str = Field(default="", description="Contact phone from venue page")
    contact_email: str = Field(default="", description="Contact email from venue page")


class ScrapedShow(BaseModel):
    """Complete scraped show with all performances."""

    title: str = Field(..., description="Show title")
    url: str = Field(..., description="Show page URL")
    performer: str | None = Field(None, description="Performer name")
    duration: str | None = Field(None, description="Show duration")
    performances: list[PerformanceDetail] = Field(
        default_factory=list, description="List of performances"
    )
    genre: Genre | None = Field(None, description="Show genre")
    show_info: ShowInfo | None = Field(None, description="Show metadata")
    venue_info: VenueInfo | None = Field(None, description="Venue information")


class ScrapingDogResponse(BaseModel):
    """Response from Scraping Dog API."""

    html: str = Field(..., description="Rendered HTML content")
    status_code: int = Field(default=200, description="HTTP status code")
    credits_used: int = Field(default=1, description="API credits consumed")

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import threading
import time
import logging
from logging.config import dictConfig
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
import signal
from agent import score_headline, deduplicate_headlines, classify_category
from scraper import (
    fetch_google_news,
    fetch_reddit_news,
    fetch_hackernews,
    fetch_ycombinator,
    fetch_twitter_trending
)
import requests
from fastapi import Request, Query
from agent import score_headline, deduplicate_headlines
from fastapi import APIRouter
from weather import get_location, get_weather_data
# --- Configuration ---
API_KEY = os.getenv("API_KEY", "mysecretkey")  # Override with .env in production
PROMETHEUS_PORT = 8001
ALLOWED_ORIGINS = ["http://localhost:3000", "https://yourproductiondomain.com"]

# --- Logging ---
dictConfig({
    "version": 1,
    "formatters": {
        "json": {
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
})
logger = logging.getLogger(__name__)

# --- Globals ---
cached_headlines = []
scraper_thread: Optional[threading.Thread] = None
shutdown_event = threading.Event()

# --- Models ---
class Headline(BaseModel):
    title: str
    link: str
    source: str
    score: float
    category: Optional[str] = "General"
    #summary: Optional[str] = None
    timestamp: datetime

# --- Scraper Function ---
def scheduled_scrape():
    global cached_headlines
    while not shutdown_event.is_set():
        try:
            logger.info("Running scheduled scrape...")

            all_headlines = []
            all_headlines += fetch_google_news()
            all_headlines += fetch_reddit_news()
            all_headlines += fetch_hackernews()
            all_headlines += fetch_ycombinator()
            all_headlines += fetch_twitter_trending()

            logger.info(f"Total raw headlines fetched: {len(all_headlines)}")

            for h in all_headlines:
                h["score"] = score_headline(h["title"], upvotes=h.get("upvotes"),
                    comments=h.get("comments"),
                    views=h.get("views"))
                h["category"] = classify_category(h["title"])
                h["timestamp"] = datetime.utcnow()

            deduped = deduplicate_headlines(all_headlines)
            deduped_sorted = sorted(deduped, key=lambda x: x["score"], reverse=True)

            cached_headlines = deduped_sorted
            logger.info(f"{len(cached_headlines)} headlines cached after deduplication.")

            time.sleep(600)  # Every 10 minutes

        except Exception as e:
            logger.error(f"Scraper error: {str(e)}")
            time.sleep(10)

# --- Lifespan Handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global scraper_thread

    logger.info("Starting application...")

    scraper_thread = threading.Thread(
        target=scheduled_scrape,
        name="background_scraper",
        daemon=True
    )
    scraper_thread.start()

    def handle_shutdown(signum, frame):
        logger.warning(f"Received signal {signum}, shutting down...")
        shutdown_event.set()
        return

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    yield

    logger.info("Shutting down background scraper...")
    shutdown_event.set()
    if scraper_thread:
        scraper_thread.join(timeout=5)

# --- App Setup ---
app = FastAPI(
    title="Pulse News Aggregator",
    lifespan=lifespan
)

# --- Middleware ---
Instrumentator().instrument(app).expose(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# --- Rate Limiting ---
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# --- Security ---
auth_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(key: str = Depends(auth_header)):
    if key != API_KEY:
        logger.warning(f"Invalid API key attempt: {key}")
        raise HTTPException(status_code=403, detail="Invalid API Key")

# --- Endpoints ---
@app.get("/health")
def health_check():
    return {
        "status": "running",
        "scraper_alive": scraper_thread.is_alive() if scraper_thread else False,
        "headlines_cached": len(cached_headlines)
    }

@app.get("/trending", response_model=List[Headline])
@limiter.limit("100/minute")
def get_trending(request: Request):
    return cached_headlines

@app.get("/admin/clear_cache", dependencies=[Depends(verify_api_key)])
def clear_cache():
    global cached_headlines
    cached_headlines = []
    return {"status": "cache cleared"}

@app.get("/weather")
def weather_summary(lat: float = Query(...), lon: float = Query(...)):
    try:
        # use wttr.in with lat,lon
        url = f"https://wttr.in/{lat},{lon}?format=j1"
        response = requests.get(url, timeout=5)
        data = response.json()

        current = data["current_condition"][0]
        area = data["nearest_area"][0]["areaName"][0]["value"]

        return {
            "location": area,
            "temperature": current["temp_C"],
            "condition": current["weatherDesc"][0]["value"],
        }
    except Exception as e:
        return {"error": "Unable to fetch weather"}



'''On startup, a daemon thread runs scheduled_scrape().

This thread fetches, scores, deduplicates, and updates cached_headlines every 600 seconds (10 minutes).

/trending simply returns this cached list.'''
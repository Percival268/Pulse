import requests
from bs4 import BeautifulSoup
import logging
import random
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from cachetools import cached, TTLCache
from requests.exceptions import RequestException, Timeout, TooManyRedirects

# --- Configuration ---
RATE_LIMIT = 100  # Not currently enforced, just a placeholder
REQUEST_DELAY = (1, 3)  # Delay range in seconds between requests
REQUEST_TIMEOUT = (3.05, 10)  # Connect timeout, read timeout
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB max
CACHE_TTL = 300  # 5 minutes

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko Firefox/114.0"
]

# --- Logging Setup ---
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# --- HTTP Session ---
session = requests.Session()
# User-Agent will be set per request, not once here (to randomize better)

# --- Cache ---
cache = TTLCache(maxsize=100, ttl=CACHE_TTL)
google_cache = TTLCache(maxsize=100, ttl=CACHE_TTL)
reddit_cache = TTLCache(maxsize=100, ttl=600)
hn_cache=TTLCache(maxsize=100, ttl=CACHE_TTL)
ycomb_cache=TTLCache(maxsize=100, ttl=1200)

# --- Utility Functions ---
def get_random_user_agent():
    return random.choice(USER_AGENTS)

def rate_limited_request(url, headers=None):
    """Make a GET request with delay, random User-Agent, and timeout."""
    time.sleep(random.uniform(*REQUEST_DELAY))  # Respectful scraping
    headers = headers or {}
    headers['User-Agent'] = get_random_user_agent()
    response = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    return response

def check_robots_allowed(url):
    """Checks robots.txt and ensures scraping is allowed for the target URL."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    agent = get_random_user_agent()

    try:
        # Manually fetch robots.txt to follow redirects
        r = requests.get(robots_url, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            logger.warning(f"robots.txt fetch failed ({r.status_code}): {robots_url}")
            return True  # Fail open

        content = r.text
        if not content.strip():
            logger.warning(f"robots.txt is empty for {robots_url}")
            return True

        rp = RobotFileParser()
        rp.parse(content.splitlines())
        allowed = rp.can_fetch(agent, url)
        logger.debug(f"robots.txt allowed for agent '{agent}' on {url}: {allowed}")
        return allowed

    except Exception as e:
        logger.warning(f"Could not process robots.txt for {url}: {e}")
        return True  # Fail open

def check_robots_allowed_override(url):
    # Reddit blocks all bots; override for browser-like headers
    parsed = urlparse(url)
    if "reddit.com" in parsed.netloc:
        return True
    return check_robots_allowed(url)


def validate_url(url: str, allowed_domains: list) -> str:
    """Ensure the URL is valid and from an allowed domain."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")
    if allowed_domains and parsed.netloc not in allowed_domains:
        raise ValueError(f"Domain not allowed: {parsed.netloc}")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

def safe_fetch(func):
    """Wrap a fetcher with try/catch and logging."""
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            logger.info(f"{func.__name__} succeeded with {len(result)} items")
            return result
        except (Timeout, TooManyRedirects, RequestException) as e:
            logger.warning(f"{func.__name__} network error: {e}")
            return []
        except Exception as e:
            logger.error(f"{func.__name__} failed: {e}")
            return []
    return wrapper



import feedparser

@safe_fetch
@cached(google_cache)
def fetch_google_news(source="google"):
    rss_url = "https://news.google.com/rss"
    headlines = []

    try:
        feed = feedparser.parse(rss_url)

        for entry in feed.entries:
            headlines.append({
                "title": entry.title,
                "link": entry.link,
                "source": "Google News"
            })

    except Exception as e:
        logger.warning(f"Google News RSS fetch failed: {e}")

    return headlines[:15]


@safe_fetch
@cached(reddit_cache)
def fetch_reddit_news(source="reddit"):
    rss_url = "https://www.reddit.com/r/news/.rss"
    allowed_domains = ["www.reddit.com"]

    if not check_robots_allowed_override(rss_url):
      logger.warning("Scraping not allowed by robots.txt")
      return []


    # Custom headers since Reddit blocks generic user-agents
    headers = {
        "User-Agent": get_random_user_agent()
    }

    r = rate_limited_request(rss_url, headers=headers)

    if int(r.headers.get("Content-Length") or 0) > MAX_CONTENT_LENGTH:
        raise ValueError("Response too large")

    r.raise_for_status()

    # Parse RSS feed using feedparser
    import feedparser
    feed = feedparser.parse(r.text)

    headlines = []
    for entry in feed.entries:
        try:
            title = entry.title
            link = validate_url(entry.link, allowed_domains)
            headlines.append({
                "title": title,
                "link": link,
                "source": "Reddit News"
            })
        except Exception as e:
            logger.warning(f"Error parsing Reddit RSS item: {e}")

    return headlines[:15]
'''
@safe_fetch
@cached(cache)
def fetch_reddit_news():
    url = "https://www.reddit.com/r/popular.json"
    headers = {'User-Agent': get_random_user_agent()}
    r = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()

    headlines = []
    for post in data.get("data", {}).get("children", []):
        item = post["data"]
        title = item.get("title")
        link = f"https://www.reddit.com{item.get('permalink')}"
        upvotes = item.get("ups", 0)
        comments = item.get("num_comments", 0)

        headlines.append({
            "title": title,
            "link": link,
            "source": "Reddit",
            "upvotes": upvotes,
            "comments": comments
        })
    return headlines
'''

@safe_fetch
@cached(hn_cache)
def fetch_hackernews(source="hn"):
    url = "https://news.ycombinator.com/"

    if not check_robots_allowed(url):
        logger.warning("Scraping not allowed by robots.txt")
        return []

    r = rate_limited_request(url)

    if int(r.headers.get("Content-Length") or 0) > MAX_CONTENT_LENGTH:
        raise ValueError("Response too large")

    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    # Each post row is a 'tr.athing' with a title in the sibling row's 'titleline' span
    headlines = []
    for item in soup.select("tr.athing"):
        try:
            titleline = item.select_one(".titleline a")
            if not titleline:
                continue

            title = titleline.get_text(strip=True)
            link = titleline['href']
            if link.startswith("item?id="):
                link = f"https://news.ycombinator.com/{link}"

            headlines.append({
                "title": title,
                "link": link,
                "source": "Hacker News"
            })
        except Exception as e:
            logger.warning(f"Error parsing Hacker News item: {e}")

    return headlines[:15]
'''
@safe_fetch
@cached(cache)
def fetch_hackernews():
    top_stories_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
    r = session.get(top_stories_url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    ids = r.json()[:30]

    headlines = []
    for story_id in ids:
        item_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
        item_r = session.get(item_url, timeout=REQUEST_TIMEOUT)
        if item_r.status_code != 200:
            continue
        item = item_r.json()
        if not item or 'title' not in item:
            continue

        title = item["title"]
        link = item.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
        upvotes = item.get("score", 0)
        comments = item.get("descendants", 0)

        headlines.append({
            "title": title,
            "link": link,
            "source": "Hacker News",
            "upvotes": upvotes,
            "comments": comments
        })
    return headlines
'''


@safe_fetch
@cached(ycomb_cache)
def fetch_ycombinator(source="ycomb"):
    rss_url = "https://www.ycombinator.com/blog/rss/"
    allowed_domains = ["www.ycombinator.com"]

    # Y Combinator's RSS feed is public and intended for bots
    headers = {
        "User-Agent": get_random_user_agent()
    }

    r = rate_limited_request(rss_url, headers=headers)

    if int(r.headers.get("Content-Length") or 0) > MAX_CONTENT_LENGTH:
        raise ValueError("Response too large")

    r.raise_for_status()

    import feedparser
    feed = feedparser.parse(r.text)

    headlines = []
    for entry in feed.entries:
        try:
            title = entry.title
            link = validate_url(entry.link, allowed_domains)
            headlines.append({
                "title": title,
                "link": link,
                "source": "YC Blog"
            })
        except Exception as e:
            logger.warning(f"Error parsing YC Blog RSS item: {e}")

    return headlines[:15]




@safe_fetch
@cached(cache)
def fetch_twitter_trending(source="twitter"):
    logger.warning("Twitter scraping is disabled (requires JS rendering or API).")
    return [{"title": "#MockTrend", "link": "https://twitter.com", "source": "Twitter"}]


# Dev trigger for testing
if __name__ == "__main__":
    for func in [
        fetch_google_news,
        fetch_reddit_news,
        fetch_hackernews,
        fetch_ycombinator,
        fetch_twitter_trending
    ]:
        headlines = func()
        print(f"{func.__name__}: {len(headlines)} headlines fetched.")
        

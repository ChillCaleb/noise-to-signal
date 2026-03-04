#!/usr/bin/env python3
"""
News scraper script that fetches articles from RSS feeds and extracts clean text.
Saves results to JSONL format for further processing.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set
from urllib.parse import urlparse

import feedparser
import trafilatura
from tqdm import tqdm


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def fetch_rss_feeds(feed_urls: List[str]) -> List[Dict[str, str]]:
    """
    Fetch articles from RSS feeds.
    
    Args:
        feed_urls: List of RSS feed URLs
        
    Returns:
        List of articles with url, title, and source
    """
    articles = []
    
    for feed_url in feed_urls:
        print(f"Fetching RSS feed: {feed_url}")
        try:
            feed = feedparser.parse(feed_url)
            source = urlparse(feed_url).netloc.replace("www.", "").replace("feeds.", "")
            
            for entry in feed.entries:
                article = {
                    "url": entry.get("link", ""),
                    "title": entry.get("title", ""),
                    "source": source,
                }
                if article["url"]:  # Only add if URL exists
                    articles.append(article)
                    
        except Exception as e:
            print(f"Error fetching {feed_url}: {e}")
            continue
    
    return articles


def deduplicate_urls(articles: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Remove duplicate articles by URL.
    
    Args:
        articles: List of article dictionaries
        
    Returns:
        List of deduplicated articles
    """
    seen_urls: Set[str] = set()
    unique_articles = []
    
    for article in articles:
        url = article["url"]
        if url not in seen_urls:
            seen_urls.add(url)
            unique_articles.append(article)
    
    return unique_articles


def extract_article_text(url: str) -> str:
    """
    Download and extract clean text from an article.
    
    Args:
        url: Article URL
        
    Returns:
        Extracted article text, or empty string if extraction fails
    """
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded)
            return text or ""
        return ""
    except Exception as e:
        print(f"Error extracting text from {url}: {e}")
        return ""


def scrape_articles(
    feed_urls: List[str],
    output_path: Path,
    max_articles: int = 500
) -> None:
    """
    Main scraping function that orchestrates the entire process.
    
    Args:
        feed_urls: List of RSS feed URLs
        output_path: Path to save JSONL output
        max_articles: Maximum number of articles to process
    """
    print(f"\n📰 Starting news scraper...")
    print(f"Output will be saved to: {output_path}\n")
    
    # Fetch articles from RSS feeds
    print("Step 1: Fetching RSS feeds...")
    articles = fetch_rss_feeds(feed_urls)
    print(f"✓ Found {len(articles)} articles in RSS feeds")
    
    # Deduplicate
    print("\nStep 2: Removing duplicates...")
    articles = deduplicate_urls(articles)
    print(f"✓ Deduplicated to {len(articles)} unique articles")
    
    # Limit to max_articles
    articles = articles[:max_articles]
    print(f"✓ Limited to {len(articles)} articles")
    
    # Create output directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Download and extract articles
    print(f"\nStep 3: Downloading and extracting articles...")
    saved_count = 0
    
    with open(output_path, "w") as f:
        for article in tqdm(articles, desc="Processing articles"):
            url = article["url"]
            title = article["title"]
            source = article["source"]
            
            # Extract article text
            text = extract_article_text(url)
            
            if text:  # Only save if we successfully extracted text
                output_record = {
                    "url": url,
                    "title": title,
                    "source": source,
                    "text": text,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                f.write(json.dumps(output_record) + "\n")
                saved_count += 1
    
    print(f"\n✓ Successfully saved {saved_count} articles to {output_path}")
    print(f"Total processed: {len(articles)} articles")


def main():
    """Main entry point."""
    # RSS feed URLs
    feed_urls = [
        "https://feeds.npr.org/1006/rss.xml",
        "https://www.federalreserve.gov/feeds/press_all.xml",
    ]
    
    # Output path
    project_root = get_project_root()
    output_path = project_root / "data" / "articles_raw.jsonl"
    
    try:
        scrape_articles(feed_urls, output_path, max_articles=500)
        print("\n✅ Script completed successfully!")
        return 0
    except KeyboardInterrupt:
        print("\n\n⚠️  Script interrupted by user.")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

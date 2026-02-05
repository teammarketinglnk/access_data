import requests
import xml.etree.ElementTree as ET
import json
import os
import smtplib
import logging
import sys
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# =====================================================
# LOAD ENV
# =====================================================
load_dotenv()

# =====================================================
# LOGGING CONFIG (FILE + CONSOLE)
# =====================================================
LOG_FILE = "status.log"

logger = logging.getLogger("breachsense")
logger.setLevel(logging.INFO)
logger.handlers.clear()

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
)

file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
file_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

# =====================================================
# CONFIG
# =====================================================
SITEMAP_URL = "https://www.breachsense.com/sitemap.xml"
BREACH_PREFIX = "https://www.breachsense.com/breaches/"

MASTER_FILE = "breachsense_master.json"
DAILY_FILE = "breachsense_daily.json"

MAX_LINKS_PER_EMAIL = 40

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BreachSenseDailyScraper/1.0)"
}

# =====================================================
# SMTP / EMAIL CONFIG (ENV)
# =====================================================
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)
EMAIL_TO = [e.strip() for e in os.getenv("EMAIL_TO", "").split(",") if e.strip()]

def require_env(name):
    if not os.getenv(name):
        raise RuntimeError(f"Missing required env var: {name}")

require_env("SMTP_HOST")
require_env("SMTP_USER")
require_env("SMTP_PASSWORD")
if not EMAIL_TO:
    raise RuntimeError("EMAIL_TO missing")

# =====================================================
# FETCH SITEMAP
# =====================================================
def fetch_sitemap():
    logger.info(f"Fetching sitemap: {SITEMAP_URL}")
    response = requests.get(SITEMAP_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.content

# =====================================================
# PARSE SITEMAP
# =====================================================
def parse_sitemap(xml_data):
    root = ET.fromstring(xml_data)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    results = []
    for url in root.findall("sm:url", ns):
        loc = url.find("sm:loc", ns)
        lastmod = url.find("sm:lastmod", ns)

        if loc is None or not loc.text:
            continue

        link = loc.text.strip()
        if not link.startswith(BREACH_PREFIX):
            continue

        results.append({
            "url": link,
            "lastmod": lastmod.text.strip() if lastmod is not None else None
        })

    return results

# =====================================================
# JSON HELPERS
# =====================================================
def load_json(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else []
    except json.JSONDecodeError:
        logger.warning(f"{path} invalid JSON — reinitializing")
        return []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# =====================================================
# EMAIL
# =====================================================
def send_email(subject, body):
    logger.info("📧 Preparing email")

    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(EMAIL_TO)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    logger.info("🔌 Connecting to SMTP server")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

    logger.info("✅ Email sent successfully")

def chunk_list(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]

# =====================================================
# MAIN
# =====================================================
def main():
    logger.info("🚀 BreachSense daily scrape started")

    try:
        current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        logger.info(f"Run date (UTC): {current_date}")

        scraped_today = parse_sitemap(fetch_sitemap())
        logger.info(f"Sitemap parsed | URLs found: {len(scraped_today)}")

        master_data = load_json(MASTER_FILE)
        master_map = {item["url"]: item for item in master_data}
        logger.info(f"Master JSON loaded | Records: {len(master_data)}")

        new_links = []
        updated_links = []

        for item in scraped_today:
            url = item["url"]
            lastmod = item["lastmod"]

            if url not in master_map:
                new_links.append({
                    "url": url,
                    "lastmod": lastmod,
                    "scraped_date": current_date
                })
            else:
                old_lastmod = master_map[url].get("lastmod")
                if lastmod and lastmod != old_lastmod:
                    master_map[url]["lastmod"] = lastmod
                    master_map[url]["scraped_date"] = current_date
                    updated_links.append(url)

        logger.info(
            f"Comparison complete | New: {len(new_links)} | Updated: {len(updated_links)}"
        )

        master_data.extend(new_links)
        save_json(MASTER_FILE, master_data)

        save_json(DAILY_FILE, {
            "date": current_date,
            "total_scraped_today": len(scraped_today),
            "new_links_count": len(new_links),
            "updated_links_count": len(updated_links),
            "new_links": new_links,
            "updated_links": updated_links
        })

        logger.info("JSON files saved")

        # =================================================
        # EMAIL (SPLIT IF > 40)
        # =================================================
        if not new_links:
            logger.info("📭 No new URLs found — email NOT sent")
            return

        subject = f"🚨 BreachSense NEW URLs | {current_date}"
        chunks = list(chunk_list(new_links, MAX_LINKS_PER_EMAIL))

        for idx, chunk in enumerate(chunks, start=1):
            body_lines = [
                f"Date: {current_date}",
                f"Total NEW BreachSense URLs: {len(new_links)}",
                f"Email part: {idx} of {len(chunks)}",
                ""
            ]
            body_lines.extend(f"- {n['url']}" for n in chunk)
            send_email(subject, "\n".join(body_lines))

        logger.info(f"📧 Sent {len(chunks)} email(s)")

        logger.info("🏁 BreachSense daily scrape completed successfully")

    except Exception:
        logger.exception("❌ BreachSense daily scrape FAILED")
        raise
    finally:
        for handler in logger.handlers:
            handler.flush()

# =====================================================
# ENTRY POINT
# =====================================================
if __name__ == "__main__":
    main()

import requests
import xml.etree.ElementTree as ET
import json
import os
import smtplib
import logging
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# -----------------------------
# LOAD ENV + LOGGING
# -----------------------------
load_dotenv()

logging.basicConfig(
    filename="status.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

# -----------------------------
# CONFIG
# -----------------------------
SITEMAP_URL = "https://www.breachsense.com/sitemap.xml"
BREACH_PREFIX = "https://www.breachsense.com/breaches/"

MASTER_FILE = "breachsense_master.json"
DAILY_FILE = "breachsense_daily.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BreachSenseDailyScraper/1.0)"
}

# -----------------------------
# SMTP / EMAIL CONFIG (ENV)
# -----------------------------
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)
EMAIL_TO = os.getenv("EMAIL_TO", "").split(",")

# -----------------------------
# FETCH SITEMAP
# -----------------------------
def fetch_sitemap():
    response = requests.get(SITEMAP_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.content

# -----------------------------
# PARSE SITEMAP
# -----------------------------
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

# -----------------------------
# JSON HELPERS
# -----------------------------
def load_json(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            return json.loads(content)
    except json.JSONDecodeError:
        logging.warning(f"{path} invalid JSON — reinitializing")
        return []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# -----------------------------
# SMTP EMAIL SENDER
# -----------------------------
def send_email(subject: str, body: str):
   def send_email(subject: str, body: str):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_FROM
        msg["To"] = ", ".join(EMAIL_TO)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

        logging.info("Email sent successfully via SMTP_SSL")

    except Exception as e:
        logging.exception("Email sending failed")
        raise




# -----------------------------
# MAIN DAILY LOGIC
# -----------------------------
def main():
    try:
        logging.info("🚀 BreachSense daily scrape started")

        current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        xml_data = fetch_sitemap()
        scraped_today = parse_sitemap(xml_data)
        logging.info(f"Sitemap parsed | URLs found: {len(scraped_today)}")

        master_data = load_json(MASTER_FILE)
        master_map = {item["url"]: item for item in master_data}
        logging.info(f"Master JSON loaded | Existing URLs: {len(master_data)}")

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
                    updated_links.append({
                        "url": url,
                        "old_lastmod": old_lastmod,
                        "new_lastmod": lastmod,
                        "scraped_date": current_date
                    })
                    master_map[url]["lastmod"] = lastmod
                    master_map[url]["scraped_date"] = current_date

        logging.info(
            f"Comparison complete | New: {len(new_links)} | Updated: {len(updated_links)}"
        )

        # Update master
        master_data.extend(new_links)
        save_json(MASTER_FILE, master_data)

        # Daily JSON
        save_json(DAILY_FILE, {
            "date": current_date,
            "total_scraped_today": len(scraped_today),
            "new_links_count": len(new_links),
            "updated_links_count": len(updated_links),
            "new_links": new_links,
            "updated_links": updated_links
        })

        logging.info("Master and daily JSON saved")

        # -----------------------------
        # EMAIL (ALWAYS SENT)
        # -----------------------------
        subject = f"📊 BreachSense Daily Scrape Report | {current_date}"

        if new_links:
            logging.info("Preparing email: NEW URLs found")
            lines = [
                f"Date: {current_date}",
                f"New BreachSense URLs found: {len(new_links)}",
                ""
            ]
            for n in new_links:
                lines.append(f" - {n['url']}")
            body = "\n".join(lines)
        else:
            logging.info("Preparing email: NO new URLs found")
            body = (
                f"Date: {current_date}\n\n"
                "✅ No new BreachSense URLs were found today.\n\n"
                "This is an automated daily status email."
            )

        send_email(subject, body)

        logging.info("🏁 BreachSense daily scrape completed successfully")

    except Exception as e:
        logging.exception("❌ BreachSense daily scrape FAILED")
        raise

# -----------------------------
# ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    main()

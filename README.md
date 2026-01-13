# BreachSense Daily Scraper

A production-ready Python scraper that monitors the **BreachSense sitemap** daily, detects **new and updated breach URLs**, persists history in JSON, and sends **automated email reports**.  
The scraper is designed to run **locally** or **automatically via GitHub Actions**.

---

## 🚀 What This Project Does

On a **daily basis**, the scraper:

1. Fetches the BreachSense sitemap
2. Filters only `/breaches/` URLs
3. Compares results with a persisted master JSON file
4. Detects:
   - 🆕 New breach URLs
   - 🔁 Updated breach URLs (via `lastmod`)
5. Updates local JSON history
6. Sends an email report:
   - Lists **new URLs**
   - Sends a **“no new URLs found”** message if nothing changed
7. Commits updated JSON back to GitHub (when run in Actions)

---

## 📁 Project Structure

scrapercopy/
│
├── .github/
│ └── workflows/
│ └── databreach-daily.yml # GitHub Actions workflow
│
├── databreach.py # Main scraper script
├── requirements.txt # Python dependencies
├── .gitignore # Ignored files
├── .env # Local environment variables (NOT committed)
├── status.log # Optional runtime logs
│
├── breachsense_master.json # Persistent history (committed)
├── breachsense_daily.json # Daily snapshot (optional)
│
└── README.md # This file


---

## 🧠 How the Daily Logic Works

- **First run**:  
  All breach URLs are treated as new and stored in `breachsense_master.json`.

- **Subsequent runs**:
  - URLs already in `master.json` are ignored unless `lastmod` changes
  - Only **truly new URLs** trigger “new breach” emails
  - Updated URLs are tracked in JSON and console output (not emailed)

The master JSON file acts as **long-term memory**.

---

## 📦 Dependencies

### Python Version
- Python **3.10+** (3.12 recommended)

### Install Requirements
```bash
pip install -r requirements.txt


requirements.txt

requests
python-dotenv
🔐 Environment Variables

Create a .env file locally:

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=your_email@gmail.com
EMAIL_TO=recipient1@example.com,recipient2@example.com


⚠️ Never commit .env to GitHub.

▶️ Run Locally
1. Create & activate virtual environment (Windows)
python -m venv venv
venv\Scripts\activate


If PowerShell blocks activation:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

2. Install dependencies
pip install -r requirements.txt

3. Run the scraper
python databreach.py

🤖 Run Automatically with GitHub Actions

The scraper runs daily using:

.github/workflows/databreach-daily.yml

What GitHub Actions Does

Checks out the repository

Installs Python & dependencies

Loads secrets as environment variables

Runs databreach.py

Commits updated JSON files (if changed)

Required GitHub Secrets

Add these in:

Repo → Settings → Secrets and variables → Actions

Secret Name	Description
SMTP_HOST	SMTP server
SMTP_PORT	SMTP port
SMTP_USER	Email username
SMTP_PASSWORD	Email app password
EMAIL_FROM	From email
EMAIL_TO	Comma-separated recipients
📊 Output Files
File	Purpose
breachsense_master.json	Persistent history (important)
breachsense_daily.json	Daily snapshot
status.log	Optional logging
✉️ Email Behavior
Scenario	Email Sent
New URLs found	✅ Yes (with URLs)
No new URLs	✅ Yes (“No new URLs found”)
Script failure	❌ No (workflow fails visibly)
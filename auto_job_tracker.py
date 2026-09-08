import requests
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# --- SECURE CONFIGURATION (Pulls from hidden GitHub Secrets) ---
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")

# --- CONFIGURATION (CLOUD COMPATIBLE) ---
# Saves the tracking file directly inside your repository directory
SEEN_JOBS_FILE = os.path.join(os.path.dirname(__file__), "seen_jobs.json")

COMPANIES = [
    "Rivian", "Lucid", "Canoo", "Tesla",
    "Slate", "Ferrari", "Porsche", "McLaren", "Ford", "GM", "Kia",
    "Toyota", "Honda", "Hyundai", "BMW", "Mercedes Benz", "Audi",
    "Suzuki", "Volkswagen", "Nissan", "Subaru", "Mazda", "Volvo",
    "Polestar", "Jaguar", "Land Rover", "Mitsubishi", "Stellantis",

    # F1 teams (2026 grid, distinct from road-car parent companies)
    "Mercedes-AMG Petronas F1 Team", "Red Bull Racing", "Racing Bulls",
    "Williams Racing", "Aston Martin F1 Team", "Alpine F1 Team",
    "Audi F1", "Haas F1 Team", "Cadillac F1",
    "Ford Performance", "Toyota Racing Development", "Honda Racing Corporation",

    # NASCAR teams
    "Hendrick Motorsports", "Joe Gibbs Racing", "Team Penske",
    "Stewart-Haas Racing", "Richard Childress Racing", "Chip Ganassi Racing",
    "23XI Racing", "Trackhouse Racing", "RFK Racing", "Front Row Motorsports",
    "Wood Brothers Racing", "Spire Motorsports", "Kaulig Racing",
    "JTG Daugherty Racing", "Legacy Motor Club",

    # IndyCar teams
    "Andretti Global", "Arrow McLaren", "Rahal Letterman Lanigan Racing",
    "Ed Carpenter Racing", "A.J. Foyt Racing", "Meyer Shank Racing",
    "Juncos Hollinger Racing", "Dale Coyne Racing", "PREMA Racing",

    # Space companies
    "SpaceX", "Blue Origin", "Rocket Lab", "Relativity Space",
    "Firefly Aerospace", "Sierra Space", "Axiom Space", "Astra",
    "Northrop Grumman", "Lockheed Martin", "United Launch Alliance",
    "Virgin Galactic", "Redwire Space", "Intuitive Machines",
    "Astrobotic", "Varda Space Industries", "Boeing"

    # Film industry - camera/optics engineering
    "ARRI", "RED Digital Cinema", "IMAX", "Panavision", "Sony Pictures Imageworks",

    # Film industry - practical effects/animatronics/production design
    "Legacy Effects", "Weta Workshop", "Industrial Light & Magic",
    "Walt Disney Imagineering",

    # Film industry - rigging/camera support/motion control
    "Chapman/Leonard Studio Equipment", "J.L. Fisher", "Mo-Sys", "Kessler Crane",
]

COMPANY_ALIASES = {
    "ECR": "Ed Carpenter Racing",
    "GM": "General Motors",
    "RLL": "Rahal Letterman Lanigan Racing",
    "JGR": "Joe Gibbs Racing",
    "RFK": "RFK Racing",
    "ULA": "United Launch Alliance",
    "ILM": "Industrial Light & Magic",
    "WDI": "Walt Disney Imagineering",
    "TRD": "Toyota Racing Development",
    "HRC": "Honda Racing Corporation",
}

# Your Target Keywords
QUERY_KEYWORDS = '"mechanical design" OR "design engineer" OR "test engineer" OR "validation engineer" OR "hands-on" OR "trackside" OR "testing" OR "manufacturing" OR "fabrication" OR "prototyping" OR "CAD" OR "suspension" OR "vehicle dynamics" OR "simulation"'
def load_seen_jobs():
    if not os.path.exists(SEEN_JOBS_FILE):
        return set()
    try:
        with open(SEEN_JOBS_FILE, 'r') as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_seen_jobs(seen_jobs):
    os.makedirs(os.path.dirname(SEEN_JOBS_FILE), exist_ok=True)
    with open(SEEN_JOBS_FILE, 'w') as f:
        json.dump(list(seen_jobs), f)

def search_jobs(company_name):
    if not RAPIDAPI_KEY:
        print("Missing RapidAPI Key!")
        return []
        
    search_company = COMPANY_ALIASES.get(company_name, company_name)
    url = "https://jsearch.p.rapidapi.com/search-v2" 
    
    querystring = {
        "query": f"{search_company} {QUERY_KEYWORDS} internship OR co-op",
        "page": "1",
        "num_pages": "1"
    }
    
    # We add a fake web browser User-Agent so GitHub runners bypass firewalls
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        
        # This logs a clear error if your API key token count runs out
        if response.status_code != 200:
            print(f"API Error for {search_company}: Status Code {response.status_code} - Reason: {response.text[:100]}")
            return []
            
        payload = response.json()
        data = payload.get('data', {})
        return data.get('jobs', []) if isinstance(data, dict) else []
        
    except Exception as e:
        print(f"Error searching {search_company}: {e}")
        return []

def send_email(new_jobs):
    if not new_jobs:
        return 
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("Missing email credentials! Cannot send report.")
        return

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL or SENDER_EMAIL
    msg['Subject'] = f"🚨 New Internships Found ({len(new_jobs)} new)"

    body = "Here are the new internship/co-op postings matching your criteria:\n\n"
    for job in new_jobs:
        company = job.get('employer_name', 'Unknown company')
        title = job.get('job_title', 'Untitled position')
        city = job.get('job_city', '')
        state = job.get('job_state', '')
        location = ', '.join(part for part in (city, state) if part) or 'Location not provided'
        link = job.get('job_apply_link', 'No application link provided')
        body += f"• **{company}** - {title}\n"
        body += f"  Location: {location}\n"
        body += f"  Link: {link}\n\n"

    msg.attach(MIMEText(body, 'plain'))

    try:
        # We target Google's direct IP address on port 465 to skip the DNS lookup bug
        server = smtplib.SMTP_SSL('74.125.142.108', 465, timeout=15)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Email sent successfully using direct IP address!")
    except Exception as e:
        print(f"Direct IP SSL connection failed: {e}. Trying TLS IP fallback...")
        try:
            # Fallback to port 587 using the direct IP address
            server = smtplib.SMTP('74.125.142.108', 587, timeout=15)
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
            server.quit()
            print("Email sent successfully via TLS IP fallback!")
        except Exception as fallback_error:
            print(f"Failed to send email entirely: {fallback_error}")



def main():
    seen_jobs = load_seen_jobs()
    new_jobs_list = []

    print("Starting job scrape...")
    for company in COMPANIES:
        print(f"Checking {company}...")
        results = search_jobs(company)
        
        for job in results:
            job_id = job.get('job_id')
            if job_id and job_id not in seen_jobs:
                seen_jobs.add(job_id)
                new_jobs_list.append(job)
    
    save_seen_jobs(seen_jobs)
    
    if new_jobs_list:
        print(f"Found {len(new_jobs_list)} new jobs! Sending report...")
        send_email(new_jobs_list)
    else:
        print("No new jobs found today.")

if __name__ == "__main__":
    main()

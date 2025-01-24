import requests
import sqlite3
import tweepy
import time
from datetime import datetime

# Configure Twitter API credentials (replace with your keys)
TWITTER_API_KEY = "Replace"
TWITTER_API_SECRET = "Replace"
TWITTER_ACCESS_TOKEN = "Replace"
TWITTER_ACCESS_SECRET = "Replace"

# Initialize Twitter API client
def init_twitter_client():
    auth = tweepy.OAuthHandler(TWITTER_API_KEY, TWITTER_API_SECRET)
    auth.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
    return tweepy.API(auth)

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect("subdomains.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subdomains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subdomain TEXT UNIQUE,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            change_type TEXT
        )
    """)
    conn.commit()
    return conn

# Fetch subdomains from crt.sh
def fetch_subdomains(domain):
    url = f"https://crt.sh/?q={domain}&output=json"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        subdomains = {entry['name_value']: (entry['cert_id'], entry['cert_info']) for entry in data}
        return subdomains
    else:
        print(f"Failed to fetch data: {response.status_code}")
        return {}

# Compare subdomains and update database
def update_db(conn, new_subdomains):
    cursor = conn.cursor()
    cursor.execute("SELECT subdomain, cert_id FROM subdomains")
    existing_subdomains = {row[0]: row[1] for row in cursor.fetchall()}

    added_subdomains = new_subdomains.keys() - existing_subdomains.keys()
    changed_subdomains = {
        subdomain: new_subdomains[subdomain]
        for subdomain in new_subdomains
        if subdomain in existing_subdomains and new_subdomains[subdomain][0] != existing_subdomains[subdomain]
    }

    for subdomain in added_subdomains:
        cursor.execute("INSERT INTO subdomains (subdomain, cert_id, change_type) VALUES (?, ?, ?)", (subdomain, new_subdomains[subdomain][0], 'added'))
    for subdomain, (cert_id, cert_info) in changed_subdomains.items():
        cursor.execute("UPDATE subdomains SET cert_id = ?, change_type = ? WHERE subdomain = ?", (cert_id, 'changed', subdomain))

    conn.commit()
    return added_subdomains, changed_subdomains

# Post update on Twitter
def post_to_twitter(client, subdomain, change_type, cert_id):
    message = f"🚨 New subdomain detected for @megaeth_labs: {subdomain} (CRT.sh ID: https://crt.sh/?id={cert_id}) at {datetime.now()}"

    if change_type == 'changed':
        message = f"🚨 Subdomain change detected for @megaeth_labs: {subdomain} (CRT.sh ID: https://crt.sh/?id={cert_id}) at {datetime.now()}"

    try:
        client.update_status(message)
        print(f"Posted on Twitter: {message}")
    except tweepy.TweepError as e:
        print(f"Failed to post on Twitter: {e}")

# Main function
def main():
    domain = "megaeth.com"  # Replace with your domain
    conn = init_db()
    twitter_client = init_twitter_client()

    while True:
        print(f"Checking for updates at {datetime.now()}...")
        new_subdomains = fetch_subdomains(domain)
        if new_subdomains:
            added_subdomains, changed_subdomains = update_db(conn, new_subdomains)
            for subdomain in added_subdomains:
                cert_id = new_subdomains[subdomain][0]
                post_to_twitter(twitter_client, subdomain, 'added', cert_id)
            for subdomain, (cert_id, cert_info) in changed_subdomains.items():
                post_to_twitter(twitter_client, subdomain, 'changed', cert_id)
        else:
            print("No new subdomains detected.")
        
        time.sleep(900)  # Check every 15 minutes

if __name__ == "__main__":
    main()

# Network Consistency Monitor
# Purpose: Resolves a specific domain to its IP and cross-references it against
#          a known "allowlist" stored in GCS. Helps detect DNS shifts that
#          could break firewall whitelisting rules.

import socket
import json
import logging
from google.cloud import storage
from google.cloud import logging as cloud_logging
from google.cloud.logging.handlers import CloudLoggingHandler

# ---------------------------------------------------------
# 1. OBSERVABILITY & LOGGING SETUP
# ---------------------------------------------------------
# Initialize Google Cloud Logging to ensure output is captured in
# GCP Operations Suite (formerly Stackdriver) rather than local stdout.
logging_client = cloud_logging.Client()
cloud_handler = CloudLoggingHandler(logging_client, name="IP_Checker_Log")
logger = logging.getLogger("IP_Checker")
logger.setLevel(logging.INFO)
logger.addHandler(cloud_handler)

# ---------------------------------------------------------
# 2. CONFIGURATION
# ---------------------------------------------------------
# Target domain and the GCS location of the "Source of Truth" JSON file.
DOMAIN = '<apigee proxy url domain here>'  # Target API Endpoint
BUCKET_NAME = '<your gcs bucket name here>' # Storage bucket for config data
FILE_NAME = 'apigee_api_IP_Address_check.json' # JSON file containing allowed IPs

# ---------------------------------------------------------
# 3. CORE FUNCTIONS
# ---------------------------------------------------------

def get_ip_from_domain(domain):
    """
    Performs a DNS lookup to resolve the current IP address of the target.
    Returns: IP string or None on failure.
    """
    try:
        ip_address = socket.gethostbyname(domain)
        return ip_address
    except socket.gaierror as e:
        logger.error(f"Apigee API IP Address Checker : Failed to resolve IP Address for domain {domain}: {e}")
        return None

def fetch_allowed_ips(bucket_name, file_name):
    """
    Connects to Google Cloud Storage to retrieve the whitelist.
    Parses the JSON content to extract valid IP addresses.
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        
        # Download and parse JSON
        content = blob.download_as_text()
        data = json.loads(content)
        
        # Handle potential schema variations (single 'ip_address' vs list 'ips')
        allowed_ips = [data["ip_address"]] if "ip_address" in data else data.get("ips", [])
        return allowed_ips
    except Exception as e:
        logger.error(f"Apigee API IP Address Checker : Failed to fetch allowed IPs: {e}")
        return []

def log_ip_check(ip, allowed_ips):
    """
    Compares the live resolved IP against the stored allowlist.
    Logs an ALERT if a mismatch is found (indicating a potential firewall breach).
    """
    if ip in allowed_ips:
        logger.info(f"Apigee API IP Address Checker : IP {ip} has not Changed and matches.")
    else:
        # Crucial: This log entry serves as the trigger for alert policies.
        logger.info(f"Apigee API IP Address Checker : IP {ip} has changed and does NOT match. Please notify team that whitelist is needed. ALERT")

# ---------------------------------------------------------
# 4. EXECUTION ENTRY POINT
# ---------------------------------------------------------
def main():
    # Step 1: Resolve the live IP
    ip = get_ip_from_domain(DOMAIN)
    if not ip:
        logger.error("Apigee API IP Address Checker : No IP address retrieved from domain.")
        return

    # Step 2: Fetch the approved list
    allowed_ips = fetch_allowed_ips(BUCKET_NAME, FILE_NAME)
    
    # Step 3: Compare and Log
    log_ip_check(ip, allowed_ips)

if __name__ == "__main__":
    main()

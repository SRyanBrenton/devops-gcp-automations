# apigee-ip-address-checker 🌐 🛡️

![Python](https://img.shields.io/badge/Python-3.9-blue?style=for-the-badge&logo=python&logoColor=white)
![GCP](https://img.shields.io/badge/Google_Cloud-Scheduler_%26_Functions-red?style=for-the-badge&logo=google-cloud&logoColor=white)
![Status](https://img.shields.io/badge/Status-Production-success?style=for-the-badge)

## 📖 Overview
This repository contains a **Network Observability Utility** running on Google Cloud Functions. 

It periodically resolves the DNS of a specific Apigee Edge endpoint and compares the returned IP address against a known "Source of Truth" stored in Google Cloud Storage (GCS). If a discrepancy is detected, it logs a high-severity alert to notify Operations and Client Success teams.

## ⚠️ The Business Problem
Enterprise clients often enforce strict **Egress Firewall Rules**, explicitly whitelisting only specific destination IP addresses for traffic leaving their networks.

**The Challenge:** Apigee Edge IP addresses are dynamic and can change without warning.
**The Risk:** If Apigee rotates an IP address and the client firewall is not updated, the client's traffic will be blocked immediately, causing a service outage.

**The Solution:** This script acts as an early warning system, detecting DNS changes immediately so we can proactively notify clients to update their firewalls before traffic is impacted.

## 🏗 Architecture
The solution uses a serverless, stateful monitoring approach:

`Cloud Scheduler (Hourly)` ➔ `Cloud Function` ➔ `DNS Lookup` ↔ `Compare vs GCS Allowlist` ➔ `Cloud Logging (Alert Trigger)`



## ✨ Key Features
* **Stateful Monitoring:** Uses a JSON file in GCS as the "State File" to remember valid IPs.
* **Log-Based Alerting:** Outputs structured logs designed to trigger GCP Alert Policies when the keyword `ALERT` is detected.
* **Zero-Maintenance:** Runs entirely on serverless infrastructure (Cloud Functions) with no VM management required.

## ⚙️ Configuration & Environment
The script uses hardcoded constants for the target domain and bucket location (configured in `main.py`).

| Constant | Description | Example |
| :--- | :--- | :--- |
| `DOMAIN` | The Apigee API endpoint to monitor. | `api.my-company.com` |
| `BUCKET_NAME` | GCS Bucket storing the allowlist JSON. | `ops-config-store` |
| `FILE_NAME` | The JSON file containing valid IPs. | `apigee_allowlist.json` |

## 📄 Data Schema
The "Source of Truth" file stored in GCS must follow this JSON structure:

```json
{
  "ip_address": "34.120.55.12"
}
```
*Or for multiple allowed IPs:*
```json
{
  "ips": ["34.120.55.12", "34.120.55.13"]
}
```

## 🚀 Deployment Guide

### 1. Prerequisites
* **GCS Bucket:** Create a bucket and upload the initial `apigee_api_IP_Address_check.json` file.
* **IAM:** The Cloud Function Service Account needs `Storage Object Viewer` permissions on the bucket.

### 2. Deploy Function
Deploy using the Google Cloud CLI:

```bash
gcloud functions deploy apigee-ip-monitor \
--runtime python39 \
--trigger-http \
--entry-point main \
--region us-central1 \
--memory 128MB
```

*Note: While deployed as HTTP, this function is intended to be triggered via Cloud Scheduler.*

### 3. Configure Scheduler
Set the job to run hourly to ensure rapid detection of IP shifts.

```bash
gcloud scheduler jobs create http check-apigee-ip \
--schedule "0 * * * *" \
--uri "https://[YOUR-FUNCTION-URL].cloudfunctions.net/apigee-ip-monitor" \
--http-method GET
```

## 🚨 Alerting Strategy
To receive notifications, create a **Log-Based Alert Policy** in Google Cloud Monitoring with the following query:

```text
resource.type="cloud_function"
logName="projects/[PROJECT_ID]/logs/IP_Checker_Log"
textPayload:"ALERT"
```
**Threshold:** > 0 occurrences per 5 minutes.

---
*Maintained by Shaun Brenton*

# Google-cloud-storage-file-archiver 📦 ☁️

![Python](https://img.shields.io/badge/Python-3.9-blue?style=for-the-badge&logo=python&logoColor=white)
![Google Cloud Run](https://img.shields.io/badge/Cloud_Run-Function-red?style=for-the-badge&logo=google-cloud&logoColor=white)
![GCS](https://img.shields.io/badge/Storage-Object_Lifecycle-orange?style=for-the-badge)

## 📖 Overview
This project is a high-performance **Cloud Run Function** designed to automate the archiving of Google Cloud Storage (GCS) objects. 

Unlike simple lifecycle policies, this function allows for complex filtering logic (prefixes, specific storage classes) and immediate "Copy-Verify-Delete" operations. It is optimized for high throughput using threaded concurrency and includes safety mechanisms to handle Cloud Function timeouts gracefully.

## 🏗 Architecture
This function is designed to be triggered via **Cloud Scheduler** (for recurring batch jobs) or an ad-hoc **HTTP Request**.

`Cloud Scheduler (Cron)` ➔ `HTTP POST Payload` ➔ `Cloud Run Function` ➔ `Thread Pool (90 Workers)` ➔ `GCS (Source ➔ Archive)`



## ✨ Key Engineering Features
* **High Concurrency:** Utilizes `concurrent.futures.ThreadPoolExecutor` with 90 workers to process thousands of files rapidly within the serverless execution window.
* **Defensive Data Handling:** Implements a strict **Copy ➔ Verify ➔ Delete** workflow. Source files are never deleted unless the destination file is confirmed to exist.
* **Resilience & Retries:** Custom decorator logic handles `429 TooManyRequests` and `5xx` errors from the GCS API with exponential backoff.
* **Graceful Shutdown:** The function monitors its own execution time (`FUNCTION_TIMEOUT_SECONDS`). If the timeout approaches, it stops accepting new files to prevent hard termination during a file transfer.

## ⚙️ Configuration & Payload
The function is stateless and configuration is passed via the HTTP JSON Body. This allows a single function deployment to manage multiple archiving rules (e.g., one scheduler job for Logs, another for Images).

**Example JSON Payload:**
```json
{
  "source_bucket": "prod-app-logs",
  "destination_bucket": "coldline-archive-logs",
  "filename_prefixes": ["2023/", "error-logs/"],
  "min_age_days_for_transfer": 90,
  "delete_source_after_transfer": true
}
```

**Payload Parameters:**

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `source_bucket` | String | Yes | The bucket to read files from. |
| `destination_bucket` | String | Yes | The bucket to move files to. |
| `min_age_days_for_transfer` | Int | No | Only move files older than X days. |
| `filename_prefixes` | List | No | Filter files by specific folder paths. Default: `[""]` (All). |
| `delete_source_after_transfer` | Bool | No | If `true`, deletes original after verification. Default: `false`. |

## 🛠️ Internal Tuning
The script contains internal constants optimized for Cloud Run (Gen 2) environments. These can be modified in `main.py` if instance sizes change:

* `MAX_WORKERS = 90`: Optimized for instances with >1 vCPU.
* `TARGET_SOURCE_STORAGE_CLASS = "COLDLINE"`: Ensures we only move specific tiers of data.
* `FUNCTION_TIMEOUT_SECONDS = 3600`: Matches the max timeout of the Cloud Run Function.

## 🚀 Deployment Guide

### 1. Prerequisites
* GCP Project with Cloud Build and Cloud Functions enabled.
* Service Account with `Storage Object Admin` permissions on both buckets.

### 2. Install Dependencies (Local)
```bash
pip install -r requirements.txt
```

### 3. Deploy to Google Cloud
Deploy as a Gen 2 Cloud Function (Cloud Run) with a long timeout to allow for batch processing.

```bash
gcloud functions deploy gcs-archiver \
--gen2 \
--runtime python310 \
--region us-central1 \
--source . \
--entry-point direct_copy_or_move \
--trigger-http \
--timeout 3600s \
--memory 1Gi \
--min-instances 0
```

### 4. Schedule the Job
Create a Cloud Scheduler job to trigger the function every night at 2 AM.

```bash
gcloud scheduler jobs create http archive-logs-daily \
--schedule="0 2 * * *" \
--uri="https://[YOUR-FUNCTION-URL].a.run.app" \
--http-method=POST \
--headers="Content-Type=application/json" \
--message-body='{"source_bucket":"my-prod","destination_bucket":"my-archive","min_age_days_for_transfer":90,"delete_source_after_transfer":true}'
```

## 🤝 Contributing
1.  Fork the repository.
2.  Create a feature branch.
3.  Submit a Pull Request.

---
*Created and maintained by Shaun Brenton*

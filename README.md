# Google Cloud Automation & SRE Tooling 🛠️ ☁️

![Status](https://img.shields.io/badge/Status-Active-success?style=for-the-badge)
![Focus](https://img.shields.io/badge/Focus-Infrastructure_Automation-blue?style=for-the-badge)

## 👋 Overview
Welcome to my automation library. This repository houses production-grade **Cloud Functions** and **Python Scripts** designed to solve complex infrastructure challenges on Google Cloud Platform (GCP).

These tools focus on **Cost Optimization**, **Network Observability**, and **Storage Lifecycle Management**, replacing manual operations work with event-driven code.

## 📂 Project Index

| Automation Tool | Stack | Description |
| :--- | :--- | :--- |
| **[GCS File Archiver](./google-cloud-storage-file-archiver)** | Python, Cloud Run | A high-concurrency utility that moves objects to "Coldline" storage based on custom prefixes and age, bypassing standard lifecycle limitations. |
| **[Apigee IP Monitor](./apigee-ip-address-checker)** | Python, Cloud Functions | A network observability agent that tracks DNS changes for Apigee endpoints to prevent firewall egress failures. |

## 💻 Technologies Used
* **Compute:** Cloud Run, Cloud Functions (Gen 2)
* **Storage:** Google Cloud Storage (Standard & Coldline)
* **Language:** Python 3.9+ (with `concurrent.futures` for threading)
* **Observability:** Cloud Logging, Cloud Monitoring

## 🏗 Architecture Principles
This repository follows **SRE Best Practices**:
1.  **Stateless Design:** All functions are idempotent and can be re-run without side effects.
2.  **Defensive Coding:** Operations like "Delete" are always preceded by a "Verify" step.
3.  **Config-Driven:** Hardcoded values are avoided in favor of JSON payloads or GCS config files.

---
*Created and maintained by [SRyanBrenton](https://github.com/SRyanBrenton)*

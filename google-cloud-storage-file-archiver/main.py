# Optimized Cloud Function with internal listing (no sharding)
# Supports: prefix filtering, storage class, age filtering, retryable listing, and parallel GCS ops

import os
import functions_framework
from google.cloud import storage
import json
import base64
import os.path
import datetime
import time
import concurrent.futures
from google.api_core import exceptions as api_exceptions
import threading

MAX_WORKERS = 90
MAX_API_RETRIES = 4
INITIAL_BACKOFF_SECONDS = 1.5
TARGET_SOURCE_STORAGE_CLASS = "COLDLINE"
MIN_AGE_DAYS_THRESHOLD = 90
FUNCTION_TIMEOUT_SECONDS = 3600
GRACEFUL_SHUTDOWN_BUFFER_SECONDS = 30

storage_client = storage.Client()

from flask import Request

@functions_framework.http
def direct_copy_or_move(request: Request):
    start_time = time.time()

    def time_remaining():
        return FUNCTION_TIMEOUT_SECONDS - (time.time() - start_time)

    def should_continue():
        return time_remaining() > GRACEFUL_SHUTDOWN_BUFFER_SECONDS

    def _retry_blob_listing(bucket, prefix=None):
        backoff = INITIAL_BACKOFF_SECONDS
        for attempt in range(MAX_API_RETRIES):
            try:
                return bucket.list_blobs(fields="items(name,updated,storageClass),nextPageToken")
            except Exception as e:
                if attempt < MAX_API_RETRIES - 1:
                    print(f"Retrying list_blobs for prefix '{prefix}' (attempt {attempt + 1}): {e}")
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    print(f"Failed to list blobs for prefix '{prefix}' after {MAX_API_RETRIES} attempts.")
                    raise

    def generate_eligible_blobs(bucket, prefixes, min_age_timedelta):
        now = datetime.datetime.now(datetime.timezone.utc)

        def filter_blobs(blob_iter):
            for page in blob_iter.pages:
                for blob in page:
                    if not should_continue():
                        print("Aborting listing — time buffer exceeded.")
                        return
                    if blob.name.endswith('/'):
                        continue
                    filename = os.path.basename(blob.name)
                    if prefixes != [""] and not any(filename.startswith(p) for p in prefixes):
                        continue
                    if min_age_timedelta and (blob.updated is None or (now - blob.updated) < min_age_timedelta):
                        continue
                    if getattr(blob, 'storage_class', None) != TARGET_SOURCE_STORAGE_CLASS:
                        continue
                    yield blob

        if prefixes == [""]:
            yield from filter_blobs(_retry_blob_listing(bucket))
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(prefixes), 10)) as lister_pool:
                futures = {
                    lister_pool.submit(_retry_blob_listing, bucket, prefix): prefix
                    for prefix in prefixes
                }
                for future in concurrent.futures.as_completed(futures):
                    try:
                        yield from filter_blobs(future.result())
                    except Exception as e:
                        print(f"Error listing for prefix {futures[future]}: {e}")

    try:
        config = request.get_json()
        if not config:
            return "Invalid request: No JSON payload received", 400
        print(f"Successfully parsed configuration from HTTP request: {config}")
    except (ValueError, TypeError, json.JSONDecodeError) as e:
        print(f"Failed to decode or parse Pub/Sub message payload: {e}")
        return f"Error: Could not process configuration payload from HTTP request.", 400

    try:
        SOURCE_BUCKET_NAME = config.get('source_bucket')
        DESTINATION_BUCKET_NAME = config.get('destination_bucket')
        FILENAME_PREFIXES = config.get('filename_prefixes', [""])
        min_age_days_for_transfer = config.get('min_age_days_for_transfer')
        delete_source_validated = config.get('delete_source_after_transfer', False)

        if not SOURCE_BUCKET_NAME or not DESTINATION_BUCKET_NAME:
            raise ValueError("Missing source or destination bucket name.")
        if SOURCE_BUCKET_NAME == DESTINATION_BUCKET_NAME:
            raise ValueError("Source and destination buckets must differ.")

        if not isinstance(FILENAME_PREFIXES, list) or not all(isinstance(p, str) for p in FILENAME_PREFIXES):
            raise ValueError("'filename_prefixes' must be a list of strings.")

        min_age_timedelta = None
        if min_age_days_for_transfer:
            min_age_days_validated = int(min_age_days_for_transfer)
            if min_age_days_validated > MIN_AGE_DAYS_THRESHOLD:
                min_age_timedelta = datetime.timedelta(days=min_age_days_validated)

    except Exception as e:
        print(f"Invalid configuration received in payload: {e}")
        return f"Error: Invalid configuration. {e}", 400

    source_bucket = storage_client.bucket(SOURCE_BUCKET_NAME)
    destination_bucket = storage_client.bucket(DESTINATION_BUCKET_NAME)

    blobs_to_process = list(generate_eligible_blobs(source_bucket, FILENAME_PREFIXES, min_age_timedelta))

    if not blobs_to_process:
        print("No eligible files found.")
        return "OK", 200

    results = {"copied": 0, "verified": 0, "deleted": 0, "failed": 0}
    lock = threading.Lock()

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_blob = {
            executor.submit(process_single_file_copy_or_move, source_bucket, blob, destination_bucket, delete_source_validated): blob
            for blob in blobs_to_process
        }

        for i, future in enumerate(concurrent.futures.as_completed(future_to_blob), 1):
            blob = future_to_blob[future]
            if not should_continue():
                print("Aborting processing — nearing timeout.")
                break
            try:
                success, copied, verified, deleted = future.result()
                with lock:
                    if success:
                        results["copied"] += copied
                        results["verified"] += verified
                        results["deleted"] += deleted
                    else:
                        results["failed"] += 1
            except Exception as e:
                print(f"Worker failed for {blob.name}: {e}")
                with lock:
                    results["failed"] += 1

            if i % 1000 == 0:
                print(f"Processed {i} files...")

    print("--- Summary ---")
    print(f"Copied: {results['copied']}, Verified: {results['verified']}, Deleted: {results['deleted']}, Failed: {results['failed']}")
    if results["failed"] > 0:
        print(f"Warning: {results['failed']} files failed. See logs for details.")
    return "OK", 200


def _retry_gcs_operation(func, *args, **kwargs):
    func_name = getattr(func, '__name__', 'unknown')
    target = args[0] if args else 'UNKNOWN'
    target_name = getattr(target, 'name', str(target))

    backoff = INITIAL_BACKOFF_SECONDS
    for attempt in range(MAX_API_RETRIES):
        try:
            if attempt > 0:
                print(f"Retry {attempt + 1} for {func_name}({target_name})...")
            return func(*args, **kwargs)
        except (
            api_exceptions.TooManyRequests,
            api_exceptions.InternalServerError,
            api_exceptions.BadGateway,
            api_exceptions.ServiceUnavailable,
            api_exceptions.GatewayTimeout,
        ) as e:
            print(f"Retryable error on {target_name}: {e}")
            if attempt < MAX_API_RETRIES - 1:
                time.sleep(backoff)
                backoff *= 2
            else:
                raise
        except Exception as e:
            print(f"Fatal error on {target_name}: {e}")
            raise


def process_single_file_copy_or_move(source_bucket, source_blob, destination_bucket, delete_source):
    # Defensive check: Ensure source blob still exists
    existing_blob = _retry_gcs_operation(source_bucket.get_blob, source_blob.name)
    if not existing_blob:
        print(f"Skipping {source_blob.name}: No longer exists at time of processing.")
        return False, 0, 0, 0
    destination_blob_name = source_blob.name
    copied = False
    verified = False
    deleted = False
    try:
        _retry_gcs_operation(source_bucket.copy_blob, source_blob, destination_bucket, destination_blob_name)
        copied = True

        dest_blob = _retry_gcs_operation(destination_bucket.get_blob, destination_blob_name)
        if dest_blob:
            verified = True
        else:
            raise Exception(f"Destination blob {destination_blob_name} not found after copy.")

        if delete_source and verified:
            _retry_gcs_operation(source_blob.delete)
            deleted = True

        return True, int(copied), int(verified), int(deleted)
    except Exception as e:
        print(f"ERROR processing {source_blob.name}: {e}")
        return False, 0, 0, 0

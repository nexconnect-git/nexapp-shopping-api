"""Background jobs for log archival."""

from pathlib import Path

import boto3

try:
    from django_rq import job
except Exception:  # pragma: no cover - local Windows fallback without rq fork support
    def job(*_args, **_kwargs):
        def decorator(function):
            return function
        return decorator


@job("default", timeout=180)
def upload_log_file_to_s3(
    local_file_path,
    s3_bucket,
    s3_key,
    s3_region_name=None,
    s3_endpoint_url=None,
    aws_access_key_id=None,
    aws_secret_access_key=None,
):
    """Upload a local log file snapshot to S3."""
    file_path = Path(local_file_path)
    if not file_path.exists() or not s3_bucket or not s3_key:
        return

    client_kwargs = {
        "service_name": "s3",
        "region_name": s3_region_name,
        "endpoint_url": s3_endpoint_url,
    }
    if aws_access_key_id and aws_secret_access_key:
        client_kwargs["aws_access_key_id"] = aws_access_key_id
        client_kwargs["aws_secret_access_key"] = aws_secret_access_key

    s3_client = boto3.client(**client_kwargs)
    s3_client.upload_file(str(file_path), s3_bucket, s3_key)

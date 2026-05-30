"""Custom logging handlers."""

import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import django_rq
except Exception:  # pragma: no cover - test stubs/local env fallback
    django_rq = None

from helpers.logging_tasks import upload_log_file_to_s3


class PerUserDailyS3Handler(logging.Handler):
    """
    Write logs to per-user, per-day files and mirror them to S3.

    S3 key format:
        <prefix>/<username>/<ddmmyyyy>/files/<filename>
    """

    _SAFE_SEGMENT = re.compile(r"[^a-zA-Z0-9_.-]+")
    _DEFAULT_ENQUEUE_EXCLUDE_PREFIXES = (
        "rq.",
        "django_rq",
        "boto3",
        "botocore",
        "urllib3",
        "helpers.logging_tasks",
    )

    def __init__(
        self,
        local_base_dir,
        filename="application.log",
        s3_enabled=False,
        s3_bucket="",
        s3_prefix="logs",
        s3_region_name=None,
        s3_endpoint_url=None,
        aws_access_key_id=None,
        aws_secret_access_key=None,
        rq_queue_name="default",
        upload_interval_seconds=30,
        timezone_name="Asia/Kolkata",
        enqueue_exclude_prefixes=None,
    ):
        super().__init__()
        self.local_base_dir = Path(local_base_dir)
        self.filename = filename
        self.s3_enabled = bool(s3_enabled and s3_bucket)
        self.s3_bucket = s3_bucket
        self.s3_prefix = (s3_prefix or "log").strip("/") or "log"
        self.s3_region_name = s3_region_name
        self.s3_endpoint_url = s3_endpoint_url
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.rq_queue_name = rq_queue_name or "default"
        self.upload_interval_seconds = max(int(upload_interval_seconds), 1)
        self._lock = threading.RLock()
        self._last_enqueue_by_file = {}
        self._known_local_files = set()
        self._timezone = self._build_timezone(timezone_name)
        self.enqueue_exclude_prefixes = tuple(
            enqueue_exclude_prefixes or self._DEFAULT_ENQUEUE_EXCLUDE_PREFIXES
        )

    def emit(self, record):
        try:
            username = self._safe_segment(getattr(record, "username", "system"))
            date_segment = datetime.now(self._timezone).strftime("%d%m%Y")
            relative_dir = Path(self.s3_prefix) / username / date_segment / "files"
            local_file = self.local_base_dir / relative_dir / self.filename
            message = self.format(record)

            with self._lock:
                local_file.parent.mkdir(parents=True, exist_ok=True)
                with local_file.open("a", encoding="utf-8") as file_pointer:
                    file_pointer.write(f"{message}\n")
                self._known_local_files.add((local_file, relative_dir))

                if (not self._should_skip_enqueue(record.name)) and self._should_enqueue(local_file):
                    self._enqueue_upload(local_file, relative_dir)
        except Exception:
            self.handleError(record)

    def close(self):
        with self._lock:
            for local_file, relative_dir in list(self._known_local_files):
                if self.s3_enabled and local_file.exists():
                    self._enqueue_upload(local_file, relative_dir, force=True)
        super().close()

    def _should_enqueue(self, local_file):
        if not self.s3_enabled:
            return False
        now_epoch = time.time()
        last_enqueue = self._last_enqueue_by_file.get(local_file, 0)
        return (now_epoch - last_enqueue) >= self.upload_interval_seconds

    def _enqueue_upload(self, local_file, relative_dir, force=False):
        if not self.s3_enabled:
            return
        if not local_file.exists():
            return
        if not force and not self._should_enqueue(local_file):
            return

        s3_key = f"{relative_dir.as_posix()}/{self.filename}"
        if django_rq is None:
            return
        now_epoch = time.time()
        slot = int(now_epoch // self.upload_interval_seconds)
        job_id = self._build_job_id(local_file, slot, force)
        try:
            queue = django_rq.get_queue(self.rq_queue_name)
            queue.enqueue(
                upload_log_file_to_s3,
                str(local_file),
                self.s3_bucket,
                s3_key,
                self.s3_region_name,
                self.s3_endpoint_url,
                self.aws_access_key_id,
                self.aws_secret_access_key,
                job_id=job_id,
            )
            self._last_enqueue_by_file[local_file] = now_epoch
        except Exception:
            return

    @classmethod
    def _safe_segment(cls, value):
        cleaned = cls._SAFE_SEGMENT.sub("_", (value or "system")).strip("._")
        return cleaned or "system"

    @staticmethod
    def _build_timezone(timezone_name):
        if not timezone_name:
            return ZoneInfo("UTC")
        try:
            return ZoneInfo(timezone_name)
        except Exception:
            return ZoneInfo("UTC")

    def _build_job_id(self, local_file, slot, force):
        file_key = self._SAFE_SEGMENT.sub("_", local_file.as_posix())
        suffix = f"final-{time.time_ns()}" if force else str(slot)
        return f"log-upload:{file_key}:{suffix}"

    def _should_skip_enqueue(self, logger_name):
        if not logger_name:
            return False
        return any(logger_name.startswith(prefix) for prefix in self.enqueue_exclude_prefixes)

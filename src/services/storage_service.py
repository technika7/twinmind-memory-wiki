"""
Storage service — abstraction over MinIO/S3 for the memory file tree.

Provides file-system-like operations (list, read, write, search)
over S3-compatible object storage.
"""

import json
import logging
import re
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from src.config import get_settings

logger = logging.getLogger(__name__)


class StorageService:
    """
    S3-compatible storage service for the memory file tree.

    All paths are relative to the bucket root and use forward slashes.
    Example: "people/john_doe/profile.md"
    """

    def __init__(self):
        settings = get_settings()
        self.bucket = settings.s3_bucket_name
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )

    def ensure_bucket(self) -> None:
        """Create the bucket if it doesn't exist."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)
            logger.info("Created bucket: %s", self.bucket)

    # ── Write Operations ───────────────────────────────────────

    def write_file(
        self, path: str, content: str, content_type: str = "text/markdown"
    ) -> None:
        """Write content to a file in the memory tree."""
        self.client.put_object(
            Bucket=self.bucket,
            Key=self._normalize_path(path),
            Body=content.encode("utf-8"),
            ContentType=content_type,
        )
        logger.debug("Wrote file: %s", path)

    def write_json(self, path: str, data: dict | list) -> None:
        """Write JSON data to a file."""
        content = json.dumps(data, indent=2, default=str)
        self.write_file(path, content, content_type="application/json")

    # ── Read Operations ────────────────────────────────────────

    def read_file(self, path: str) -> Optional[str]:
        """Read file content as a string. Returns None if not found."""
        try:
            response = self.client.get_object(
                Bucket=self.bucket,
                Key=self._normalize_path(path),
            )
            return response["Body"].read().decode("utf-8")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise

    def read_json(self, path: str) -> Optional[dict | list]:
        """Read and parse a JSON file. Returns None if not found."""
        content = self.read_file(path)
        if content is None:
            return None
        return json.loads(content)

    def file_exists(self, path: str) -> bool:
        """Check if a file exists."""
        try:
            self.client.head_object(
                Bucket=self.bucket,
                Key=self._normalize_path(path),
            )
            return True
        except ClientError:
            return False

    # ── List Operations (ls) ───────────────────────────────────

    def list_directory(self, path: str = "", depth: Optional[int] = None) -> list[dict]:
        """
        List contents of a directory path.

        Returns a list of dicts with:
        - name: filename or directory name
        - type: "file" or "directory"
        - path: full path
        - size: file size in bytes (files only)
        - last_modified: ISO timestamp (files only)

        Args:
            path: Directory path to list (empty string for root).
            depth: If 0, only immediate children. If None, recursive.
        """
        prefix = self._normalize_path(path)
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        # Use delimiter for non-recursive listing
        delimiter = "/" if depth == 0 else ""

        paginator = self.client.get_paginator("list_objects_v2")
        pages = paginator.paginate(
            Bucket=self.bucket,
            Prefix=prefix,
            Delimiter=delimiter,
        )

        entries = []
        seen_dirs = set()

        for page in pages:
            # Directories (common prefixes when using delimiter)
            for cp in page.get("CommonPrefixes", []):
                dir_path = cp["Prefix"].rstrip("/")
                dir_name = dir_path.split("/")[-1]
                if dir_name.startswith("."):
                    continue
                entries.append(
                    {
                        "name": dir_name,
                        "type": "directory",
                        "path": "/" + dir_path,
                    }
                )

            # Files
            for obj in page.get("Contents", []):
                key = obj["Key"]
                # Skip the prefix itself
                if key == prefix:
                    continue

                # For recursive listing, extract directory entries
                relative = key[len(prefix) :]
                parts = relative.split("/")

                if len(parts) > 1 and delimiter == "":
                    # This file is in a subdirectory — register the dir
                    dir_name = parts[0]
                    dir_path = prefix + dir_name
                    if dir_path not in seen_dirs:
                        seen_dirs.add(dir_path)
                        entries.append(
                            {
                                "name": dir_name,
                                "type": "directory",
                                "path": "/" + dir_path,
                            }
                        )
                elif len(parts) == 1:
                    entries.append(
                        {
                            "name": parts[0],
                            "type": "file",
                            "path": "/" + key,
                            "size": obj["Size"],
                            "last_modified": obj["LastModified"].isoformat(),
                        }
                    )

        # Deduplicate and sort: directories first, then files
        unique_entries = []
        seen = set()
        for entry in entries:
            if entry["path"] not in seen:
                seen.add(entry["path"])
                unique_entries.append(entry)

        unique_entries.sort(key=lambda x: (x["type"] != "directory", x["name"]))
        return unique_entries

    # ── Search Operations (grep) ───────────────────────────────

    def search_files(
        self,
        query: str,
        path: str = "",
        case_insensitive: bool = True,
    ) -> list[dict]:
        """
        Search for a text pattern across all files under a path.

        Returns grep-style results with line numbers and matching content.
        """
        prefix = self._normalize_path(path)
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        paginator = self.client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=self.bucket, Prefix=prefix)

        results = []
        flags = re.IGNORECASE if case_insensitive else 0

        for page in pages:
            for obj in page.get("Contents", []):
                key = obj["Key"]
                # Only search text files
                if not (key.endswith(".md") or key.endswith(".json")):
                    continue

                content = self.read_file(key)
                if content is None:
                    continue

                matches = []
                for line_num, line in enumerate(content.split("\n"), start=1):
                    if re.search(re.escape(query), line, flags):
                        matches.append(
                            {
                                "line": line_num,
                                "content": line.strip(),
                            }
                        )

                if matches:
                    results.append(
                        {
                            "path": "/" + key,
                            "matches": matches,
                        }
                    )

        return results

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _normalize_path(path: str) -> str:
        """
        Normalize a file path for S3 key usage.

        Strips leading slashes, collapses double slashes,
        and resolves '..' components.
        """
        # Remove leading slash
        path = path.lstrip("/")
        # Collapse double slashes
        while "//" in path:
            path = path.replace("//", "/")
        # Resolve parent references
        parts = []
        for part in path.split("/"):
            if part == "..":
                if parts:
                    parts.pop()
            elif part and part != ".":
                parts.append(part)
        return "/".join(parts)


"""Fail-closed, type-aware resource scope matching.

Supported resource identifiers:
- Absolute POSIX filesystem paths
- Absolute Windows filesystem paths
- s3://bucket/key URIs
- Standard S3 bucket and object ARNs
- Other AWS ARNs, with exact-match-only authorization

Filesystem matching is lexical. Actual filesystem operations must
additionally enforce resolved-path containment and protect against
symlink and TOCTOU attacks.
"""

from __future__ import annotations

import ntpath
import posixpath
import re
from urllib.parse import urlsplit

_S3_BUCKET_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9.-]{1,61}[a-z0-9])?$"
)

_ARN_RE = re.compile(
    r"^arn:([a-z0-9-]+):([a-z0-9-]+):([^:]*):([^:]*):(.+)$"
)


def capability_is_covered(requested: str, granted: str) -> bool:
    """Return whether a granted capability covers a requested capability."""
    if (
        not isinstance(requested, str)
        or not isinstance(granted, str)
        or not requested
        or not granted
    ):
        return False

    return requested == granted or requested.startswith(granted + ":")


def _parse_filesystem_resource(
    resource: str,
) -> tuple[str, str] | None:
    """Return (filesystem_flavour, normalized_path), or None."""

    if (
        not isinstance(resource, str)
        or not resource
        or "\x00" in resource
    ):
        return None

    # Reject Windows device namespaces.
    if resource.startswith(("\\\\?\\", "\\\\.\\")):
        return None

    drive, _ = ntpath.splitdrive(resource)

    # Windows drive paths and UNC paths.
    if drive or resource.startswith("\\\\"):
        if not ntpath.isabs(resource):
            return None

        normalized = ntpath.normcase(ntpath.normpath(resource))

        return ("windows", normalized)

    # POSIX absolute paths.
    if posixpath.isabs(resource):
        normalized = posixpath.normpath(resource)

        return ("posix", normalized)

    # Relative and unsupported paths are denied.
    return None


def _parse_s3_resource(
    resource: str,
) -> tuple[str, str] | None:
    """Return canonical (bucket, key), or None for an invalid S3 URI."""

    try:
        parsed = urlsplit(resource)
        port = parsed.port
    except ValueError:
        return None

    if parsed.scheme.lower() != "s3":
        return None

    if (
        not parsed.netloc
        or parsed.username
        or parsed.password
        or port is not None
    ):
        return None

    if parsed.query or parsed.fragment:
        return None

    bucket = parsed.netloc

    if not _S3_BUCKET_RE.fullmatch(bucket):
        return None

    # S3 object keys are opaque identifiers, not filesystem paths.
    # Do not collapse "." or ".." segments.
    key = parsed.path[1:] if parsed.path.startswith("/") else parsed.path

    if "*" in bucket or "*" in key:
        return None

    return (bucket, key)


def _parse_arn_resource(
    resource: str,
) -> tuple[str, ...] | None:
    """Parse an ARN into a canonical authorization identity."""

    match = _ARN_RE.fullmatch(resource)

    if not match:
        return None

    partition, service, region, account, arn_resource = match.groups()

    if service == "s3":
        # Standard S3 ARN:
        # arn:aws:s3:::bucket
        # arn:aws:s3:::bucket/key
        if region or account or not arn_resource:
            return None

        bucket, separator, key = arn_resource.partition("/")

        if not _S3_BUCKET_RE.fullmatch(bucket):
            return None

        if "*" in arn_resource:
            return None

        return ("s3", bucket, key if separator else "")

    # Other ARN types have service-specific resource semantics.
    # Only exact identity matching is allowed.
    if "*" in resource:
        return None

    return (
        "arn",
        partition,
        service,
        region,
        account,
        arn_resource,
    )


def _parse_resource(resource: str) -> tuple[str, ...] | None:
    """Identify and canonicalize a supported resource identifier."""

    if not isinstance(resource, str) or not resource:
        return None

    if resource.startswith("arn:"):
        return _parse_arn_resource(resource)

    if resource.lower().startswith("s3://"):
        parsed_s3 = _parse_s3_resource(resource)

        if parsed_s3 is None:
            return None

        return ("s3", *parsed_s3)

    filesystem = _parse_filesystem_resource(resource)

    if filesystem is None:
        return None

    return filesystem


def _s3_key_is_within_scope(
    requested_key: str,
    granted_key: str,
) -> bool:
    """Check S3 object-key containment using a slash boundary."""

    if requested_key == granted_key:
        return True

    if not granted_key:
        return True

    return requested_key.startswith(granted_key.rstrip("/") + "/")


def _filesystem_path_is_within_scope(
    requested: tuple[str, ...],
    granted: tuple[str, ...],
) -> bool:
    """Check normalized filesystem containment."""

    # Never unpack or compare different resource types.
    if len(requested) != 2 or len(granted) != 2:
        return False

    requested_flavour, requested_path = requested
    granted_flavour, granted_path = granted

    if requested_flavour != granted_flavour:
        return False

    path_module = (
        ntpath if requested_flavour == "windows" else posixpath
    )

    try:
        common = path_module.commonpath(
            [requested_path, granted_path]
        )
    except ValueError:
        # Different Windows drives or incompatible roots.
        return False

    return common == granted_path


def resource_is_within_scope(
    resource: str,
    roots: list[str],
) -> bool:
    """Return whether a resource is contained by an authorized root.

    Malformed identifiers, unsupported formats, and empty scopes deny.
    Different resource types cannot authorize one another.
    """

    requested = _parse_resource(resource)

    if requested is None or not isinstance(roots, list) or not roots:
        return False

    for root in roots:
        granted = _parse_resource(root)

        if granted is None:
            continue

        requested_type = requested[0]
        granted_type = granted[0]

        # Filesystem resources must have the same filesystem type.
        if requested_type in ("posix", "windows"):
            if granted_type not in ("posix", "windows"):
                continue

            if _filesystem_path_is_within_scope(requested, granted):
                return True

            continue

        # S3 URIs and S3 ARNs share the canonical "s3" identity.
        if requested_type == "s3":
            if granted_type != "s3":
                continue

            _, requested_bucket, requested_key = requested
            _, granted_bucket, granted_key = granted

            if (
                requested_bucket == granted_bucket
                and _s3_key_is_within_scope(
                    requested_key,
                    granted_key,
                )
            ):
                return True

            continue

        # Generic ARNs are exact-match-only.
        if requested_type == "arn":
            if granted_type == "arn" and requested == granted:
                return True

    return False


def validate_resource_scope(resource_scope: dict) -> None:
    """Validate resource scope before storing a capability lease.

    Accepted forms:
        {}                                  -- deny all
        {"resources": []}                  -- deny all
        {"resources": ["/data"]}           -- explicit resource root

    Unknown keys, wildcards, malformed identifiers, and unsupported
    resource formats are rejected.
    """

    if not isinstance(resource_scope, dict):
        raise ValueError("INVALID_RESOURCE_SCOPE: must be a dict")

    unknown_keys = set(resource_scope) - {"resources"}

    if unknown_keys:
        raise ValueError(
            "INVALID_RESOURCE_SCOPE: unsupported keys: "
            + ", ".join(sorted(str(key) for key in unknown_keys))
        )

    if "resources" not in resource_scope:
        return

    resources = resource_scope["resources"]

    if not isinstance(resources, list):
        raise ValueError(
            "INVALID_RESOURCE_SCOPE: resources must be a list"
        )

    for resource in resources:
        if not isinstance(resource, str) or not resource.strip():
            raise ValueError(
                "INVALID_RESOURCE_SCOPE: resource entries "
                "must be non-empty strings"
            )

        if "*" in resource:
            raise ValueError(
                "INVALID_RESOURCE_SCOPE: wildcard resources "
                "are not supported"
            )

        if _parse_resource(resource) is None:
            raise ValueError(
                "INVALID_RESOURCE_SCOPE: unsupported or malformed "
                f"resource identifier: {resource!r}"
            )

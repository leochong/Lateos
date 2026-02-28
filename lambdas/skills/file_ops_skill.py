"""
File Operations Skill Lambda

Handles file storage and retrieval via S3.
Implements RULE 1: All secrets via Secrets Manager (S3 encryption keys).
Implements RULE 2: Scoped IAM role (access only to user's S3 prefix).
Implements RULE 6: Per-user data isolation (S3 prefix = user_id).

Capabilities:
- Upload files to S3
- Download files from S3
- List files (user's files only)
- Delete files (user's files only)
- Get file metadata
- Generate pre-signed URLs for sharing

Security:
- S3 bucket with KMS encryption
- Per-user prefix isolation (users can only access their own files)
- Scoped IAM role (prefix = lateos/{env}/files/{user_id}/*)
- No cross-user access (RULE 6 enforcement)
- File size limits
- Virus scanning (deferred to Phase 4)
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

# Initialize AWS clients
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

# Initialize logger and tracer
logger = Logger(service="file_ops_skill")
tracer = Tracer(service="file_ops_skill")

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
FILES_BUCKET_NAME = os.environ.get("FILES_BUCKET_NAME")
AUDIT_TABLE_NAME = os.environ.get("AUDIT_TABLE_NAME")

# File size limits
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
PRESIGNED_URL_EXPIRY = 3600  # 1 hour


class FileOpsError(Exception):
    """Raised when file operation fails"""

    pass


def get_user_prefix(user_id: str) -> str:
    """
    Get S3 prefix for user's files.

    Args:
        user_id: Cognito user ID

    Returns:
        S3 prefix path
    """
    return f"lateos/{ENVIRONMENT}/files/{user_id}/"


def validate_file_path(user_id: str, file_path: str) -> str:
    """
    Validate and normalize file path within user's prefix.

    Args:
        user_id: Cognito user ID
        file_path: Requested file path

    Returns:
        Full S3 key within user's prefix

    Raises:
        FileOpsError: If path attempts directory traversal
    """
    # Prevent directory traversal
    if ".." in file_path or file_path.startswith("/"):
        raise FileOpsError("Invalid file path: directory traversal not allowed")

    # Build full S3 key
    user_prefix = get_user_prefix(user_id)
    full_key = f"{user_prefix}{file_path}"

    return full_key


def upload_file(
    user_id: str,
    file_path: str,
    content: bytes,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Upload file to S3.

    Args:
        user_id: Cognito user ID
        file_path: File path within user's storage
        content: File content as bytes
        content_type: Optional MIME type
        metadata: Optional file metadata

    Returns:
        Upload result dict with S3 key and metadata
    """
    logger.info(f"Uploading file for user {user_id}: {file_path}")

    if not FILES_BUCKET_NAME:
        raise FileOpsError("File storage bucket not configured")

    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        raise FileOpsError(f"File too large. Maximum size is {MAX_FILE_SIZE / (1024 * 1024)} MB")

    # Validate and get full S3 key
    s3_key = validate_file_path(user_id, file_path)

    try:
        # Upload to S3 with server-side encryption
        put_args = {
            "Bucket": FILES_BUCKET_NAME,
            "Key": s3_key,
            "Body": content,
            "ServerSideEncryption": "aws:kms",  # KMS encryption
        }

        if content_type:
            put_args["ContentType"] = content_type

        if metadata:
            put_args["Metadata"] = metadata

        s3_client.put_object(**put_args)

        result = {
            "file_path": file_path,
            "s3_key": s3_key,
            "size": len(content),
            "content_type": content_type,
            "uploaded_at": datetime.now().isoformat(),
        }

        # Log to audit table
        log_file_action(user_id, "upload_file", {"file_path": file_path, "size": len(content)})

        return result

    except ClientError as e:
        logger.error(f"Failed to upload file: {e}")
        raise FileOpsError(f"Failed to upload file: {e}")


def download_file(user_id: str, file_path: str) -> Dict[str, Any]:
    """
    Download file from S3.

    Args:
        user_id: Cognito user ID
        file_path: File path within user's storage

    Returns:
        File content and metadata
    """
    logger.info(f"Downloading file for user {user_id}: {file_path}")

    if not FILES_BUCKET_NAME:
        raise FileOpsError("File storage bucket not configured")

    # Validate and get full S3 key
    s3_key = validate_file_path(user_id, file_path)

    try:
        # Get object from S3
        response = s3_client.get_object(Bucket=FILES_BUCKET_NAME, Key=s3_key)

        result = {
            "file_path": file_path,
            "content": response["Body"].read(),
            "content_type": response.get("ContentType"),
            "size": response.get("ContentLength"),
            "last_modified": (
                response.get("LastModified").isoformat() if response.get("LastModified") else None
            ),
        }

        # Log to audit table
        log_file_action(user_id, "download_file", {"file_path": file_path})

        return result

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            raise FileOpsError(f"File not found: {file_path}")
        else:
            logger.error(f"Failed to download file: {e}")
            raise FileOpsError(f"Failed to download file: {e}")


def list_files(user_id: str, prefix: str = "", limit: int = 100) -> List[Dict[str, Any]]:
    """
    List files in user's storage.

    Args:
        user_id: Cognito user ID
        prefix: Optional prefix within user's storage
        limit: Maximum number of files to return

    Returns:
        List of file metadata dicts
    """
    logger.info(f"Listing files for user {user_id}, prefix: {prefix}")

    if not FILES_BUCKET_NAME:
        raise FileOpsError("File storage bucket not configured")

    # Get user's S3 prefix
    user_prefix = get_user_prefix(user_id)
    full_prefix = f"{user_prefix}{prefix}"

    try:
        # List objects in S3
        response = s3_client.list_objects_v2(
            Bucket=FILES_BUCKET_NAME, Prefix=full_prefix, MaxKeys=limit
        )

        files = []
        for obj in response.get("Contents", []):
            # Remove user prefix from key for display
            file_path = obj["Key"][len(user_prefix) :]
            files.append(
                {
                    "file_path": file_path,
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                }
            )

        # Log to audit table
        log_file_action(user_id, "list_files", {"prefix": prefix, "count": len(files)})

        return files

    except ClientError as e:
        logger.error(f"Failed to list files: {e}")
        raise FileOpsError(f"Failed to list files: {e}")


def delete_file(user_id: str, file_path: str) -> Dict[str, Any]:
    """
    Delete file from S3.

    Args:
        user_id: Cognito user ID
        file_path: File path within user's storage

    Returns:
        Deletion confirmation dict
    """
    logger.info(f"Deleting file for user {user_id}: {file_path}")

    if not FILES_BUCKET_NAME:
        raise FileOpsError("File storage bucket not configured")

    # Validate and get full S3 key
    s3_key = validate_file_path(user_id, file_path)

    try:
        # Delete object from S3
        s3_client.delete_object(Bucket=FILES_BUCKET_NAME, Key=s3_key)

        result = {
            "file_path": file_path,
            "status": "deleted",
            "deleted_at": datetime.now().isoformat(),
        }

        # Log to audit table
        log_file_action(user_id, "delete_file", {"file_path": file_path})

        return result

    except ClientError as e:
        logger.error(f"Failed to delete file: {e}")
        raise FileOpsError(f"Failed to delete file: {e}")


def get_file_metadata(user_id: str, file_path: str) -> Dict[str, Any]:
    """
    Get file metadata from S3.

    Args:
        user_id: Cognito user ID
        file_path: File path within user's storage

    Returns:
        File metadata dict
    """
    logger.info(f"Getting file metadata for user {user_id}: {file_path}")

    if not FILES_BUCKET_NAME:
        raise FileOpsError("File storage bucket not configured")

    # Validate and get full S3 key
    s3_key = validate_file_path(user_id, file_path)

    try:
        # Head object to get metadata
        response = s3_client.head_object(Bucket=FILES_BUCKET_NAME, Key=s3_key)

        result = {
            "file_path": file_path,
            "content_type": response.get("ContentType"),
            "size": response.get("ContentLength"),
            "last_modified": (
                response.get("LastModified").isoformat() if response.get("LastModified") else None
            ),
            "etag": response.get("ETag"),
            "metadata": response.get("Metadata", {}),
        }

        return result

    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            raise FileOpsError(f"File not found: {file_path}")
        else:
            logger.error(f"Failed to get file metadata: {e}")
            raise FileOpsError(f"Failed to get file metadata: {e}")


def generate_presigned_url(
    user_id: str, file_path: str, expiry_seconds: int = PRESIGNED_URL_EXPIRY
) -> Dict[str, Any]:
    """
    Generate pre-signed URL for file sharing.

    Args:
        user_id: Cognito user ID
        file_path: File path within user's storage
        expiry_seconds: URL expiry time in seconds (max 1 hour)

    Returns:
        Pre-signed URL dict
    """
    logger.info(f"Generating presigned URL for user {user_id}: {file_path}")

    if not FILES_BUCKET_NAME:
        raise FileOpsError("File storage bucket not configured")

    # Enforce maximum expiry
    if expiry_seconds > PRESIGNED_URL_EXPIRY:
        expiry_seconds = PRESIGNED_URL_EXPIRY

    # Validate and get full S3 key
    s3_key = validate_file_path(user_id, file_path)

    try:
        # Generate presigned URL
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": FILES_BUCKET_NAME, "Key": s3_key},
            ExpiresIn=expiry_seconds,
        )

        result = {
            "file_path": file_path,
            "presigned_url": url,
            "expires_at": (datetime.now() + timedelta(seconds=expiry_seconds)).isoformat(),
            "expiry_seconds": expiry_seconds,
        }

        # Log to audit table
        log_file_action(user_id, "generate_presigned_url", {"file_path": file_path})

        return result

    except ClientError as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        raise FileOpsError(f"Failed to generate presigned URL: {e}")


def log_file_action(user_id: str, action: str, details: Dict[str, Any]) -> None:
    """
    Log file operation to audit table.

    Args:
        user_id: Cognito user ID
        action: Action name
        details: Action details dict
    """
    if not AUDIT_TABLE_NAME:
        logger.warning("Audit table not configured, skipping audit log")
        return

    try:
        table = dynamodb.Table(AUDIT_TABLE_NAME)
        table.put_item(
            Item={
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
                "skill": "file_ops",
                "action": action,
                "details": json.dumps(details),
            }
        )
        logger.info(f"Logged file operation: {action} for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to log file operation: {e}")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    File operations skill Lambda handler.

    Event format:
    {
        "user_id": "cognito-user-id",
        "action": "upload" | "download" | "list" | "delete" | "metadata" | "presigned_url",
        "parameters": {
            # Action-specific parameters
        }
    }

    Returns:
        {
            "statusCode": 200,
            "body": {
                "result": <action result>
            }
        }
    """
    logger.info("File operations skill invoked", extra={"event": event})

    try:
        # Extract user context
        user_id = event.get("user_id")
        if not user_id:
            raise FileOpsError("Missing user_id in request")

        # Extract action
        action = event.get("action")
        if not action:
            raise FileOpsError("Missing action in request")

        # Extract parameters
        params = event.get("parameters", {})

        # Route to appropriate handler
        if action == "upload":
            result = upload_file(
                user_id=user_id,
                file_path=params.get("file_path", ""),
                content=params.get("content", b""),
                content_type=params.get("content_type"),
                metadata=params.get("metadata"),
            )
        elif action == "download":
            result = download_file(
                user_id=user_id,
                file_path=params.get("file_path", ""),
            )
        elif action == "list":
            result = list_files(
                user_id=user_id,
                prefix=params.get("prefix", ""),
                limit=params.get("limit", 100),
            )
        elif action == "delete":
            result = delete_file(
                user_id=user_id,
                file_path=params.get("file_path", ""),
            )
        elif action == "metadata":
            result = get_file_metadata(
                user_id=user_id,
                file_path=params.get("file_path", ""),
            )
        elif action == "presigned_url":
            result = generate_presigned_url(
                user_id=user_id,
                file_path=params.get("file_path", ""),
                expiry_seconds=params.get("expiry_seconds", PRESIGNED_URL_EXPIRY),
            )
        else:
            raise FileOpsError(f"Unknown action: {action}")

        return {
            "statusCode": 200,
            "body": {"result": result, "skill": "file_ops", "action": action},
        }

    except FileOpsError as e:
        logger.error(f"File operations error: {e}")
        return {
            "statusCode": 400,
            "body": {"error": str(e), "skill": "file_ops"},
        }
    except Exception as e:
        logger.exception(f"Unexpected error in file operations skill: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Internal server error", "skill": "file_ops"},
        }

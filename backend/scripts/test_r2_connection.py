"""
Standalone R2 connection test.
Run with: python scripts/test_r2_connection.py
Confirms upload, list, and delete work before touching FastAPI.
"""

import asyncio
import os
import sys

import aioboto3
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

REQUIRED = [
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
    "R2_ENDPOINT_URL",
]


def check_config() -> None:
    missing = [k for k in REQUIRED if not os.getenv(k)]
    if missing:
        print(f"[ERROR] Missing env vars: {', '.join(missing)}")
        sys.exit(1)


async def run_test() -> None:
    check_config()

    session = aioboto3.Session(
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        region_name=os.getenv("R2_REGION", "auto"),
    )

    bucket = os.getenv("R2_BUCKET_NAME")
    test_key = "test/r2_connection_check.txt"
    test_content = b"R2 connection test - safe to delete"

    async with session.client("s3", endpoint_url=os.getenv("R2_ENDPOINT_URL")) as s3:
        # 1. Upload
        print(f"[1/3] Uploading test file to {bucket}/{test_key} ...")
        await s3.put_object(Bucket=bucket, Key=test_key, Body=test_content)
        print("      OK")

        # 2. List — confirm file appears
        print("[2/3] Listing objects with prefix 'test/' ...")
        response = await s3.list_objects_v2(Bucket=bucket, Prefix="test/")
        keys = [obj["Key"] for obj in response.get("Contents", [])]
        assert test_key in keys, f"Expected {test_key} in listing but got: {keys}"
        print(f"      OK — found: {keys}")

        # 3. Delete
        print("[3/3] Deleting test file ...")
        await s3.delete_object(Bucket=bucket, Key=test_key)
        print("      OK")

    print("\nR2 connection test passed.")


if __name__ == "__main__":
    asyncio.run(run_test())

# scripts/test_reply_to.py
import sys

sys.path.insert(0, "/app")

import asyncio

from app.core.email import get_email_service


async def main():
    service = get_email_service()
    await service.send_role_notification(
        candidate_email="nnabugwuemmanuel675@gmail.com",
        employer_name="Test Employer Co",
        job_title="Test Role",
        job_url="https://example.com/jobs/test",
        register_url="https://example.com/register?role=candidate&email=test%40example.com",
        employer_email="emmanuelonyekachi04122000@gmail.com",
    )


asyncio.run(main())

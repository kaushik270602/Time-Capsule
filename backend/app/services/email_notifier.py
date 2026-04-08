"""
Email notification service for TimeLock.

Uses Resend HTTP API for reliable email delivery.
Falls back to SMTP if RESEND_API_KEY is not set.
"""

import logging
import httpx
from app.config import settings
from app.models.capsule import Capsule
from app.models.user import User

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


class EmailNotifier:
    """Handles email notifications via Resend HTTP API."""

    def __init__(self):
        # Use SMTP_PASSWORD as the Resend API key (it's the same value: re_xxx)
        self.api_key = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM or "onboarding@resend.dev"
        self.max_retries = 3

    def send_email(self, user: User, capsule: Capsule) -> bool:
        if not self.api_key:
            logger.warning("Resend API key not configured, skipping email")
            return False

        for attempt in range(1, self.max_retries + 1):
            try:
                success = self._send_via_resend(user, capsule)
                if success:
                    logger.info(f"Email sent to {user.email} for capsule {capsule.id}")
                    return True
                logger.warning(f"Email attempt {attempt} failed for capsule {capsule.id}")
            except Exception as e:
                logger.error(f"Email attempt {attempt} error: {e}")
                if attempt == self.max_retries:
                    return False
        return False

    def _send_via_resend(self, user: User, capsule: Capsule) -> bool:
        html_body = self._create_html_body(user, capsule)
        text_body = self._create_text_body(user, capsule)

        payload = {
            "from": self.from_email,
            "to": [user.email],
            "subject": f"Your TimeLock capsule '{capsule.title}' has unlocked!",
            "html": html_body,
            "text": text_body,
        }

        try:
            resp = httpx.post(
                RESEND_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )

            if resp.status_code in (200, 201):
                logger.info(f"Resend API success: {resp.json()}")
                return True
            else:
                logger.error(f"Resend API error {resp.status_code}: {resp.text}")
                return False

        except httpx.TimeoutException:
            logger.error("Resend API request timed out")
            return False
        except Exception as e:
            logger.error(f"Resend API unexpected error: {e}")
            return False

    def _format_unlock_date(self, capsule: Capsule) -> str:
        try:
            from app.services.timezone_service import TimezoneService
            tz_str = capsule.timezone or "UTC"
            local_dt = TimezoneService.convert_from_utc(capsule.unlock_date, tz_str)
            abbrev = TimezoneService.get_timezone_abbreviation(local_dt, tz_str)
            return local_dt.strftime("%B %d, %Y at %I:%M %p") + f" {abbrev}"
        except Exception:
            return capsule.unlock_date.strftime("%B %d, %Y at %I:%M %p UTC")

    def _create_text_body(self, user: User, capsule: Capsule) -> str:
        capsule_link = f"https://frontend-production-b78fd.up.railway.app/capsules/{capsule.id}"
        unlock_date_str = self._format_unlock_date(capsule)
        return f"""Hello!

Your TimeLock capsule has unlocked!

Capsule: {capsule.title}
Unlock Date: {unlock_date_str}

View your capsule here: {capsule_link}

Best regards,
The TimeLock Team
"""

    def _create_html_body(self, user: User, capsule: Capsule) -> str:
        capsule_link = f"https://frontend-production-b78fd.up.railway.app/capsules/{capsule.id}"
        unlock_date_str = self._format_unlock_date(capsule)
        return f"""<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #f59e0b; color: white; padding: 30px 20px; text-align: center; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; font-size: 24px;">🎉 Your Capsule Has Unlocked!</h1>
        </div>
        <div style="background-color: #fafaf9; padding: 30px; border-radius: 0 0 8px 8px; border: 1px solid #e7e5e4; border-top: none;">
            <p style="margin-top: 0;">Hello!</p>
            <p>Great news! Your TimeLock capsule has unlocked and is now ready to view.</p>
            <div style="background-color: white; padding: 20px; margin: 20px 0; border-radius: 8px; border-left: 4px solid #f59e0b;">
                <h2 style="margin-top: 0; color: #1c1917;">{capsule.title}</h2>
                <p style="margin-bottom: 0;"><strong>Unlock Date:</strong> {unlock_date_str}</p>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{capsule_link}" style="display: inline-block; background-color: #f59e0b; color: #ffffff; padding: 14px 36px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px;">View Your Capsule</a>
            </div>
            <p>Click the button above to view your capsule and see what you preserved for this moment.</p>
            <div style="text-align: center; color: #a8a29e; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e7e5e4;">
                <p>This is an automated notification from TimeLock.</p>
            </div>
        </div>
    </div>
</body>
</html>
"""

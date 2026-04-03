"""
Email notification service for TimeLock.

Sends email notifications when capsules unlock with retry logic.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from app.config import settings
from app.models.capsule import Capsule
from app.models.user import User

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Handles email notifications for capsule unlocks."""
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM or settings.SMTP_USER
        self.max_retries = 3
    
    def send_email(self, user: User, capsule: Capsule) -> bool:
        """
        Sends email notification with capsule details and link.
        
        Args:
            user: User to send notification to
            capsule: Capsule that was unlocked
            
        Returns:
            True if sent successfully, False otherwise
            
        Retries up to 3 times on failure.
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                success = self._send_email_attempt(user, capsule)
                if success:
                    logger.info(f"Email sent successfully to {user.email} for capsule {capsule.id}")
                    return True
                logger.warning(f"Email send attempt {attempt} failed for capsule {capsule.id}")
            except Exception as e:
                logger.error(f"Email send attempt {attempt} failed with error: {e}")
                if attempt == self.max_retries:
                    logger.error(f"All {self.max_retries} email attempts failed for capsule {capsule.id}")
                    return False
        
        return False
    
    def _send_email_attempt(self, user: User, capsule: Capsule) -> bool:
        """
        Single attempt to send email.
        
        Args:
            user: User to send notification to
            capsule: Capsule that was unlocked
            
        Returns:
            True if sent successfully, False otherwise
        """
        # If SMTP is not configured, log and return False
        if not self.smtp_host or not self.smtp_user or not self.smtp_password:
            logger.warning("SMTP not configured, skipping email send")
            return False
        
        try:
            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Your TimeLock capsule '{capsule.title}' has unlocked!"
            msg['From'] = self.from_email
            msg['To'] = user.email
            
            # Create email body
            text_body = self._create_text_body(user, capsule)
            html_body = self._create_html_body(user, capsule)
            
            # Attach both plain text and HTML versions
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            return True
            
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return False
    
    def _format_unlock_date(self, capsule: Capsule) -> str:
        """Format unlock date in the capsule's stored timezone."""
        try:
            from app.services.timezone_service import TimezoneService
            tz_str = capsule.timezone or "UTC"
            local_dt = TimezoneService.convert_from_utc(capsule.unlock_date, tz_str)
            abbrev = TimezoneService.get_timezone_abbreviation(local_dt, tz_str)
            return local_dt.strftime("%B %d, %Y at %I:%M %p") + f" {abbrev}"
        except Exception:
            return capsule.unlock_date.strftime("%B %d, %Y at %I:%M %p UTC")

    def _create_text_body(self, user: User, capsule: Capsule) -> str:
        capsule_link = f"https://timelock.app/capsules/{capsule.id}"
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
        """
        Creates HTML email body.
        
        Args:
            user: User receiving the email
            capsule: Capsule that was unlocked
            
        Returns:
            HTML email body
        """
        capsule_link = f"https://timelock.app/capsules/{capsule.id}"
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

"""
app/email.py

Email sending service using Resend SDK.
https://resend.com/docs/send-with-python

One function: send_verification_email()
All email logic lives here — router stays clean.
"""
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)


def send_verification_email(to_email: str, token: str) -> None:
    """
    Send an account verification email to the user.

    Uses Resend SDK. If RESEND_API_KEY is not configured (e.g. local dev),
    the verification link is logged to the console instead of being sent.

    Args:
        to_email: The recipient's email address.
        token:    The secure verification token stored in the DB.
    """
    settings = get_settings()
    verify_url = f"{settings.app_base_url}/verify-email?token={token}"

    if not settings.resend_api_key:
        # No API key configured — print link so dev can verify manually
        logger.warning(
            f"[email] RESEND_API_KEY not set. Verification link for {to_email}:\n{verify_url}"
        )
        return

    try:
        import resend

        resend.api_key = settings.resend_api_key

        sender = f"{settings.resend_from_name} <{settings.resend_from_email}>" if settings.resend_from_name else settings.resend_from_email

        resend.Emails.send({
            "from": sender,
            "to": [to_email],
            "subject": "Verify your Praxis account",
            "html": _build_email_html(verify_url),
        })
        logger.info(f"[email] Verification email sent to {to_email}")

    except Exception as exc:
        # Never crash registration because the email failed —
        # user can request a resend later (future feature).
        logger.error(f"[email] Failed to send verification email to {to_email}: {exc}")


def _build_email_html(verify_url: str) -> str:
    """Load the HTML template from app/templates/verify_email.html and inject the verify_url."""
    from pathlib import Path

    template_path = Path(__file__).parent / "templates" / "verify_email.html"
    try:
        html_content = template_path.read_text(encoding="utf-8")
        return html_content.replace("{{VERIFY_URL}}", verify_url)
    except Exception as exc:
        logger.error(f"[email] Failed to read template {template_path}: {exc}")
        # Inline fallback if template file is missing
        return f'<p>Click to verify: <a href="{verify_url}">Verify Email</a></p>'


def send_password_reset_email(to_email: str, token: str) -> None:
    """
    Send a password reset email with a one-time reset link.
    Link is valid for 30 minutes.
    """
    settings = get_settings()
    reset_url = f"{settings.app_base_url}/reset-password?token={token}"

    if not settings.resend_api_key:
        logger.warning(
            f"[email] RESEND_API_KEY not set. Password reset link for {to_email}:\n{reset_url}"
        )
        return

    try:
        import resend

        resend.api_key = settings.resend_api_key
        sender = (
            f"{settings.resend_from_name} <{settings.resend_from_email}>"
            if settings.resend_from_name
            else settings.resend_from_email
        )
        resend.Emails.send({
            "from": sender,
            "to": [to_email],
            "subject": "Reset your Praxis password",
            "html": _build_reset_email_html(reset_url),
        })
        logger.info(f"[email] Password reset email sent to {to_email}")

    except Exception as exc:
        logger.error(f"[email] Failed to send password reset email to {to_email}: {exc}")


def _build_reset_email_html(reset_url: str) -> str:
    """Load the password reset HTML template and inject the reset_url."""
    from pathlib import Path

    template_path = Path(__file__).parent / "templates" / "reset_password.html"
    try:
        html_content = template_path.read_text(encoding="utf-8")
        return html_content.replace("{{RESET_URL}}", reset_url)
    except Exception as exc:
        logger.error(f"[email] Failed to read reset template {template_path}: {exc}")
        return f'<p>Click to reset your password: <a href="{reset_url}">Reset Password</a></p>'

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

        resend.Emails.send({
            "from": "Praxis AI <onboarding@resend.dev>",
            "to": [to_email],
            "subject": "Verify your Praxis AI account",
            "html": _build_email_html(verify_url),
        })
        logger.info(f"[email] Verification email sent to {to_email}")

    except Exception as exc:
        # Never crash registration because the email failed —
        # user can request a resend later (future feature).
        logger.error(f"[email] Failed to send verification email to {to_email}: {exc}")


def _build_email_html(verify_url: str) -> str:
    """Return the HTML body for the verification email."""
    return f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: 'Inter', Arial, sans-serif; background: #0f172a; color: #e2e8f0; padding: 40px;">
      <div style="max-width: 480px; margin: 0 auto; background: #1e293b; border-radius: 12px; padding: 40px; border: 1px solid #334155;">
        <h1 style="color: #818cf8; font-size: 24px; margin-bottom: 8px;">Welcome to Praxis AI ✨</h1>
        <p style="color: #94a3b8; margin-bottom: 24px;">
          Please verify your email address to activate your account.
        </p>
        <a href="{verify_url}"
           style="display: inline-block; padding: 12px 28px; background: linear-gradient(135deg, #6366f1, #8b5cf6);
                  color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px;">
          Verify Email Address
        </a>
        <p style="color: #64748b; font-size: 13px; margin-top: 28px;">
          This link expires in 24 hours. If you did not create an account, you can safely ignore this email.
        </p>
        <hr style="border: none; border-top: 1px solid #334155; margin: 24px 0;">
        <p style="color: #475569; font-size: 12px;">Praxis AI — Intelligent Research Assistant</p>
      </div>
    </body>
    </html>
    """

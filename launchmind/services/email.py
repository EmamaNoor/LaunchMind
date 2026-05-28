import logging

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from launchmind.utils import retry

logger = logging.getLogger(__name__)


@retry(max_attempts=3, delay=1.0)
def send_email(
    api_key: str,
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
) -> None:
    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=subject,
        html_content=f"<p>{body}</p>",
    )
    sg = SendGridAPIClient(api_key)
    response = sg.send(message)
    logger.info("Email sent to %s (status %s)", to_email, response.status_code)

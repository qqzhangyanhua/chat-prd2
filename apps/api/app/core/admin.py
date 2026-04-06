from collections.abc import Iterable


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_admin_email(email: str, admin_emails: Iterable[str]) -> bool:
    normalized_email = normalize_email(email)
    if not normalized_email:
        return False
    return normalized_email in {normalize_email(admin_email) for admin_email in admin_emails}

from django.core import signing

SALT = "lead-chat"


def make_lead_token(lead_id: int) -> str:
    return signing.dumps({"lead": lead_id}, salt=SALT)


def read_lead_token(token: str, max_age: int = 60 * 60 * 24 * 7):
    """Return the lead id, or None if the token is forged or expired."""
    try:
        return signing.loads(token, salt=SALT, max_age=max_age)["lead"]
    except signing.BadSignature:
        return None
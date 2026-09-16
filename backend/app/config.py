from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "Grievance Desk API"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://app:app@db:5432/grievance"

    # Secrets / Auth
    jwt_secret: str = "CHANGE_ME_super_secret_grievance_jwt"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 720  # 30 days (long-lived refresh-style session)

    # Fernet key (32 url-safe base64 bytes) used to encrypt SMTP/IMAP passwords and Gemini
    # API keys at rest. Generate one with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # If left blank, one is derived from jwt_secret at startup (fine for local dev — set an
    # explicit ENCRYPTION_KEY in production so credentials survive a JWT_SECRET rotation).
    encryption_key: str = ""

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # SMTP (real outbound). Placeholders until configured.
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "no-reply@grievancedesk.local"
    smtp_ssl: bool = True

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    # Platform Super Admin (seeded on boot; oversees organizations, not tickets)
    superadmin_email: str = "superadmin@grievancedesk.platform"
    superadmin_password: str = "ChangeMe_SuperAdmin_2026!"
    superadmin_name: str = "Platform Super Admin"

    # Background jobs
    imap_poll_interval_seconds: int = 60
    sla_check_interval_seconds: int = 120

    # Public base URL of the deployed frontend SPA — used to build deep links in
    # notification emails (e.g. a resolver's "Open Ticket" link).
    frontend_url: str = "http://localhost:5173"

    # Public, unauthenticated ticket-tracking page — used for the "Track This Ticket" button in
    # customer-facing emails (thank-you, assignment, resolved, escalation). Deliberately separate
    # from `frontend_url`: customers aren't logged in, so they must land on /track (where they
    # enter their Ticket ID + contact) rather than the authenticated ?ticket= deep link used for
    # resolver/authority/admin emails.
    public_tracker_url: str = "https://grievance.fillipsoftware.com/track"

    # WhatsApp Business Cloud API (Meta). Platform-wide fallback; organizations can also
    # configure their own in Org Settings, which overrides this. Empty => outbound WhatsApp
    # sends are skipped (inbound intake still works; the customer just isn't messaged back).
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    # App Secret used to verify Meta's X-Hub-Signature-256 on inbound webhook posts. Strongly
    # recommended once a real WhatsApp Business number is connected — without it, anyone who
    # learns the webhook URL can inject fake complaints into the pipeline.
    whatsapp_app_secret: str = ""
    whatsapp_api_version: str = "v20.0"

    # SMS (generic HTTP gateway). Platform-wide fallback; organizations can also configure
    # their own in Org Settings → Channels → SMS, which overrides this. Empty => outbound SMS
    # sends are skipped, same graceful no-op as unconfigured SMTP/WhatsApp.
    sms_provider: str = ""
    sms_api_url: str = ""
    sms_api_key: str = ""
    sms_sender_id: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_username and self.smtp_password)


@lru_cache
def get_settings() -> Settings:
    return Settings()



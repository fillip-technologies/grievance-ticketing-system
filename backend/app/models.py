import secrets
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .crypto import decrypt, encrypt
from .database import Base


class EncryptedString(TypeDecorator):
    """Transparently encrypts a string column at write time and decrypts at read time.
    Used for SMTP/IMAP passwords and Gemini API keys — see app/crypto.py."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if not value:
            return value
        return encrypt(value)

    def process_result_value(self, value, dialect):
        if not value:
            return value
        return decrypt(value)


def gen_uuid() -> str:
    return str(uuid.uuid4())


def gen_api_key() -> str:
    return "gd_" + secrets.token_urlsafe(24)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    webhook_api_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=gen_api_key)
    status: Mapped[str] = mapped_column(String(32), default="Active")  # Active | Suspended
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list["User"]] = relationship(back_populates="org", cascade="all, delete-orphan")
    mailboxes: Mapped[list["Mailbox"]] = relationship(back_populates="org", cascade="all, delete-orphan")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="org", cascade="all, delete-orphan")
    sections: Mapped[list["Section"]] = relationship(back_populates="org", cascade="all, delete-orphan")
    settings: Mapped["OrganizationSettings | None"] = relationship(
        back_populates="org", cascade="all, delete-orphan", uselist=False
    )


class Section(Base):
    """Admin-defined routing section (e.g. "Sales", "HR") beyond the built-in Support/Enquiry
    category. A message the classifier matches to a section auto-assigns (round robin) to
    whichever active Resolver(s) have this section as their `User.section_id` — regardless of
    the org's general `auto_assign_resolver` toggle, since section routing is opt-in by design
    (an org only sees this behavior once it actually creates a section and staffs it).
    Sections do not affect SLA hours — that still comes from Ticket.category (Support/Enquiry).
    """

    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_section_org_name"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    # Free-text scope description (e.g. "Salary, leave, onboarding, workplace complaints") fed
    # to the AI classifier so it can tell this section apart from others — see
    # gemini_service._run_classification's dynamic section-matching prompt.
    description: Mapped[str] = mapped_column(String(500), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Round-robin cursor scoped to this section, mirroring
    # OrganizationSettings.last_assigned_resolver_id for the general pool.
    last_assigned_resolver_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    org: Mapped["Organization"] = relationship(back_populates="sections")
    resolvers: Mapped[list["User"]] = relationship(back_populates="section")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="section")


class OrganizationSettings(Base):
    __tablename__ = "organization_settings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, index=True)

    ticket_prefix: Mapped[str] = mapped_column(String(32), default="TKT-2026-")
    next_ticket_seq: Mapped[int] = mapped_column(Integer, default=1001)

    auto_send_receipt: Mapped[bool] = mapped_column(Boolean, default=True)
    # Off by default — new tickets (any intake channel, unless routed to a Department with its
    # own resolver pool — see Department below) are left unassigned for the OrgAdmin to assign
    # manually. Turn on in Org Settings to restore blind round-robin assignment instead.
    auto_assign_resolver: Mapped[bool] = mapped_column(Boolean, default=False)
    # Display name shown as the email "From" name, and in WhatsApp/SMS message text, instead
    # of a hardcoded platform brand. Falls back to Organization.name when blank — see
    # ticket_service.resolve_brand_name.
    sender_display_name: Mapped[str] = mapped_column(String(255), default="")
    support_sla_hours: Mapped[int] = mapped_column(Integer, default=48)
    enquiry_sla_hours: Mapped[int] = mapped_column(Integer, default=6)
    # If an Escalated ticket is still unresolved this many hours after its last escalation,
    # the SLA sentinel bumps it to the next EscalationAuthority tier (if one is configured).
    re_escalation_hours: Mapped[int] = mapped_column(Integer, default=4)
    # A Resolved ticket with no customer reply auto-closes this many days after resolved_at —
    # see ticket_service.auto_close_unconfirmed_resolved_tickets.
    auto_close_after_days: Mapped[int] = mapped_column(Integer, default=3)

    # Business-hours SLA calendar. When disabled (default), SLA due dates are plain wall-clock
    # (current behavior — unaffected). When enabled, due dates only accumulate hours during the
    # configured business days/window in `timezone`, skipping weekends and holiday_dates.
    business_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    business_start_hour: Mapped[int] = mapped_column(Integer, default=9)   # 0-23, local time
    business_end_hour: Mapped[int] = mapped_column(Integer, default=18)   # 0-23, local time
    business_days: Mapped[str] = mapped_column(String(32), default="1,2,3,4,5")  # ISO weekday, Mon=1..Sun=7
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")  # IANA tz name, e.g. Asia/Kolkata
    holiday_dates: Mapped[str] = mapped_column(String(2000), default="")  # comma-separated YYYY-MM-DD

    # Org-level Gemini override; falls back to platform GEMINI_API_KEY env var when empty.
    # Encrypted at rest (see EncryptedString / app/crypto.py) — widened to fit ciphertext overhead.
    gemini_api_key: Mapped[str] = mapped_column(EncryptedString(500), default="")

    smtp_host: Mapped[str] = mapped_column(String(255), default="")
    smtp_port: Mapped[int] = mapped_column(Integer, default=465)
    smtp_username: Mapped[str] = mapped_column(String(255), default="")
    smtp_password: Mapped[str] = mapped_column(EncryptedString(500), default="")
    smtp_from_email: Mapped[str] = mapped_column(String(255), default="")

    # WhatsApp Business Cloud API (Meta) — org-level override; falls back to the platform
    # WHATSAPP_* env vars when empty. Used to send the registered/resolved/escalated
    # notifications back to WhatsApp complainants, mirroring the email lifecycle.
    whatsapp_access_token: Mapped[str] = mapped_column(EncryptedString(1000), default="")
    whatsapp_phone_number_id: Mapped[str] = mapped_column(String(64), default="")
    whatsapp_app_secret: Mapped[str] = mapped_column(EncryptedString(500), default="")

    # SMS (generic HTTP API) — org-level override; falls back to the platform SMS_* env vars
    # when empty. Same lifecycle as WhatsApp (ack + resolution texts to customer_mobile), just
    # over a plain SMS gateway instead of Meta's Cloud API. `sms_api_url` is deliberately a
    # free-text endpoint (not a fixed integration) since the actual provider isn't picked yet —
    # this is wired up and skips sending gracefully until a real endpoint/key are configured.
    sms_provider: Mapped[str] = mapped_column(String(64), default="")
    sms_api_url: Mapped[str] = mapped_column(String(500), default="")
    sms_api_key: Mapped[str] = mapped_column(EncryptedString(500), default="")
    sms_sender_id: Mapped[str] = mapped_column(String(64), default="")

    # Round-robin cursor: id of the last User (Resolver) a ticket was assigned to.
    last_assigned_resolver_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    org: Mapped["Organization"] = relationship(back_populates="settings")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    org_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    mobile: Mapped[str] = mapped_column(String(32), default="")
    # SuperAdmin (platform, org_id is null) | OrgAdmin | Resolver | EscalationAuthority
    role: Mapped[str] = mapped_column(String(32), default="OrgAdmin")
    # Escalation tier this user sits at (only meaningful for role=EscalationAuthority).
    # 1 = first-line escalation, 2 = next tier up, etc. — lets an org build a ladder.
    escalation_level: Mapped[int] = mapped_column(Integer, default=1)
    # Section this Resolver is dedicated to (e.g. "Sales"), only meaningful for role=Resolver.
    # NULL = general pool (handles plain Support/Enquiry tickets, not tied to any section).
    # A section-dedicated Resolver is excluded from the general pool — see
    # ticket_service.pick_round_robin_resolver.
    section_id: Mapped[str | None] = mapped_column(
        ForeignKey("sections.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    must_reset_password: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    org: Mapped["Organization | None"] = relationship(back_populates="users")
    section: Mapped["Section | None"] = relationship(back_populates="resolvers")
    assigned_tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="assignee", foreign_keys="Ticket.assigned_to"
    )


class Mailbox(Base):
    __tablename__ = "mailboxes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    email_address: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    server_type: Mapped[str] = mapped_column(String(64), default="Custom IMAP")

    # Inbound (IMAP) — real polling credentials.
    incoming_host: Mapped[str] = mapped_column(String(255), default="")
    port: Mapped[int] = mapped_column(Integer, default=993)
    incoming_username: Mapped[str] = mapped_column(String(255), default="")
    incoming_password: Mapped[str] = mapped_column(EncryptedString(500), default="")
    incoming_use_ssl: Mapped[bool] = mapped_column(Boolean, default=True)

    # Outbound (SMTP) — used for acknowledgement / resolution receipts.
    outgoing_smtp_host: Mapped[str] = mapped_column(String(255), default="")
    outgoing_smtp_port: Mapped[int] = mapped_column(Integer, default=465)
    smtp_use_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    smtp_username: Mapped[str] = mapped_column(String(255), default="")
    smtp_password: Mapped[str] = mapped_column(EncryptedString(500), default="")

    auto_dispatch: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32), default="Connected")  # Connected | Paused | Error
    last_sync_error: Mapped[str] = mapped_column(String(500), default="")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_tickets_ingested: Mapped[int] = mapped_column(Integer, default=0)

    org: Mapped["Organization"] = relationship(back_populates="mailboxes")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="mailbox")
    ingested_emails: Mapped[list["IngestedEmail"]] = relationship(
        back_populates="mailbox", cascade="all, delete-orphan"
    )


class IngestedEmail(Base):
    """Idempotency guard so a poll cycle never double-creates a ticket from the same email."""

    __tablename__ = "ingested_emails"
    __table_args__ = (UniqueConstraint("mailbox_id", "message_id", name="uq_mailbox_message"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    mailbox_id: Mapped[str] = mapped_column(ForeignKey("mailboxes.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str] = mapped_column(String(998), index=True)
    ticket_id: Mapped[str | None] = mapped_column(ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    mailbox: Mapped["Mailbox"] = relationship(back_populates="ingested_emails")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    mailbox_id: Mapped[str | None] = mapped_column(ForeignKey("mailboxes.id", ondelete="SET NULL"), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Admin-defined routing section (e.g. "Sales") the classifier matched this ticket to, if
    # any — drives auto-assignment to that section's Resolver pool. NULL = plain Support/Enquiry,
    # routed by the general auto_assign_resolver toggle instead. See Section in this module.
    section_id: Mapped[str | None] = mapped_column(
        ForeignKey("sections.id", ondelete="SET NULL"), nullable=True, index=True
    )

    customer_name: Mapped[str] = mapped_column(String(255))
    customer_mobile: Mapped[str] = mapped_column(String(32), default="")
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Caller-quoted external reference (e.g. an earlier booking/order number they mention on a
    # help-desk call) — distinct from `id`, which is always our own system-generated ticket number.
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str] = mapped_column(String(500))
    description: Mapped[Text] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32), default="Support")
    status: Mapped[str] = mapped_column(String(32), default="Open")
    priority: Mapped[str] = mapped_column(String(32), default="High")
    channel: Mapped[str] = mapped_column(String(32), default="Portal")
    confidence_score: Mapped[float] = mapped_column(Float, default=0.9)
    sla_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    urgency: Mapped[str] = mapped_column(String(32), default="Medium")
    ai_summary: Mapped[str] = mapped_column(String(500), default="")
    # 0 = never escalated; 1 = first-tier EscalationAuthority; 2 = second tier; etc.
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # When this ticket actually closed — customer-confirmed, auto-closed, or admin-closed.
    # Distinct from resolved_at, which is when a resolver *marked* it Resolved (which may
    # differ if the customer later confirmed/denied or it sat unconfirmed until auto-close).
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # SLA clock pause: while True, the SLA sentinel skips breach/escalation checks on this
    # ticket. On resume, `due_at` is pushed forward by the paused duration so the resolver
    # keeps the SLA time they actually had, instead of losing it while waiting on the customer.
    awaiting_customer: Mapped[bool] = mapped_column(Boolean, default=False)
    awaiting_customer_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set once an 80%-of-SLA-elapsed warning has been sent to the assignee, so it never repeats.
    sla_warning_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    org: Mapped["Organization"] = relationship(back_populates="tickets")
    mailbox: Mapped["Mailbox | None"] = relationship(back_populates="tickets")
    assignee: Mapped["User | None"] = relationship(back_populates="assigned_tickets", foreign_keys=[assigned_to])
    section: Mapped["Section | None"] = relationship(back_populates="tickets")
    replies: Mapped[list["TicketReply"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", order_by="TicketReply.created_at"
    )
    logs: Mapped[list["ActivityLog"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", order_by="ActivityLog.created_at"
    )


class TicketReply(Base):
    __tablename__ = "ticket_replies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    sender: Mapped[str] = mapped_column(String(255))
    is_agent: Mapped[bool] = mapped_column(Boolean, default=True)
    text: Mapped[Text] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ticket: Mapped["Ticket"] = relationship(back_populates="replies")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    actor: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(255))
    details: Mapped[Text] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ticket: Mapped["Ticket"] = relationship(back_populates="logs")


class FailedNotification(Base):
    """Retry queue for a lifecycle email/WhatsApp send that failed for a transient reason
    (network blip, SMTP timeout, Meta API hiccup — see the `retryable` flag returned by
    smtp_service.send_email / whatsapp_service.send_text). Not used for "not configured"
    failures, which won't fix themselves without an admin action. Polled by the scheduler
    (see app/services/notification_retry_service.py) with exponential backoff."""

    __tablename__ = "failed_notifications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    ticket_id: Mapped[str | None] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(16))  # "email" | "whatsapp"
    to_address: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(500), default="")
    body: Mapped[Text] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    last_error: Mapped[str] = mapped_column(String(1000), default="")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)  # True = delivered OR gave up permanently
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

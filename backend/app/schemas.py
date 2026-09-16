from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field

TicketStatus = Literal["Open", "In Progress", "Resolved", "Escalated", "Closed"]
TicketCategory = Literal["Support", "Enquiry"]
TicketChannel = Literal["Email", "WhatsApp", "Portal", "Webhook API", "Phone"]
OrgRole = Literal["OrgAdmin", "Resolver", "EscalationAuthority"]


# ---------- Auth ----------
class OrgRegisterRequest(BaseModel):
    orgName: str = Field(min_length=2, max_length=255)
    adminName: str = Field(min_length=2, max_length=255)
    adminEmail: EmailStr
    adminMobile: str = ""
    adminPassword: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str = Field(min_length=6, max_length=128)


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    mobile: str = ""
    role: str
    isActive: bool = True
    orgId: Optional[str] = None
    orgName: Optional[str] = None
    orgSlug: Optional[str] = None
    createdAt: str


class AuthResponse(BaseModel):
    token: str
    user: UserOut
    temporaryPassword: Optional[str] = None


# ---------- Team ----------
class TeamMemberCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    mobile: str = ""
    role: OrgRole = "Resolver"
    # Escalation ladder tier (only meaningful when role="EscalationAuthority"). 1 = first-line.
    escalationLevel: int = Field(default=1, ge=1, le=10)
    # Section this Resolver is dedicated to (only meaningful when role="Resolver"); null/omitted
    # = general pool. See Section in models.py.
    sectionId: Optional[str] = None


class TeamMemberUpdate(BaseModel):
    isActive: Optional[bool] = None
    role: Optional[OrgRole] = None
    escalationLevel: Optional[int] = Field(default=None, ge=1, le=10)
    # Explicit sentinel needed since None is a valid value ("move back to the general pool") —
    # omitting the field entirely must leave the existing section untouched. See team.py.
    sectionId: Optional[str] = None
    clearSection: bool = False


# ---------- Sections ----------
class SectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)


class SectionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    isActive: Optional[bool] = None


# ---------- Tickets ----------
class TicketStatusUpdate(BaseModel):
    status: TicketStatus


class ReplyCreate(BaseModel):
    text: str = Field(min_length=1)


class ReassignRequest(BaseModel):
    userId: str


class AwaitingCustomerUpdate(BaseModel):
    awaiting: bool


# ---------- Mailboxes ----------
class MailboxCreate(BaseModel):
    emailAddress: EmailStr
    displayName: str
    serverType: str = "Custom IMAP"
    incomingHost: str = ""
    port: int = 993
    incomingUsername: str = ""
    incomingPassword: str = ""
    incomingUseSsl: bool = True
    outgoingSmtpHost: str = ""
    outgoingSmtpPort: int = 465
    smtpUseSsl: bool = True
    smtpUsername: str = ""
    smtpPassword: str = ""
    autoDispatch: bool = True


class MailboxStatusUpdate(BaseModel):
    status: str


# ---------- AI / SMTP ----------
class IntakeRequest(BaseModel):
    message: str
    customerName: Optional[str] = None
    customerMobile: Optional[str] = None
    customerEmail: Optional[str] = None
    channel: TicketChannel = "Portal"


class ManualTicketCreate(BaseModel):
    """Help-desk intake: an admin fills this out on behalf of a caller during a phone call. It
    runs through the exact same classify/assign/SLA pipeline as an emailed complaint."""
    customerName: str = Field(min_length=1, max_length=255)
    customerMobile: str = Field(min_length=1, max_length=32)
    customerEmail: Optional[str] = None
    message: str = Field(min_length=1)
    # Caller-quoted reference to an earlier order/booking/ticket in another system, e.g. "the
    # customer is calling about a refund for their earlier safari booking #RS-4821".
    externalReference: Optional[str] = None
    # When the call actually happened (ISO 8601), for logging it a bit after the fact — the SLA
    # clock starts from this time instead of from form-submission time. Blank/omitted = now.
    occurredAt: Optional[str] = None


class VoiceRequest(BaseModel):
    transcript: str
    currentTab: str = "dashboard"


class SmtpVerifyRequest(BaseModel):
    emailAddress: str
    password: str = ""
    host: str = ""
    port: int = 465
    ssl: bool = True


class SmtpSendRequest(BaseModel):
    toEmail: EmailStr
    customerName: str = ""
    ticketNumber: str = ""
    subject: str = "Receipt"
    body: str = ""
    fromEmail: Optional[str] = None
    host: str = ""
    port: int = 465


class VerifyKeyRequest(BaseModel):
    apiKey: Optional[str] = None


class WhatsAppTestRequest(BaseModel):
    toMobile: str = Field(min_length=6, max_length=32)
    body: str = ""


class SmsTestRequest(BaseModel):
    toMobile: str = Field(min_length=6, max_length=32)
    body: str = ""


# ---------- Public complaint tracking (unauthenticated) ----------
class PublicTrackRequest(BaseModel):
    ticketId: str = Field(min_length=1, max_length=64)
    # Whichever contact detail the complainant gave at intake — email or mobile. Acts as a
    # lightweight shared-secret alongside the ticket ID so ticket IDs (sequential, guessable)
    # alone aren't enough to look up someone else's complaint.
    contact: str = Field(min_length=3, max_length=255)


# ---------- Organization settings ----------
class OrganizationSettingsUpdate(BaseModel):
    ticketPrefix: str = "TKT-2026-"
    autoSendReceipt: bool = True
    autoAssignResolver: bool = False
    senderDisplayName: str = ""
    supportSlaHours: int = Field(default=48, ge=0, le=720)
    enquirySlaHours: int = Field(default=6, ge=0, le=720)
    reEscalationHours: int = Field(default=4, ge=0, le=720)
    autoCloseAfterDays: int = Field(default=3, ge=0, le=90)
    smtpHost: str = ""
    smtpPort: int = 465
    smtpUsername: str = ""
    smtpPassword: str = ""  # blank = keep existing password unchanged
    smtpFromEmail: str = ""
    geminiApiKey: str = ""  # blank = keep existing key unchanged
    clearSmtpPassword: bool = False
    clearGeminiKey: bool = False
    whatsappPhoneNumberId: str = ""
    whatsappAccessToken: str = ""  # blank = keep existing token unchanged
    whatsappAppSecret: str = ""  # blank = keep existing secret unchanged
    clearWhatsappAccessToken: bool = False
    clearWhatsappAppSecret: bool = False
    smsProvider: str = ""
    smsApiUrl: str = ""
    smsSenderId: str = ""
    smsApiKey: str = ""  # blank = keep existing key unchanged
    clearSmsApiKey: bool = False
    businessHoursEnabled: bool = False
    businessStartHour: int = Field(default=9, ge=0, le=23)
    businessEndHour: int = Field(default=18, ge=1, le=24)
    businessDays: str = "1,2,3,4,5"
    timezone: str = "UTC"
    holidayDates: str = ""


# ---------- Intake / WhatsApp response payloads ----------
class ClassificationOut(BaseModel):
    category: str
    confidence_score: float
    subject: Optional[str] = None
    summary: Optional[str] = None
    urgency: Optional[str] = None
    extracted_name: Optional[str] = None
    extracted_mobile: Optional[str] = None
    extracted_email: Optional[str] = None
    note: Optional[str] = None

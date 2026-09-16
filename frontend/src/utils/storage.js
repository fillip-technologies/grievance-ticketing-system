// Client API + session module for the Grievance Desk frontend.
// Talks to the FastAPI backend. Session is a JWT cached in localStorage.

const TOKEN_KEY = 'grievance_desk_token_v4';
const USER_KEY = 'grievance_desk_user_v4';

let cachedUser = null;

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}

export function getCurrentUser() {
  if (cachedUser) return cachedUser;
  try {
    cachedUser = JSON.parse(localStorage.getItem(USER_KEY) || 'null');
  } catch (e) {
    cachedUser = null;
  }
  return cachedUser;
}

export function setSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  cachedUser = user;
}

export function logoutUser() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  cachedUser = null;
}

export async function apiRequest(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(path, {
    ...options,
    headers,
    body: options.body && !(options.body instanceof FormData)
      ? JSON.stringify(options.body)
      : options.body,
  });

  let data = null;
  try {
    data = await res.json();
  } catch (e) {
    // non-JSON response
  }

  if (!res.ok) {
    const detail =
      (data && (data.detail || data.message || data.error)) || `Request failed (${res.status})`;
    const err = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    err.status = res.status;
    throw err;
  }
  return data;
}

// ---------- Auth ----------
export const loginUser = (email, password) =>
  apiRequest('/api/auth/login', { method: 'POST', body: { email, password } });

export const registerOrganization = (data) =>
  apiRequest('/api/organizations/register', { method: 'POST', body: data });

export const changePassword = (currentPassword, newPassword) =>
  apiRequest('/api/auth/change-password', { method: 'POST', body: { currentPassword, newPassword } });

// ---------- Organization (Org Admin) ----------
export const getOrganization = () => apiRequest('/api/organizations/me');
export const saveOrganizationSettings = (body) => apiRequest('/api/organizations/me', { method: 'PUT', body });
export const regenerateWebhookKey = () => apiRequest('/api/organizations/me/regenerate-key', { method: 'POST' });

// ---------- Team (Org Admin) ----------
export const fetchTeam = () => apiRequest('/api/team');
export const createTeamMember = (body) => apiRequest('/api/team', { method: 'POST', body });
export const updateTeamMember = (id, body) =>
  apiRequest(`/api/team/${encodeURIComponent(id)}`, { method: 'PATCH', body });
export const deleteTeamMember = (id) =>
  apiRequest(`/api/team/${encodeURIComponent(id)}`, { method: 'DELETE' });

// ---------- Sections (Org Admin) ----------
export const fetchSections = () => apiRequest('/api/sections');
export const createSection = (body) => apiRequest('/api/sections', { method: 'POST', body });
export const updateSection = (id, body) =>
  apiRequest(`/api/sections/${encodeURIComponent(id)}`, { method: 'PATCH', body });
export const deleteSection = (id) => apiRequest(`/api/sections/${encodeURIComponent(id)}`, { method: 'DELETE' });

// ---------- Super Admin ----------
export const fetchOrganizations = () => apiRequest('/api/superadmin/organizations');
export const updateOrganizationStatus = (id, status) =>
  apiRequest(`/api/superadmin/organizations/${encodeURIComponent(id)}/status`, { method: 'PATCH', body: { status } });

// ---------- Tickets ----------
export const fetchTickets = () => apiRequest('/api/tickets');
export const updateTicketStatus = (id, status) =>
  apiRequest(`/api/tickets/${encodeURIComponent(id)}/status`, { method: 'POST', body: { status } });
export const reassignTicket = (id, userId) =>
  apiRequest(`/api/tickets/${encodeURIComponent(id)}/reassign`, { method: 'POST', body: { userId } });
export const addReply = (id, text) =>
  apiRequest(`/api/tickets/${encodeURIComponent(id)}/replies`, { method: 'POST', body: { text } });
export const setAwaitingCustomer = (id, awaiting) =>
  apiRequest(`/api/tickets/${encodeURIComponent(id)}/awaiting-customer`, { method: 'POST', body: { awaiting } });
export const createManualTicket = (body) => apiRequest('/api/tickets/manual', { method: 'POST', body });

// ---------- Mailboxes ----------
export const fetchMailboxes = () => apiRequest('/api/mailboxes');
export const createMailbox = (body) => apiRequest('/api/mailboxes', { method: 'POST', body });
export const deleteMailbox = (id) => apiRequest(`/api/mailboxes/${encodeURIComponent(id)}`, { method: 'DELETE' });
export const updateMailboxStatus = (id, status) =>
  apiRequest(`/api/mailboxes/${encodeURIComponent(id)}/status`, { method: 'PATCH', body: { status } });
export const testMailboxReceipt = (id) =>
  apiRequest(`/api/mailboxes/${encodeURIComponent(id)}/test-receipt`, { method: 'POST' });
export const syncMailboxNow = (id) =>
  apiRequest(`/api/mailboxes/${encodeURIComponent(id)}/sync-now`, { method: 'POST' });

// ---------- SMTP ----------
export const verifySmtp = (body) => apiRequest('/api/smtp/verify', { method: 'POST', body });
export const sendSmtpReceipt = (body) => apiRequest('/api/smtp/send-receipt', { method: 'POST', body });

// ---------- WhatsApp Business API ----------
export const sendWhatsAppTest = (body) => apiRequest('/api/whatsapp/send-test', { method: 'POST', body });

// ---------- SMS ----------
export const sendSmsTest = (body) => apiRequest('/api/sms/send-test', { method: 'POST', body });

// ---------- AI reply drafting ----------
export const suggestReply = (ticketId) => apiRequest(`/api/tickets/${encodeURIComponent(ticketId)}/suggest-reply`, { method: 'POST' });

// ---------- Public complaint tracking (unauthenticated) ----------
export const trackComplaint = (ticketId, contact) =>
  apiRequest('/api/public/track', { method: 'POST', body: { ticketId, contact } });
export const verifyGeminiKey = (body) => apiRequest('/api/settings/verify-key', { method: 'POST', body });
export const voiceCommand = (body) => apiRequest('/api/ai-voice-command', { method: 'POST', body });

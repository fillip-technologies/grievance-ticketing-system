import React, { useState, useEffect } from 'react';
import {
  Cpu,
  Key,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  RefreshCw,
  ExternalLink,
  Eye,
  EyeOff,
  Database,
  Bot,
  Server,
  Send,
  Copy,
  Link2,
  Mail,
  Gavel,
  FileCode2,
  Clock3,
  ChevronDown,
  ChevronUp,
  Settings as SettingsIcon,
} from 'lucide-react';
import {
  getOrganization,
  saveOrganizationSettings,
  regenerateWebhookKey,
  verifyGeminiKey,
  sendSmtpReceipt,
  getCurrentUser,
} from '../utils/storage';

const DEFAULT_FORM = {
  ticketPrefix: 'TKT-2026-',
  autoSendReceipt: true,
  autoAssignResolver: false,
  senderDisplayName: '',
  supportSlaHours: 48,
  enquirySlaHours: 6,
  reEscalationHours: 4,
  autoCloseAfterDays: 3,
  smtpHost: '',
  smtpPort: 465,
  smtpUsername: '',
  smtpFromEmail: '',
  whatsappPhoneNumberId: '',
  businessHoursEnabled: false,
  businessStartHour: 9,
  businessEndHour: 18,
  businessDays: '1,2,3,4,5',
  timezone: 'UTC',
  holidayDates: '',
};

const WEEKDAY_OPTIONS = [
  { value: 1, label: 'Mon' },
  { value: 2, label: 'Tue' },
  { value: 3, label: 'Wed' },
  { value: 4, label: 'Thu' },
  { value: 5, label: 'Fri' },
  { value: 6, label: 'Sat' },
  { value: 7, label: 'Sun' },
];

// Common timezones as a plain dropdown instead of asking people to type an IANA name.
const COMMON_TIMEZONES = [
  { value: 'UTC', label: 'UTC' },
  { value: 'Asia/Kolkata', label: 'India (Asia/Kolkata)' },
  { value: 'Asia/Dubai', label: 'Dubai (Asia/Dubai)' },
  { value: 'Asia/Singapore', label: 'Singapore (Asia/Singapore)' },
  { value: 'Asia/Shanghai', label: 'China (Asia/Shanghai)' },
  { value: 'Asia/Tokyo', label: 'Japan (Asia/Tokyo)' },
  { value: 'Europe/London', label: 'UK (Europe/London)' },
  { value: 'Europe/Paris', label: 'Central Europe (Europe/Paris)' },
  { value: 'America/New_York', label: 'US Eastern (America/New_York)' },
  { value: 'America/Chicago', label: 'US Central (America/Chicago)' },
  { value: 'America/Denver', label: 'US Mountain (America/Denver)' },
  { value: 'America/Los_Angeles', label: 'US Pacific (America/Los_Angeles)' },
  { value: 'Australia/Sydney', label: 'Australia (Australia/Sydney)' },
];

// Known providers auto-fill their SMTP host/port so most people never see them.
const SMTP_PROVIDER_PRESETS = {
  Gmail: { host: 'smtp.gmail.com', port: 465 },
  Outlook: { host: 'smtp.office365.com', port: 587 },
  Hostinger: { host: 'smtp.hostinger.com', port: 465 },
};

const buildFormAppsScript = (intakeUrl) => `function onFormSubmit(e) {
  // Fires on every new Google Form response. Collects every Q&A pair into one message,
  // best-effort-detects a name/email/phone question, and forwards it to Grievance Desk —
  // which classifies it with AI, generates a Complaint ID, and starts the notify pipeline.
  var responses = e.namedValues; // { "Question text": ["Answer"], ... }
  var lines = [];
  var name = '', email = '', phone = '';

  for (var question in responses) {
    var answer = responses[question].join(', ');
    lines.push(question + ': ' + answer);
    var q = question.toLowerCase();
    if (!email && q.indexOf('email') !== -1) email = answer;
    if (!name && q.indexOf('name') !== -1) name = answer;
    if (!phone && (q.indexOf('phone') !== -1 || q.indexOf('mobile') !== -1 || q.indexOf('contact number') !== -1)) phone = answer;
  }

  var payload = {
    message: lines.join('\\n'),
    customerName: name,
    customerMobile: phone,
    customerEmail: email,
    channel: 'Webhook API'
  };

  UrlFetchApp.fetch('${intakeUrl}', {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });
}`;

export const OrganizationSettings = ({ showToast }) => {
  const currentUser = getCurrentUser();

  const [org, setOrg] = useState(null);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [hasSmtpPassword, setHasSmtpPassword] = useState(false);
  const [hasGeminiKey, setHasGeminiKey] = useState(false);
  const [smtpPasswordInput, setSmtpPasswordInput] = useState('');
  const [showSmtpPassword, setShowSmtpPassword] = useState(false);
  const [geminiKeyInput, setGeminiKeyInput] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  const [isVerifying, setIsVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState(null);

  const [testEmail, setTestEmail] = useState(currentUser?.email || '');
  const [sendingTest, setSendingTest] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const [copiedKey, setCopiedKey] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [copiedScript, setCopiedScript] = useState(false);

  const [smtpProvider, setSmtpProvider] = useState('Gmail');
  const [smtpAdvanced, setSmtpAdvanced] = useState(false);
  const [customTimezone, setCustomTimezone] = useState(false);
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await getOrganization();
      setOrg(data);
      const s = data.settings || {};
      setForm({
        ticketPrefix: s.ticketPrefix || DEFAULT_FORM.ticketPrefix,
        autoSendReceipt: s.autoSendReceipt !== undefined ? s.autoSendReceipt : true,
        autoAssignResolver: s.autoAssignResolver !== undefined ? s.autoAssignResolver : false,
        senderDisplayName: s.senderDisplayName || '',
        supportSlaHours: s.supportSlaHours || 48,
        enquirySlaHours: s.enquirySlaHours || 6,
        reEscalationHours: s.reEscalationHours ?? 4,
        autoCloseAfterDays: s.autoCloseAfterDays ?? 3,
        smtpHost: s.smtpHost || '',
        smtpPort: s.smtpPort || 465,
        smtpUsername: s.smtpUsername || '',
        smtpFromEmail: s.smtpFromEmail || '',
        whatsappPhoneNumberId: s.whatsappPhoneNumberId || '',
        businessHoursEnabled: Boolean(s.businessHoursEnabled),
        businessStartHour: s.businessStartHour ?? 9,
        businessEndHour: s.businessEndHour ?? 18,
        businessDays: s.businessDays || '1,2,3,4,5',
        timezone: s.timezone || 'UTC',
        holidayDates: s.holidayDates || '',
      });
      setHasSmtpPassword(Boolean(s.hasSmtpPassword));
      setHasGeminiKey(Boolean(s.hasGeminiKey));

      const matchedProvider = Object.entries(SMTP_PROVIDER_PRESETS).find(
        ([, preset]) => preset.host === (s.smtpHost || '').toLowerCase()
      )?.[0];
      setSmtpProvider(matchedProvider || 'Other');
      setSmtpAdvanced(!matchedProvider && Boolean(s.smtpHost));
      setCustomTimezone(!COMMON_TIMEZONES.some((tz) => tz.value === (s.timezone || 'UTC')));
    } catch (err) {
      showToast?.(`Failed to load organization settings: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const data = await saveOrganizationSettings({
        ticketPrefix: form.ticketPrefix,
        autoSendReceipt: form.autoSendReceipt,
        autoAssignResolver: form.autoAssignResolver,
        senderDisplayName: form.senderDisplayName,
        supportSlaHours: Number(form.supportSlaHours) || 48,
        enquirySlaHours: Number(form.enquirySlaHours) || 6,
        reEscalationHours: Number(form.reEscalationHours) || 4,
        autoCloseAfterDays: Number(form.autoCloseAfterDays) || 3,
        smtpHost: form.smtpHost,
        smtpPort: Number(form.smtpPort) || 465,
        smtpUsername: form.smtpUsername,
        smtpFromEmail: form.smtpFromEmail,
        smtpPassword: smtpPasswordInput,
        geminiApiKey: geminiKeyInput,
        // WhatsApp is configured on the Channels page — carry the saved value through unchanged.
        whatsappPhoneNumberId: form.whatsappPhoneNumberId,
        whatsappAccessToken: '',
        whatsappAppSecret: '',
        businessHoursEnabled: form.businessHoursEnabled,
        businessStartHour: Number(form.businessStartHour) || 9,
        businessEndHour: Number(form.businessEndHour) || 18,
        businessDays: form.businessDays,
        timezone: form.timezone,
        holidayDates: form.holidayDates,
      });
      setHasSmtpPassword(Boolean(data.settings.hasSmtpPassword));
      setHasGeminiKey(Boolean(data.settings.hasGeminiKey));
      setSmtpPasswordInput('');
      setGeminiKeyInput('');
      setSaved(true);
      showToast?.('Organization settings saved.');
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      showToast?.(`Failed to save: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setIsVerifying(true);
    setVerifyResult(null);
    try {
      const data = await verifyGeminiKey({ apiKey: geminiKeyInput.trim() || undefined });
      setVerifyResult(data);
    } catch (err) {
      setVerifyResult({ success: false, message: err?.message || 'Failed to reach verification endpoint.' });
    } finally {
      setIsVerifying(false);
    }
  };

  const handleSendTestEmail = async () => {
    if (!testEmail.trim()) return;
    setSendingTest(true);
    setTestResult(null);
    try {
      const data = await sendSmtpReceipt({
        toEmail: testEmail.trim(),
        customerName: 'SMTP Test',
        ticketNumber: 'TEST',
        subject: `[Test] ${org?.name || 'Grievance Desk'} SMTP Check`,
        body: 'This is a test email confirming your organization\'s SMTP configuration is working correctly.',
      });
      setTestResult(data);
    } catch (err) {
      setTestResult({ success: false, message: err.message });
    } finally {
      setSendingTest(false);
    }
  };

  const handleSmtpProviderChange = (value) => {
    setSmtpProvider(value);
    const preset = SMTP_PROVIDER_PRESETS[value];
    if (preset) {
      setForm((p) => ({ ...p, smtpHost: preset.host, smtpPort: preset.port }));
      setSmtpAdvanced(false);
    } else {
      setSmtpAdvanced(true);
    }
  };

  const toggleBusinessDay = (day) => {
    setForm((p) => {
      const days = new Set((p.businessDays || '').split(',').map((s) => s.trim()).filter(Boolean));
      const key = String(day);
      if (days.has(key)) days.delete(key); else days.add(key);
      return { ...p, businessDays: Array.from(days).sort().join(',') };
    });
  };

  const handleRegenerateKey = async () => {
    if (!confirm('Regenerating the webhook API key will break any external integrations already using the old key (website form, WhatsApp Business webhook, Zapier). Continue?')) return;
    try {
      const data = await regenerateWebhookKey();
      setOrg((prev) => ({ ...prev, webhookApiKey: data.webhookApiKey }));
      showToast?.('Webhook API key regenerated.');
    } catch (err) {
      showToast?.(`Failed: ${err.message}`);
    }
  };

  const copy = (text, setFlag) => {
    navigator.clipboard.writeText(text);
    setFlag(true);
    setTimeout(() => setFlag(false), 2000);
  };

  if (loading) {
    return <div className="py-16 text-center text-xs text-slate-500">Loading organization settings...</div>;
  }

  const externalIntakeUrl = org ? `${window.location.origin}/api/webhook/external/${org.webhookApiKey}/intake` : '';

  return (
    <div className="space-y-8 animate-in fade-in duration-200">
      {/* SECTION 1: How the pipeline works */}
      <div className="bg-white rounded-2xl border border-slate-200/90 shadow-xs p-6 sm:p-8">
        <div className="flex items-center space-x-3 pb-6 border-b border-slate-100">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-md shadow-indigo-600/20">
            <Cpu className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-extrabold text-slate-900 tracking-tight">How the Complaint Pipeline Works</h2>
            <p className="text-xs text-slate-500 mt-0.5">Every complaint — email, WhatsApp, or webhook — follows this exact flow, automatically.</p>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <div className="w-7 h-7 rounded-lg bg-sky-100 text-sky-700 font-bold text-xs flex items-center justify-center mb-3">01</div>
            <h3 className="text-xs font-bold text-slate-900 mb-1 flex items-center space-x-1.5"><Server className="w-3.5 h-3.5 text-sky-600" /><span>Intake</span></h3>
            <p className="text-[11px] text-slate-600 leading-relaxed">Email arrives via IMAP-polled mailbox, WhatsApp webhook, or your website's webhook API key.</p>
          </div>
          <div className="p-4 rounded-xl bg-indigo-50/50 border border-indigo-200/80">
            <div className="w-7 h-7 rounded-lg bg-indigo-600 text-white font-bold text-xs flex items-center justify-center mb-3">02</div>
            <h3 className="text-xs font-bold text-slate-900 mb-1 flex items-center space-x-1.5"><Bot className="w-3.5 h-3.5 text-indigo-600" /><span>AI Classify + Ack</span></h3>
            <p className="text-[11px] text-slate-600 leading-relaxed">Gemini categorizes Support/Enquiry, a Complaint ID is generated, and an acknowledgement email is sent.</p>
          </div>
          <div className="p-4 rounded-xl bg-amber-50/50 border border-amber-200/80">
            <div className="w-7 h-7 rounded-lg bg-amber-500 text-white font-bold text-xs flex items-center justify-center mb-3">03</div>
            <h3 className="text-xs font-bold text-slate-900 mb-1 flex items-center space-x-1.5"><Database className="w-3.5 h-3.5 text-amber-600" /><span>Round-Robin Assign</span></h3>
            <p className="text-[11px] text-slate-600 leading-relaxed">Auto-assigned to the next available Resolver, who is emailed the full complaint + SLA due time.</p>
          </div>
          <div className="p-4 rounded-xl bg-emerald-50/50 border border-emerald-200/80">
            <div className="w-7 h-7 rounded-lg bg-emerald-600 text-white font-bold text-xs flex items-center justify-center mb-3">04</div>
            <h3 className="text-xs font-bold text-slate-900 mb-1 flex items-center space-x-1.5"><Gavel className="w-3.5 h-3.5 text-emerald-600" /><span>Resolve or Escalate</span></h3>
            <p className="text-[11px] text-slate-600 leading-relaxed">Resolved in time → customer gets a resolution email. Overdue → auto-escalated to your Escalation Authority.</p>
          </div>
        </div>
      </div>

      {/* SECTION 2: Cohesive settings form */}
      <form onSubmit={handleSave} className="bg-white rounded-2xl border border-slate-200/90 shadow-xs p-6 sm:p-8 space-y-8">
        <div className="pb-6 border-b border-slate-100">
          <h2 className="text-lg font-extrabold text-slate-900 tracking-tight">Organization Settings</h2>
          <p className="text-xs text-slate-500 mt-0.5">All settings save together — nothing here is overwritten separately.</p>
        </div>

        {/* Dispatcher settings */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">Ticket ID Prefix</label>
            <input
              type="text"
              value={form.ticketPrefix}
              onChange={(e) => setForm((p) => ({ ...p, ticketPrefix: e.target.value }))}
              className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3.5 py-2.5 text-xs font-mono font-bold text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <p className="text-[11px] text-slate-500 mt-1">Followed by a sequential number, e.g. {form.ticketPrefix}1001.</p>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">Auto-Send Acknowledgement Email</label>
            <div
              onClick={() => setForm((p) => ({ ...p, autoSendReceipt: !p.autoSendReceipt }))}
              className={`w-full p-2.5 rounded-xl border flex items-center justify-between cursor-pointer transition-all ${
                form.autoSendReceipt ? 'bg-emerald-50 border-emerald-300 text-emerald-900 font-bold' : 'bg-slate-50 border-slate-300 text-slate-600'
              }`}
            >
              <div className="flex items-center space-x-2 text-xs">
                <Send className={`w-4 h-4 ${form.autoSendReceipt ? 'text-emerald-600' : 'text-slate-400'}`} />
                <span>{form.autoSendReceipt ? 'On' : 'Off'}</span>
              </div>
              <div className={`w-10 h-5 rounded-full p-0.5 transition-colors ${form.autoSendReceipt ? 'bg-emerald-600' : 'bg-slate-300'}`}>
                <div className={`w-4 h-4 bg-white rounded-full transition-transform ${form.autoSendReceipt ? 'translate-x-5' : 'translate-x-0'}`} />
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">Auto-Assign New Tickets to a Resolver</label>
            <div
              onClick={() => setForm((p) => ({ ...p, autoAssignResolver: !p.autoAssignResolver }))}
              className={`w-full p-2.5 rounded-xl border flex items-center justify-between cursor-pointer transition-all ${
                form.autoAssignResolver ? 'bg-emerald-50 border-emerald-300 text-emerald-900 font-bold' : 'bg-slate-50 border-slate-300 text-slate-600'
              }`}
            >
              <div className="flex items-center space-x-2 text-xs">
                <Database className={`w-4 h-4 ${form.autoAssignResolver ? 'text-emerald-600' : 'text-slate-400'}`} />
                <span>{form.autoAssignResolver ? 'On' : 'Off'}</span>
              </div>
              <div className={`w-10 h-5 rounded-full p-0.5 transition-colors ${form.autoAssignResolver ? 'bg-emerald-600' : 'bg-slate-300'}`}>
                <div className={`w-4 h-4 bg-white rounded-full transition-transform ${form.autoAssignResolver ? 'translate-x-5' : 'translate-x-0'}`} />
              </div>
            </div>
            <p className="text-[11px] text-slate-500 mt-1">
              {form.autoAssignResolver
                ? 'New tickets round-robin to the least-busy active Resolver automatically.'
                : 'New tickets are left unassigned — assign a Resolver manually from the ticket.'}
            </p>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">Response Time Goal (Hours)</label>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <span className="text-[10px] text-slate-500 block">Support</span>
                <input type="number" min="0" value={form.supportSlaHours} onChange={(e) => setForm((p) => ({ ...p, supportSlaHours: e.target.value }))} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              </div>
              <div>
                <span className="text-[10px] text-slate-500 block">Enquiry</span>
                <input type="number" min="0" value={form.enquirySlaHours} onChange={(e) => setForm((p) => ({ ...p, enquirySlaHours: e.target.value }))} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">Re-escalate After (Hours)</label>
            <input type="number" min="0" value={form.reEscalationHours} onChange={(e) => setForm((p) => ({ ...p, reEscalationHours: e.target.value }))} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            <p className="text-[10px] text-slate-500 mt-1">
              If an escalated ticket is still unresolved this long after its last escalation, it climbs to the
              next Escalation Authority tier (when one is configured in Team Management).
            </p>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">Auto-Close After (Days)</label>
            <input type="number" min="0" value={form.autoCloseAfterDays} onChange={(e) => setForm((p) => ({ ...p, autoCloseAfterDays: e.target.value }))} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            <p className="text-[10px] text-slate-500 mt-1">
              A Resolved ticket the customer never replies to is automatically Closed this many days after
              being marked Resolved.
            </p>
          </div>
        </div>

        {/* Business-hours SLA calendar */}
        <div className="pt-6 border-t border-slate-100">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center space-x-2">
              <Clock3 className="w-3.5 h-3.5 text-indigo-600" /><span>Business Hours</span>
            </h3>
            <div
              onClick={() => setForm((p) => ({ ...p, businessHoursEnabled: !p.businessHoursEnabled }))}
              className={`px-3 py-1 rounded-lg border flex items-center space-x-2 cursor-pointer text-xs font-bold transition-all ${
                form.businessHoursEnabled ? 'bg-emerald-50 border-emerald-300 text-emerald-900' : 'bg-slate-50 border-slate-300 text-slate-600'
              }`}
            >
              <span>{form.businessHoursEnabled ? 'On' : 'Off (counts all hours)'}</span>
              <div className={`w-8 h-4 rounded-full p-0.5 transition-colors ${form.businessHoursEnabled ? 'bg-emerald-600' : 'bg-slate-300'}`}>
                <div className={`w-3 h-3 bg-white rounded-full transition-transform ${form.businessHoursEnabled ? 'translate-x-4' : 'translate-x-0'}`} />
              </div>
            </div>
          </div>
          <p className="text-[11px] text-slate-500 mb-3">
            When enabled, SLA due dates only count time during the window below — a complaint filed Friday
            evening won't silently breach over the weekend.
          </p>
          <div className={`grid grid-cols-1 md:grid-cols-4 gap-3 ${form.businessHoursEnabled ? '' : 'opacity-50 pointer-events-none'}`}>
            <div>
              <span className="text-[10px] text-slate-500 block mb-1">Start Hour (0-23, local)</span>
              <input type="number" min="0" max="23" value={form.businessStartHour} onChange={(e) => setForm((p) => ({ ...p, businessStartHour: e.target.value }))} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <div>
              <span className="text-[10px] text-slate-500 block mb-1">End Hour (1-24, local)</span>
              <input type="number" min="1" max="24" value={form.businessEndHour} onChange={(e) => setForm((p) => ({ ...p, businessEndHour: e.target.value }))} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <div className="md:col-span-2">
              <span className="text-[10px] text-slate-500 block mb-1">Timezone</span>
              {customTimezone ? (
                <div className="flex items-center gap-1.5">
                  <input placeholder="Asia/Kolkata" value={form.timezone} onChange={(e) => setForm((p) => ({ ...p, timezone: e.target.value }))} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                  <button type="button" onClick={() => setCustomTimezone(false)} className="text-[10px] text-indigo-600 hover:text-indigo-800 font-semibold whitespace-nowrap cursor-pointer">Pick from list</button>
                </div>
              ) : (
                <select
                  value={form.timezone}
                  onChange={(e) => {
                    if (e.target.value === '__other__') { setCustomTimezone(true); return; }
                    setForm((p) => ({ ...p, timezone: e.target.value }));
                  }}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
                >
                  {COMMON_TIMEZONES.map((tz) => <option key={tz.value} value={tz.value}>{tz.label}</option>)}
                  <option value="__other__">Other (type it in)</option>
                </select>
              )}
            </div>
            <div className="md:col-span-4">
              <span className="text-[10px] text-slate-500 block mb-1">Business Days</span>
              <div className="flex flex-wrap gap-1.5">
                {WEEKDAY_OPTIONS.map((d) => {
                  const active = (form.businessDays || '').split(',').includes(String(d.value));
                  return (
                    <button
                      type="button"
                      key={d.value}
                      onClick={() => toggleBusinessDay(d.value)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-all cursor-pointer ${
                        active ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-50'
                      }`}
                    >
                      {d.label}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="md:col-span-4">
              <span className="text-[10px] text-slate-500 block mb-1">Holiday Dates (comma-separated, YYYY-MM-DD)</span>
              <input placeholder="2026-01-26, 2026-08-15, 2026-10-02" value={form.holidayDates} onChange={(e) => setForm((p) => ({ ...p, holidayDates: e.target.value }))} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              <p className="text-[10px] text-slate-500 mt-1">These dates are fully excluded from SLA counting, even if they fall on a configured business day.</p>
            </div>
          </div>
        </div>

        {/* Email notifications (outgoing SMTP) */}
        <div className="pt-6 border-t border-slate-100">
          <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-1 flex items-center space-x-2">
            <Mail className="w-3.5 h-3.5 text-sky-600" /><span>Email Notifications</span>
          </h3>
          <p className="text-[11px] text-slate-500 mb-3">The email account used to send confirmation, assignment, resolution, and escalation emails.</p>

          <div className="mb-4">
            <label className="block text-[10px] text-slate-500 mb-1">Sender Display Name</label>
            <input
              placeholder={`Leave blank to use "${org?.name || 'your organization'}"`}
              value={form.senderDisplayName}
              onChange={(e) => setForm((p) => ({ ...p, senderDisplayName: e.target.value }))}
              className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              Shown as the "From" name on outgoing emails and in WhatsApp/SMS messages — e.g. "Acme Support Team"
              instead of your organization's registered name.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="sm:col-span-2">
              <label className="block text-[10px] text-slate-500 mb-1">Email Provider</label>
              <select value={smtpProvider} onChange={(e) => handleSmtpProviderChange(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-sky-500 cursor-pointer">
                <option value="Gmail">Gmail</option>
                <option value="Outlook">Outlook / Microsoft 365</option>
                <option value="Hostinger">Hostinger</option>
                <option value="Other">Other / Custom</option>
              </select>
            </div>

            {smtpProvider !== 'Other' && !smtpAdvanced && (
              <button type="button" onClick={() => setSmtpAdvanced(true)} className="sm:col-span-2 text-[11px] font-semibold text-sky-700 hover:text-sky-900 cursor-pointer flex items-center space-x-1 -mt-1">
                <ChevronDown className="w-3.5 h-3.5" /><span>Show advanced server settings</span>
              </button>
            )}

            {(smtpAdvanced || smtpProvider === 'Other') && (
              <>
                {smtpProvider !== 'Other' && (
                  <button type="button" onClick={() => setSmtpAdvanced(false)} className="sm:col-span-2 text-[11px] font-semibold text-slate-500 hover:text-slate-800 cursor-pointer flex items-center space-x-1 -mt-1">
                    <ChevronUp className="w-3.5 h-3.5" /><span>Hide advanced server settings</span>
                  </button>
                )}
                <input placeholder="smtp.hostinger.com" value={form.smtpHost} onChange={(e) => setForm((p) => ({ ...p, smtpHost: e.target.value }))} className="bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-sky-500" />
                <input type="number" placeholder="465" value={form.smtpPort} onChange={(e) => setForm((p) => ({ ...p, smtpPort: e.target.value }))} className="bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-sky-500" />
              </>
            )}

            <input placeholder="Login email / username" value={form.smtpUsername} onChange={(e) => setForm((p) => ({ ...p, smtpUsername: e.target.value }))} className="bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-sky-500" />
            <input placeholder="From address shown to customers" value={form.smtpFromEmail} onChange={(e) => setForm((p) => ({ ...p, smtpFromEmail: e.target.value }))} className="bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-sky-500" />
            <div className="relative sm:col-span-2">
              <input
                type={showSmtpPassword ? 'text' : 'password'}
                placeholder={hasSmtpPassword ? '•••••••• (saved — leave blank to keep)' : 'Password'}
                value={smtpPasswordInput}
                onChange={(e) => setSmtpPasswordInput(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 pr-10 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
              <button
                type="button"
                onClick={() => setShowSmtpPassword((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                {showSmtpPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              </button>
            </div>
            <div className="flex items-center space-x-2 sm:col-span-2">
              <input value={testEmail} onChange={(e) => setTestEmail(e.target.value)} placeholder="Send a test email to..." className="flex-1 bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-sky-500" />
              <button type="button" onClick={handleSendTestEmail} disabled={sendingTest} className="px-3 py-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-60 text-white text-xs font-semibold rounded-xl whitespace-nowrap cursor-pointer">
                {sendingTest ? 'Sending...' : 'Send Test'}
              </button>
            </div>
          </div>
          {testResult && (
            <p className={`mt-2 text-[11px] ${testResult.success ? 'text-emerald-600' : 'text-rose-600'}`}>{testResult.message}</p>
          )}
        </div>

        <div className="flex items-center space-x-3 pt-2">
          <button type="submit" disabled={saving} className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white font-bold text-xs rounded-xl shadow-sm transition-all cursor-pointer flex items-center space-x-1.5">
            <CheckCircle2 className="w-4 h-4" />
            <span>{saving ? 'Saving...' : 'Save Settings'}</span>
          </button>
          {saved && <span className="text-xs font-bold text-emerald-600 animate-in fade-in">✓ Saved successfully!</span>}
        </div>

        {/* Advanced / developer settings — collapsed by default */}
        <div className="pt-6 border-t border-slate-100">
          <button
            type="button"
            onClick={() => setShowAdvancedSettings((v) => !v)}
            className="flex items-center space-x-2 text-xs font-bold text-slate-600 hover:text-slate-900 cursor-pointer"
          >
            <SettingsIcon className="w-3.5 h-3.5" />
            <span>Advanced / Developer Settings</span>
            {showAdvancedSettings ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
          <p className="text-[11px] text-slate-500 mt-1">Only needed if you're using a custom AI key or wiring up your own website/Google Form.</p>

          {showAdvancedSettings && (
            <div className="mt-4 space-y-6">
              {/* Gemini key */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center space-x-2">
                    <Key className="w-3.5 h-3.5 text-amber-600" /><span>Gemini API Key (org override)</span>
                  </h3>
                  {hasGeminiKey ? (
                    <span className="inline-flex items-center space-x-1 px-2 py-0.5 bg-emerald-100 text-emerald-800 border border-emerald-200 rounded-full text-[10px] font-bold">
                      <CheckCircle2 className="w-3 h-3" /><span>Key Saved</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center space-x-1 px-2 py-0.5 bg-indigo-100 text-indigo-800 border border-indigo-200 rounded-full text-[10px] font-bold">
                      <Sparkles className="w-3 h-3" /><span>Using Platform Default Key</span>
                    </span>
                  )}
                </div>
                <div className="relative max-w-xl">
                  <Key className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type={showKey ? 'text' : 'password'}
                    value={geminiKeyInput}
                    onChange={(e) => setGeminiKeyInput(e.target.value)}
                    placeholder={hasGeminiKey ? '•••••••• (saved — leave blank to keep)' : 'AIzaSy...'}
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl pl-9 pr-10 py-2.5 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  <button type="button" onClick={() => setShowKey(!showKey)} className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600">
                    {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <div className="flex flex-wrap items-center gap-3 mt-3">
                  <button type="button" onClick={handleTestConnection} disabled={isVerifying} className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs rounded-xl transition-all cursor-pointer flex items-center space-x-1.5 disabled:opacity-60">
                    <RefreshCw className={`w-3.5 h-3.5 text-amber-300 ${isVerifying ? 'animate-spin' : ''}`} />
                    <span>{isVerifying ? 'Testing...' : 'Test Connection'}</span>
                  </button>
                  <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener noreferrer" className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-xl transition-colors flex items-center space-x-1.5">
                    <span>Get Free Gemini Key</span><ExternalLink className="w-3.5 h-3.5 text-slate-500" />
                  </a>
                </div>
                {verifyResult && (
                  <div className={`mt-4 p-4 rounded-xl border text-xs ${verifyResult.success ? 'bg-emerald-50 border-emerald-200 text-emerald-900' : 'bg-rose-50 border-rose-200 text-rose-900'}`}>
                    <div className="flex items-start space-x-3">
                      {verifyResult.success ? <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" /> : <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0" />}
                      <div>
                        <div className="font-bold text-sm">{verifyResult.success ? 'Connection Successful!' : 'Connection Error'}</div>
                        <p>{verifyResult.message}</p>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Webhook integration */}
              <div className="pt-6 border-t border-slate-100">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center space-x-2">
                    <Link2 className="w-3.5 h-3.5 text-slate-600" /><span>External Webhook Integration</span>
                  </h3>
                  <button type="button" onClick={handleRegenerateKey} className="px-2.5 py-1 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg text-[11px] font-semibold cursor-pointer">
                    Regenerate Key
                  </button>
                </div>
                <p className="text-[11px] text-slate-500 mb-3">Point your website form, Zapier, or Google Forms at this URL. (Looking for WhatsApp? That's under the Channels page.)</p>

                <div className="space-y-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wider mb-1">Webhook API Key</label>
                    <div className="flex items-center space-x-2">
                      <code className="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs font-mono text-slate-800 truncate">{org?.webhookApiKey}</code>
                      <button type="button" onClick={() => copy(org?.webhookApiKey, setCopiedKey)} className="p-2 text-slate-500 hover:text-slate-900 hover:bg-slate-100 rounded-lg cursor-pointer"><Copy className="w-4 h-4" /></button>
                    </div>
                    {copiedKey && <span className="text-[11px] text-emerald-600">Copied!</span>}
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wider mb-1">Generic Intake Webhook (POST)</label>
                    <div className="flex items-center space-x-2">
                      <code className="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs font-mono text-slate-800 truncate">{externalIntakeUrl}</code>
                      <button type="button" onClick={() => copy(externalIntakeUrl, setCopiedUrl)} className="p-2 text-slate-500 hover:text-slate-900 hover:bg-slate-100 rounded-lg cursor-pointer"><Copy className="w-4 h-4" /></button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Google Forms integration */}
              <div className="pt-6 border-t border-slate-100">
                <div className="flex items-center space-x-2 mb-2">
                  <FileCode2 className="w-3.5 h-3.5 text-slate-600" />
                  <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">Google Forms Integration</h3>
                </div>
                <p className="text-[11px] text-slate-500 mb-3">
                  Sends form answers straight to Grievance Desk the moment someone submits, instead of relying on
                  a notification email.
                </p>

                <ol className="text-xs text-slate-600 space-y-1.5 list-decimal list-inside">
                  <li>Open your Google Form's response Sheet (or the Form itself) → <span className="font-semibold">Extensions → Apps Script</span>.</li>
                  <li>Delete any starter code, paste the script below, and save (Ctrl/Cmd+S).</li>
                  <li>Click the clock icon (<span className="font-semibold">Triggers</span>) → <span className="font-semibold">Add Trigger</span> → function <code className="bg-slate-100 px-1 rounded">onFormSubmit</code>, event source <span className="font-semibold">From form</span>, event type <span className="font-semibold">On form submit</span> → Save.</li>
                  <li>Submit a test response — the complaint should appear on your Dashboard within seconds, fully classified with a Complaint ID.</li>
                </ol>

                <div className="relative mt-3">
                  <pre className="bg-slate-950 text-slate-200 text-[11px] leading-relaxed rounded-xl p-4 overflow-x-auto font-mono max-h-80">
{buildFormAppsScript(externalIntakeUrl)}
                  </pre>
                  <button
                    type="button"
                    onClick={() => copy(buildFormAppsScript(externalIntakeUrl), setCopiedScript)}
                    className="absolute top-3 right-3 p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg cursor-pointer"
                    title="Copy script"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                  {copiedScript && <span className="absolute top-3 right-11 text-[11px] text-emerald-400 mt-1">Copied!</span>}
                </div>
              </div>
            </div>
          )}
        </div>
      </form>
    </div>
  );
};

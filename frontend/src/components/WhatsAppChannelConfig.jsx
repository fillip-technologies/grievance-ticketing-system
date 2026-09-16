import React, { useState, useEffect } from 'react';
import {
  MessageSquare,
  CheckCircle2,
  AlertTriangle,
  Eye,
  EyeOff,
  ExternalLink,
  Copy,
  Check,
  Send,
} from 'lucide-react';
import { getOrganization, saveOrganizationSettings, sendWhatsAppTest } from '../utils/storage';

export const WhatsAppChannelConfig = ({ showToast }) => {
  const [loading, setLoading] = useState(true);
  const [orgSettings, setOrgSettings] = useState(null); // full settings object, kept as-is for safe re-submission
  const [webhookApiKey, setWebhookApiKey] = useState('');

  const [phoneNumberId, setPhoneNumberId] = useState('');
  const [hasAccessToken, setHasAccessToken] = useState(false);
  const [hasAppSecret, setHasAppSecret] = useState(false);
  const [accessTokenInput, setAccessTokenInput] = useState('');
  const [appSecretInput, setAppSecretInput] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [showAppSecret, setShowAppSecret] = useState(false);

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [testMobile, setTestMobile] = useState('');
  const [sendingTest, setSendingTest] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [copied, setCopied] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await getOrganization();
      setWebhookApiKey(data.webhookApiKey || '');
      const s = data.settings || {};
      setOrgSettings(s);
      setPhoneNumberId(s.whatsappPhoneNumberId || '');
      setHasAccessToken(Boolean(s.hasWhatsappAccessToken));
      setHasAppSecret(Boolean(s.hasWhatsappAppSecret));
    } catch (err) {
      showToast?.(`Failed to load WhatsApp settings: ${err.message}`);
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
    if (!orgSettings) return;
    setSaving(true);
    try {
      const data = await saveOrganizationSettings({
        // Carry every other org setting through unchanged — the API expects the full form.
        ticketPrefix: orgSettings.ticketPrefix,
        autoSendReceipt: orgSettings.autoSendReceipt,
        supportSlaHours: orgSettings.supportSlaHours,
        enquirySlaHours: orgSettings.enquirySlaHours,
        reEscalationHours: orgSettings.reEscalationHours,
        smtpHost: orgSettings.smtpHost || '',
        smtpPort: orgSettings.smtpPort || 465,
        smtpUsername: orgSettings.smtpUsername || '',
        smtpFromEmail: orgSettings.smtpFromEmail || '',
        smtpPassword: '', // blank = keep existing unchanged
        geminiApiKey: '', // blank = keep existing unchanged
        businessHoursEnabled: orgSettings.businessHoursEnabled,
        businessStartHour: orgSettings.businessStartHour,
        businessEndHour: orgSettings.businessEndHour,
        businessDays: orgSettings.businessDays,
        timezone: orgSettings.timezone,
        holidayDates: orgSettings.holidayDates,
        // The fields this panel actually edits:
        whatsappPhoneNumberId: phoneNumberId.trim(),
        whatsappAccessToken: accessTokenInput,
        whatsappAppSecret: appSecretInput,
      });
      setOrgSettings(data.settings);
      setHasAccessToken(Boolean(data.settings.hasWhatsappAccessToken));
      setHasAppSecret(Boolean(data.settings.hasWhatsappAppSecret));
      setAccessTokenInput('');
      setAppSecretInput('');
      setSaved(true);
      showToast?.('WhatsApp settings saved.');
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      showToast?.(`Failed to save: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleSendTest = async () => {
    if (!testMobile.trim()) return;
    setSendingTest(true);
    setTestResult(null);
    try {
      const data = await sendWhatsAppTest({ toMobile: testMobile.trim() });
      setTestResult(data);
    } catch (err) {
      setTestResult({ success: false, message: err.message });
    } finally {
      setSendingTest(false);
    }
  };

  const copyToken = () => {
    navigator.clipboard.writeText(webhookApiKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return <div className="py-16 text-center text-xs text-slate-500">Loading WhatsApp settings...</div>;
  }

  const webhookUrl = webhookApiKey ? `${window.location.origin}/api/webhook/external/${webhookApiKey}/whatsapp` : '';
  const connected = hasAccessToken;

  return (
    <div className="bg-white rounded-2xl border border-slate-200/90 shadow-xs p-5 sm:p-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-5 border-b border-slate-100">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center">
            <MessageSquare className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900 tracking-tight">WhatsApp</h2>
            <p className="text-xs text-slate-500 mt-0.5">Receive complaints sent to your WhatsApp Business number.</p>
          </div>
        </div>
        {connected ? (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full text-[11px] font-bold self-start sm:self-auto">
            <CheckCircle2 className="w-3.5 h-3.5" /><span>Connected</span>
          </span>
        ) : (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 bg-amber-50 text-amber-700 border border-amber-200 rounded-full text-[11px] font-bold self-start sm:self-auto">
            <AlertTriangle className="w-3.5 h-3.5" /><span>Not connected yet</span>
          </span>
        )}
      </div>

      <form onSubmit={handleSave} className="mt-5 space-y-4">
        <p className="text-xs text-slate-500">
          Get these two values from your WhatsApp Business (Meta Cloud API) account, then paste them here.{' '}
          <a href="https://developers.facebook.com/docs/whatsapp/cloud-api/get-started" target="_blank" rel="noopener noreferrer" className="text-emerald-700 font-semibold hover:text-emerald-900 inline-flex items-center space-x-0.5">
            <span>Where do I find these?</span><ExternalLink className="w-3 h-3" />
          </a>
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Phone Number ID</label>
            <input
              type="text"
              value={phoneNumberId}
              onChange={(e) => setPhoneNumberId(e.target.value)}
              placeholder="e.g. 109876543210"
              className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Access Token</label>
            <div className="relative">
              <input
                type={showToken ? 'text' : 'password'}
                value={accessTokenInput}
                onChange={(e) => setAccessTokenInput(e.target.value)}
                placeholder={hasAccessToken ? '•••••••• (saved — leave blank to keep)' : 'Paste permanent access token'}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 pr-10 py-2 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
              <button type="button" onClick={() => setShowToken(!showToken)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                {showToken ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>

          <div className="sm:col-span-2">
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              App Secret <span className="text-slate-400 font-normal">(optional — confirms messages really come from Meta)</span>
            </label>
            <div className="relative">
              <input
                type={showAppSecret ? 'text' : 'password'}
                value={appSecretInput}
                onChange={(e) => setAppSecretInput(e.target.value)}
                placeholder={hasAppSecret ? '•••••••• (saved — leave blank to keep)' : 'Optional'}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 pr-10 py-2 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
              <button type="button" onClick={() => setShowAppSecret((v) => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                {showAppSecret ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3 pt-1">
          <button type="submit" disabled={saving} className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white font-bold text-xs rounded-xl shadow-xs transition-colors cursor-pointer">
            {saving ? 'Saving...' : 'Save WhatsApp Settings'}
          </button>
          {saved && <span className="text-xs font-bold text-emerald-600">✓ Saved</span>}
        </div>
      </form>

      {/* Where WhatsApp sends messages to us */}
      <div className="mt-6 pt-5 border-t border-slate-100">
        <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Point WhatsApp at this address</h3>
        <p className="text-[11px] text-slate-500 mb-2">
          In Meta's WhatsApp Business console, set this as the Webhook Callback URL and use the same value as the Verify Token.
        </p>
        <div className="flex items-center space-x-2 bg-slate-50 border border-slate-200 rounded-xl p-2.5">
          <code className="flex-1 text-xs font-mono text-slate-800 truncate">{webhookUrl || 'Loading...'}</code>
          <button type="button" onClick={copyToken} disabled={!webhookApiKey} className="p-1.5 text-slate-500 hover:text-slate-900 hover:bg-white rounded-lg cursor-pointer disabled:opacity-40" title="Copy webhook URL">
            {copied ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Test send */}
      <div className="mt-6 pt-5 border-t border-slate-100">
        <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Send a Test Message</h3>
        <div className="flex items-center space-x-2">
          <input
            value={testMobile}
            onChange={(e) => setTestMobile(e.target.value)}
            placeholder="+91XXXXXXXXXX"
            className="flex-1 bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
          <button type="button" onClick={handleSendTest} disabled={sendingTest || !connected} className="px-4 py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-40 text-white text-xs font-semibold rounded-xl flex items-center space-x-1.5 whitespace-nowrap cursor-pointer">
            <Send className="w-3.5 h-3.5" />
            <span>{sendingTest ? 'Sending...' : 'Send Test'}</span>
          </button>
        </div>
        {!connected && <p className="text-[11px] text-slate-400 mt-1.5">Save your Phone Number ID and Access Token above first.</p>}
        {testResult && (
          <p className={`mt-2 text-[11px] ${testResult.success ? 'text-emerald-600' : 'text-rose-600'}`}>{testResult.message}</p>
        )}
      </div>
    </div>
  );
};

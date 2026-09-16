import React, { useState, useEffect } from 'react';
import {
  Smartphone,
  CheckCircle2,
  AlertTriangle,
  Eye,
  EyeOff,
  Send,
} from 'lucide-react';
import { getOrganization, saveOrganizationSettings, sendSmsTest } from '../utils/storage';

export const SmsChannelConfig = ({ showToast }) => {
  const [loading, setLoading] = useState(true);
  const [orgSettings, setOrgSettings] = useState(null); // full settings object, kept as-is for safe re-submission

  const [provider, setProvider] = useState('');
  const [apiUrl, setApiUrl] = useState('');
  const [senderId, setSenderId] = useState('');
  const [hasApiKey, setHasApiKey] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [showKey, setShowKey] = useState(false);

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [testMobile, setTestMobile] = useState('');
  const [sendingTest, setSendingTest] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await getOrganization();
      const s = data.settings || {};
      setOrgSettings(s);
      setProvider(s.smsProvider || '');
      setApiUrl(s.smsApiUrl || '');
      setSenderId(s.smsSenderId || '');
      setHasApiKey(Boolean(s.hasSmsApiKey));
    } catch (err) {
      showToast?.(`Failed to load SMS settings: ${err.message}`);
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
        whatsappPhoneNumberId: orgSettings.whatsappPhoneNumberId || '',
        whatsappAccessToken: '', // blank = keep existing unchanged
        whatsappAppSecret: '', // blank = keep existing unchanged
        businessHoursEnabled: orgSettings.businessHoursEnabled,
        businessStartHour: orgSettings.businessStartHour,
        businessEndHour: orgSettings.businessEndHour,
        businessDays: orgSettings.businessDays,
        timezone: orgSettings.timezone,
        holidayDates: orgSettings.holidayDates,
        // The fields this panel actually edits:
        smsProvider: provider.trim(),
        smsApiUrl: apiUrl.trim(),
        smsSenderId: senderId.trim(),
        smsApiKey: apiKeyInput,
      });
      setOrgSettings(data.settings);
      setHasApiKey(Boolean(data.settings.hasSmsApiKey));
      setApiKeyInput('');
      setSaved(true);
      showToast?.('SMS settings saved.');
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
      const data = await sendSmsTest({ toMobile: testMobile.trim() });
      setTestResult(data);
    } catch (err) {
      setTestResult({ success: false, message: err.message });
    } finally {
      setSendingTest(false);
    }
  };

  if (loading) {
    return <div className="py-16 text-center text-xs text-slate-500">Loading SMS settings...</div>;
  }

  const connected = hasApiKey && Boolean(apiUrl) && Boolean(senderId);

  return (
    <div className="bg-white rounded-2xl border border-slate-200/90 shadow-xs p-5 sm:p-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-5 border-b border-slate-100">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center">
            <Smartphone className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900 tracking-tight">SMS</h2>
            <p className="text-xs text-slate-500 mt-0.5">Send acknowledgement and resolution texts to the complainant's phone number.</p>
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
          No SMS provider is wired up yet — fill these in once you have one (Twilio, MSG91, or any gateway with a
          JSON HTTP API). Until then, SMS sends are skipped, same as an unconfigured email/WhatsApp channel.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Provider Name <span className="text-slate-400 font-normal">(optional label)</span></label>
            <input
              type="text"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              placeholder="e.g. Twilio, MSG91"
              className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Sender ID / From Number</label>
            <input
              type="text"
              value={senderId}
              onChange={(e) => setSenderId(e.target.value)}
              placeholder="e.g. GRVDSK or +1XXXXXXXXXX"
              className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div className="sm:col-span-2">
            <label className="block text-xs font-semibold text-slate-700 mb-1">API Endpoint URL</label>
            <input
              type="text"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder="https://your-sms-gateway.example.com/send"
              className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div className="sm:col-span-2">
            <label className="block text-xs font-semibold text-slate-700 mb-1">API Key</label>
            <div className="relative">
              <input
                type={showKey ? 'text' : 'password'}
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                placeholder={hasApiKey ? '•••••••• (saved — leave blank to keep)' : 'Paste your SMS gateway API key'}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 pr-10 py-2 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <button type="button" onClick={() => setShowKey(!showKey)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                {showKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3 pt-1">
          <button type="submit" disabled={saving} className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white font-bold text-xs rounded-xl shadow-xs transition-colors cursor-pointer">
            {saving ? 'Saving...' : 'Save SMS Settings'}
          </button>
          {saved && <span className="text-xs font-bold text-emerald-600">✓ Saved</span>}
        </div>
      </form>

      {/* Test send */}
      <div className="mt-6 pt-5 border-t border-slate-100">
        <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Send a Test Message</h3>
        <div className="flex items-center space-x-2">
          <input
            value={testMobile}
            onChange={(e) => setTestMobile(e.target.value)}
            placeholder="+91XXXXXXXXXX"
            className="flex-1 bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <button type="button" onClick={handleSendTest} disabled={sendingTest || !connected} className="px-4 py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-40 text-white text-xs font-semibold rounded-xl flex items-center space-x-1.5 whitespace-nowrap cursor-pointer">
            <Send className="w-3.5 h-3.5" />
            <span>{sendingTest ? 'Sending...' : 'Send Test'}</span>
          </button>
        </div>
        {!connected && <p className="text-[11px] text-slate-400 mt-1.5">Save your API Endpoint URL, Sender ID, and API Key above first.</p>}
        {testResult && (
          <p className={`mt-2 text-[11px] ${testResult.success ? 'text-emerald-600' : 'text-rose-600'}`}>{testResult.message}</p>
        )}
      </div>
    </div>
  );
};

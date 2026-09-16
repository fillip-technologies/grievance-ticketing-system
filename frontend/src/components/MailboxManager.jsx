import React, { useState } from 'react';
import {
  Mail,
  Plus,
  Server,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Trash2,
  X,
  Sparkles,
  Lock,
  Eye,
  EyeOff,
  ShieldCheck,
  Send,
  Clock,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { verifySmtp, testMailboxReceipt, syncMailboxNow } from '../utils/storage';

// Known providers auto-fill their server settings so most people never see a host/port field.
const PROVIDER_PRESETS = {
  Gmail: { incomingHost: 'imap.gmail.com', port: 993, outgoingSmtpHost: 'smtp.gmail.com', outgoingSmtpPort: 465 },
  Outlook: { incomingHost: 'outlook.office365.com', port: 993, outgoingSmtpHost: 'smtp.office365.com', outgoingSmtpPort: 587 },
  Hostinger: { incomingHost: 'imap.hostinger.com', port: 993, outgoingSmtpHost: 'smtp.hostinger.com', outgoingSmtpPort: 465 },
};

export const MailboxManager = ({
  mailboxes,
  onAddMailbox,
  onDeleteMailbox,
  onToggleMailboxStatus,
  onMailboxSynced,
}) => {
  const [isAdding, setIsAdding] = useState(false);
  const [isSyncingId, setIsSyncingId] = useState(null);

  // Form state
  const [emailAddress, setEmailAddress] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [serverType, setServerType] = useState('Gmail');
  const [incomingHost, setIncomingHost] = useState(PROVIDER_PRESETS.Gmail.incomingHost);
  const [port, setPort] = useState(PROVIDER_PRESETS.Gmail.port);
  const [outgoingSmtpHost, setOutgoingSmtpHost] = useState(PROVIDER_PRESETS.Gmail.outgoingSmtpHost);
  const [outgoingSmtpPort, setOutgoingSmtpPort] = useState(PROVIDER_PRESETS.Gmail.outgoingSmtpPort);
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [useSsl, setUseSsl] = useState(true);
  const [autoDispatch, setAutoDispatch] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const isKnownProvider = serverType !== 'Other';

  const handleProviderChange = (value) => {
    setServerType(value);
    const preset = PROVIDER_PRESETS[value];
    if (preset) {
      setIncomingHost(preset.incomingHost);
      setPort(preset.port);
      setOutgoingSmtpHost(preset.outgoingSmtpHost);
      setOutgoingSmtpPort(preset.outgoingSmtpPort);
      setShowAdvanced(false);
    } else {
      // "Other" — clear so the domain-based guess (or manual entry) below takes over.
      setIncomingHost('');
      setOutgoingSmtpHost('');
      setPort(993);
      setOutgoingSmtpPort(465);
      setShowAdvanced(true);
    }
  };

  // Connection test states
  const [testStatus, setTestStatus] = useState('idle');
  const [testMessage, setTestMessage] = useState(null);
  const [sendingReceiptId, setSendingReceiptId] = useState(null);
  const [receiptSentMessage, setReceiptSentMessage] = useState(null);

  const handleTestConnection = async () => {
    if (!emailAddress.trim() || !password.trim()) {
      setTestStatus('error');
      setTestMessage('Please enter the mailbox email address and password first.');
      return;
    }

    setTestStatus('testing');
    setTestMessage('Handshaking with outgoing SMTP over SSL/TLS...');

    try {
      const defaultHost = outgoingSmtpHost.trim() || incomingHost.trim() || `mail.${emailAddress.split('@')[1] || 'domain.com'}`;
      const data = await verifySmtp({
        emailAddress: emailAddress.trim(),
        host: defaultHost,
        port: outgoingSmtpPort || 465,
        password,
      });
      if (data.success) {
        setTestStatus('success');
        setTestMessage(`SMTP Authenticated (Latency: ${data.latencyMs || 0}ms). IMAP credentials will be verified on first sync.`);
      } else {
        setTestStatus('error');
        setTestMessage(data.message || 'SMTP handshake failed.');
      }
    } catch (e) {
      setTestStatus('error');
      setTestMessage(e?.message || 'Failed to verify connection. Check credentials and server settings.');
    }
  };

  const handleTestSendReceipt = async (mb) => {
    setSendingReceiptId(mb.id);
    setReceiptSentMessage(null);
    try {
      const data = await testMailboxReceipt(mb.id);
      setReceiptSentMessage({
        id: mb.id,
        msg: data.success
          ? `Test receipt dispatched via ${data.smtpServer || 'configured SMTP'} — ${data.message}`
          : `Not dispatched: ${data.message}`,
      });
    } catch (e) {
      setReceiptSentMessage({ id: mb.id, msg: `Failed: ${e?.message}` });
    } finally {
      setSendingReceiptId(null);
    }
  };

  const handleAddSubmit = (e) => {
    e.preventDefault();
    if (!emailAddress.trim() || !displayName.trim()) return;

    const domain = emailAddress.split('@')[1] || 'domain.com';
    onAddMailbox({
      emailAddress: emailAddress.trim().toLowerCase(),
      displayName: displayName.trim(),
      serverType,
      incomingHost: incomingHost.trim() || `imap.${domain}`,
      port: Number(port) || 993,
      incomingUsername: emailAddress.trim().toLowerCase(),
      incomingPassword: password,
      incomingUseSsl: useSsl,
      outgoingSmtpHost: outgoingSmtpHost.trim() || `smtp.${domain}`,
      outgoingSmtpPort: Number(outgoingSmtpPort) || 465,
      smtpUseSsl: useSsl,
      smtpUsername: emailAddress.trim().toLowerCase(),
      smtpPassword: password,
      autoDispatch,
    });

    setEmailAddress('');
    setDisplayName('');
    setPassword('');
    handleProviderChange('Gmail');
    setTestStatus('idle');
    setTestMessage(null);
    setIsAdding(false);
  };

  const handleTriggerSync = async (mb) => {
    setIsSyncingId(mb.id);
    try {
      const data = await syncMailboxNow(mb.id);
      onMailboxSynced?.(data.mailbox);
      const created = data.result?.created || 0;
      const fetched = data.result?.fetched || 0;
      const skipped = data.result?.skipped || 0;
      if (data.result?.error) {
        setReceiptSentMessage({ id: mb.id, msg: `Sync error: ${data.result.error}` });
      } else {
        const skippedLabel = skipped ? `, ${skipped} auto-reply/bounce skipped` : '';
        setReceiptSentMessage({ id: mb.id, msg: `Synced: ${fetched} unread email(s) checked, ${created} new ticket(s) created${skippedLabel}.` });
      }
    } catch (e) {
      setReceiptSentMessage({ id: mb.id, msg: `Sync failed: ${e?.message}` });
    } finally {
      setIsSyncingId(null);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200/90 shadow-xs p-5 sm:p-6 mb-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-100">
        <div>
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-lg bg-sky-100 text-sky-700 flex items-center justify-center">
              <Mail className="w-4 h-4" />
            </div>
            <h2 className="text-base font-bold text-slate-900 font-sans tracking-tight">
              Connect Your Inbox
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Connect the inbox that receives your complaint emails. We check it automatically
            every ~60 seconds — no manual action needed.
          </p>
        </div>

        <button
          onClick={() => setIsAdding(!isAdding)}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-xl shadow-xs flex items-center justify-center space-x-1.5 transition-colors cursor-pointer self-start sm:self-auto"
        >
          {isAdding ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
          <span>{isAdding ? 'Cancel' : 'Add Mailbox'}</span>
        </button>
      </div>

      <div className="mt-4 p-3.5 bg-emerald-50 text-emerald-900 rounded-xl border border-emerald-200 text-xs flex items-start space-x-3">
        <div className="p-1.5 rounded-lg shrink-0 mt-0.5 bg-emerald-100 text-emerald-700">
          <Clock className="w-4 h-4" />
        </div>
        <p className="text-[11px] leading-relaxed">
          Every mailbox with status <strong>Connected</strong> is checked automatically in the
          background. Use "Sync Now" below only to test immediately after connecting a new mailbox.
        </p>
      </div>

      {/* Add Mailbox Form */}
      {isAdding && (
        <form
          onSubmit={handleAddSubmit}
          className="my-5 p-5 bg-slate-50 border border-slate-200 rounded-2xl space-y-4 animate-in fade-in duration-200 shadow-sm"
        >
          <div className="flex items-center justify-between border-b border-slate-200 pb-2">
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center space-x-2">
              <Server className="w-4 h-4 text-indigo-600" />
              <span>Connect Mailbox</span>
            </h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Display Name <span className="text-rose-500">*</span>
              </label>
              <input
                type="text" required value={displayName} onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g. Complaint Intake Inbox"
                className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Email Address <span className="text-rose-500">*</span>
              </label>
              <input
                type="email" required value={emailAddress}
                onChange={(e) => {
                  setEmailAddress(e.target.value);
                  if (!incomingHost && e.target.value.includes('@')) {
                    const domain = e.target.value.split('@')[1];
                    setIncomingHost(`imap.${domain}`);
                  }
                }}
                placeholder="e.g. complaints@yourcompany.com"
                className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center justify-between">
                <span className="flex items-center space-x-1">
                  <Lock className="w-3 h-3 text-slate-500" />
                  <span>Password / App Password <span className="text-rose-500">*</span></span>
                </span>
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'} required value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Used for both IMAP and SMTP login"
                  className="w-full bg-white border border-slate-300 rounded-xl pl-3 pr-10 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-indigo-500 font-mono"
                />
                <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                  {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
              <p className="text-[10px] text-slate-500 mt-1">For Gmail/Outlook, use an app-specific password (2FA accounts require it).</p>
            </div>

            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-slate-700 mb-1">Email Provider</label>
              <select value={serverType} onChange={(e) => handleProviderChange(e.target.value)} className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-indigo-500 cursor-pointer">
                <option value="Gmail">Gmail</option>
                <option value="Outlook">Outlook / Microsoft 365</option>
                <option value="Hostinger">Hostinger</option>
                <option value="Other">Other / Custom</option>
              </select>
              {isKnownProvider && (
                <p className="text-[10px] text-slate-500 mt-1">
                  We'll connect automatically using {PROVIDER_PRESETS[serverType].incomingHost} — nothing else to fill in.
                </p>
              )}
            </div>
          </div>

          {isKnownProvider && !showAdvanced && (
            <button
              type="button"
              onClick={() => setShowAdvanced(true)}
              className="text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 cursor-pointer flex items-center space-x-1"
            >
              <ChevronDown className="w-3.5 h-3.5" />
              <span>Show advanced server settings</span>
            </button>
          )}

          {(showAdvanced || !isKnownProvider) && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-4 bg-white border border-slate-200 rounded-xl">
              {isKnownProvider && (
                <button
                  type="button"
                  onClick={() => setShowAdvanced(false)}
                  className="sm:col-span-2 text-[11px] font-semibold text-slate-500 hover:text-slate-800 cursor-pointer flex items-center space-x-1 -mt-1"
                >
                  <ChevronUp className="w-3.5 h-3.5" />
                  <span>Hide advanced server settings</span>
                </button>
              )}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Incoming (IMAP) Host & Port</label>
                <div className="grid grid-cols-3 gap-2">
                  <input type="text" value={incomingHost} onChange={(e) => setIncomingHost(e.target.value)} placeholder="imap.domain.com" className="col-span-2 bg-white border border-slate-300 rounded-xl px-3 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-indigo-500 font-mono" />
                  <input type="number" value={port} onChange={(e) => setPort(Number(e.target.value))} placeholder="993" className="bg-white border border-slate-300 rounded-xl px-2 py-2 text-xs text-slate-900 font-mono focus:ring-2 focus:ring-indigo-500" />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Outgoing (SMTP) Host & Port</label>
                <div className="grid grid-cols-3 gap-2">
                  <input type="text" value={outgoingSmtpHost} onChange={(e) => setOutgoingSmtpHost(e.target.value)} placeholder="smtp.domain.com" className="col-span-2 bg-white border border-slate-300 rounded-xl px-3 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-indigo-500 font-mono" />
                  <input type="number" value={outgoingSmtpPort} onChange={(e) => setOutgoingSmtpPort(Number(e.target.value))} placeholder="465" className="bg-white border border-slate-300 rounded-xl px-2 py-2 text-xs text-slate-900 font-mono focus:ring-2 focus:ring-indigo-500" />
                </div>
              </div>

              <label className="flex items-center space-x-2 cursor-pointer sm:col-span-2">
                <input type="checkbox" checked={useSsl} onChange={(e) => setUseSsl(e.target.checked)} className="rounded text-indigo-600 focus:ring-indigo-500" />
                <span className="text-xs font-medium text-slate-700">Use a secure connection (SSL/TLS)</span>
              </label>
            </div>
          )}

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 border-t border-slate-200/80">
            <label className="flex items-center space-x-2 cursor-pointer">
              <input type="checkbox" checked={autoDispatch} onChange={(e) => setAutoDispatch(e.target.checked)} className="rounded text-indigo-600 focus:ring-indigo-500" />
              <span className="text-xs font-semibold text-slate-800">Check this inbox automatically (recommended)</span>
            </label>

            <button type="button" onClick={handleTestConnection} disabled={testStatus === 'testing'} className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold rounded-xl flex items-center space-x-1.5 transition-colors cursor-pointer shrink-0 disabled:opacity-50">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span>{testStatus === 'testing' ? 'Testing...' : 'Test Connection'}</span>
            </button>
          </div>

          {testMessage && (
            <div className={`p-3 rounded-xl text-xs flex items-center space-x-2 border ${
              testStatus === 'success' ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : testStatus === 'error' ? 'bg-rose-50 border-rose-200 text-rose-800' : 'bg-indigo-50 border-indigo-200 text-indigo-800'
            }`}>
              {testStatus === 'testing' && <RefreshCw className="w-4 h-4 animate-spin text-indigo-600" />}
              {testStatus === 'success' && <CheckCircle2 className="w-4 h-4 text-emerald-600" />}
              {testStatus === 'error' && <AlertCircle className="w-4 h-4 text-rose-600" />}
              <span className="font-medium">{testMessage}</span>
            </div>
          )}

          <div className="flex justify-end space-x-2 pt-2">
            <button type="button" onClick={() => setIsAdding(false)} className="px-4 py-2 bg-slate-200 text-slate-700 text-xs font-semibold rounded-xl hover:bg-slate-300 cursor-pointer">Cancel</button>
            <button type="submit" className="px-5 py-2 bg-indigo-600 text-white text-xs font-bold rounded-xl hover:bg-indigo-700 shadow-md cursor-pointer">Save Mailbox</button>
          </div>
        </form>
      )}

      {/* Connected Mailboxes Grid */}
      {mailboxes.length === 0 ? (
        <div className="py-12 text-center text-xs text-slate-500">No mailboxes connected yet.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
          {mailboxes.map((mb) => (
            <div key={mb.id} className="p-5 rounded-2xl border border-slate-200/90 bg-slate-50/50 flex flex-col justify-between space-y-4 shadow-xs hover:border-slate-300 transition-all">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-sm text-slate-900">{mb.displayName}</span>
                    <button
                      onClick={() => onToggleMailboxStatus(mb.id)}
                      className={`px-2.5 py-0.5 text-[10px] font-bold rounded-full cursor-pointer ${
                        mb.status === 'Connected' ? 'bg-emerald-100 text-emerald-800 border border-emerald-200' : 'bg-slate-200 text-slate-700'
                      }`}
                      title="Click to toggle Connected/Paused"
                    >
                      {mb.status}
                    </button>
                  </div>
                  <p className="text-xs text-indigo-600 font-mono font-bold mt-1">{mb.emailAddress}</p>
                  <div className="flex flex-wrap items-center gap-2 mt-2">
                    <span className="text-[11px] text-slate-600 font-mono bg-white px-2 py-0.5 rounded-md border border-slate-200">
                      IMAP: {mb.incomingHost}:{mb.port}
                    </span>
                    <span className="text-[11px] text-emerald-700 font-mono bg-emerald-50/80 border border-emerald-200 px-2 py-0.5 rounded-md font-semibold">
                      SMTP: {mb.outgoingSmtpHost}:{mb.outgoingSmtpPort}
                    </span>
                  </div>
                  {mb.lastSyncError && (
                    <p className="text-[11px] text-rose-600 mt-2 flex items-center space-x-1">
                      <AlertCircle className="w-3 h-3" /><span>{mb.lastSyncError}</span>
                    </p>
                  )}
                </div>

                <button onClick={() => onDeleteMailbox(mb.id)} className="text-slate-400 hover:text-rose-600 p-1.5 rounded-lg hover:bg-rose-50 transition-colors cursor-pointer" title="Disconnect Mailbox">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>

              {receiptSentMessage && receiptSentMessage.id === mb.id && (
                <div className="p-2.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span className="font-mono text-[11px] leading-tight">{receiptSentMessage.msg}</span>
                </div>
              )}

              <div className="pt-3 border-t border-slate-200/80 flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="flex items-center space-x-3 text-slate-600">
                  <span className="flex items-center space-x-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
                    <span>Ingested: <strong className="font-mono text-slate-900">{mb.totalTicketsIngested}</strong></span>
                  </span>
                  {mb.lastSyncedAt && (
                    <span className="text-[10px] text-slate-400">Last synced {new Date(mb.lastSyncedAt).toLocaleTimeString()}</span>
                  )}
                </div>

                <div className="flex items-center space-x-2">
                  <button onClick={() => handleTestSendReceipt(mb)} disabled={sendingReceiptId === mb.id} className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-xl text-xs flex items-center space-x-1 transition-all shadow-xs cursor-pointer disabled:opacity-50" title="Send Test Customer Receipt over Outgoing SMTP">
                    <Send className={`w-3 h-3 ${sendingReceiptId === mb.id ? 'animate-bounce' : ''}`} />
                    <span>{sendingReceiptId === mb.id ? 'Sending...' : 'Test Receipt'}</span>
                  </button>

                  <button onClick={() => handleTriggerSync(mb)} disabled={isSyncingId === mb.id} className="px-3.5 py-1.5 bg-white border border-slate-300 hover:bg-slate-100 text-slate-800 font-semibold rounded-xl text-xs flex items-center space-x-1.5 transition-all shadow-xs cursor-pointer">
                    <RefreshCw className={`w-3.5 h-3.5 text-indigo-600 ${isSyncingId === mb.id ? 'animate-spin' : ''}`} />
                    <span>{isSyncingId === mb.id ? 'Syncing...' : 'Sync Now'}</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

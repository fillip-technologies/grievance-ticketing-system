import React, { useState } from 'react';
import { PhoneCall, User, Mail, Hash, Clock, ShieldAlert, CheckCircle2, Copy, Send } from 'lucide-react';
import { createManualTicket } from '../utils/storage';

// datetime-local inputs need "YYYY-MM-DDTHH:mm" in *local* time — not toISOString(), which is UTC.
const toLocalInputValue = (date) => {
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

const buildInitialForm = () => ({
  customerName: '',
  customerMobile: '',
  customerEmail: '',
  message: '',
  externalReference: '',
  occurredAt: toLocalInputValue(new Date()),
});

export const HelpDeskForm = ({ onCreated }) => {
  const [form, setForm] = useState(buildInitialForm);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [lastCreated, setLastCreated] = useState(null);
  const [copied, setCopied] = useState(false);

  const setField = (key) => (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    if (!form.customerName.trim() || !form.customerMobile.trim()) {
      setErrorMsg('Caller name and phone number are required.');
      return;
    }
    if (!form.message.trim()) {
      setErrorMsg("Please describe the caller's issue or question.");
      return;
    }
    setSubmitting(true);
    try {
      const data = await createManualTicket({
        customerName: form.customerName.trim(),
        customerMobile: form.customerMobile.trim(),
        customerEmail: form.customerEmail.trim() || null,
        message: form.message.trim(),
        externalReference: form.externalReference.trim() || null,
        // form.occurredAt is local time ("YYYY-MM-DDTHH:mm"); new Date(...) parses it as local
        // and toISOString() converts to the UTC instant the backend expects.
        occurredAt: form.occurredAt ? new Date(form.occurredAt).toISOString() : null,
      });
      setLastCreated(data.ticket);
      setForm(buildInitialForm());
      onCreated && onCreated(data.ticket);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to create the ticket.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCopyId = () => {
    if (!lastCreated) return;
    navigator.clipboard.writeText(lastCreated.id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl border border-slate-200/90 shadow-xs p-6 sm:p-8">
        <div className="flex items-center space-x-3 pb-6 border-b border-slate-100">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-md shadow-indigo-600/20">
            <PhoneCall className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-900">Help Desk — Log a Phone Call</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              For callers who phone in instead of emailing. Fill in what the caller tells you and submit — it's
              classified, assigned, and put on the SLA clock exactly like an emailed complaint.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Caller Name <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  value={form.customerName}
                  onChange={setField('customerName')}
                  placeholder="e.g. Suresh Nair"
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Phone Number <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <PhoneCall className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  value={form.customerMobile}
                  onChange={setField('customerMobile')}
                  placeholder="+91 90000 00000"
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono font-medium"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Email (optional)
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  value={form.customerEmail}
                  onChange={setField('customerEmail')}
                  placeholder="caller@example.com"
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                />
              </div>
              <p className="mt-1 text-[11px] text-slate-500">Without an email, we can't send the caller an automatic acknowledgement/status update.</p>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Reference / Ticket No. (optional)
              </label>
              <div className="relative">
                <Hash className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  value={form.externalReference}
                  onChange={setField('externalReference')}
                  placeholder="e.g. an earlier booking/order number"
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono font-medium"
                />
              </div>
              <p className="mt-1 text-[11px] text-slate-500">If the caller is following up on an earlier booking, order, or ticket, note it here.</p>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Call Date & Time
              </label>
              <div className="relative">
                <Clock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="datetime-local"
                  value={form.occurredAt}
                  onChange={setField('occurredAt')}
                  max={toLocalInputValue(new Date())}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                />
              </div>
              <p className="mt-1 text-[11px] text-slate-500">Defaults to now — change this if you're logging the call a while after it happened, so the SLA clock starts from the real call time.</p>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Issue / Query <span className="text-rose-500">*</span>
            </label>
            <textarea
              rows={4}
              value={form.message}
              onChange={setField('message')}
              placeholder="Write down what the caller is asking about or complaining about, in their own words as closely as possible."
              className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
            />
          </div>

          {errorMsg && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs flex items-start space-x-2">
              <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white font-bold text-xs rounded-xl shadow-sm transition-colors cursor-pointer flex items-center justify-center space-x-1.5"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{submitting ? 'Logging call...' : 'Log Call & Create Ticket'}</span>
            </button>
          </div>
        </form>

        {lastCreated && (
          <div className="mt-6 p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-900 space-y-2">
            <div className="flex items-center space-x-2 font-semibold">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>Ticket created — read this number back to the caller:</span>
            </div>
            <div className="flex items-center space-x-2 bg-white border border-emerald-200 rounded-lg px-3 py-2 font-mono text-sm">
              <span className="flex-1 font-bold">{lastCreated.id}</span>
              <button type="button" onClick={handleCopyId} className="text-emerald-600 hover:text-emerald-800 cursor-pointer">
                <Copy className="w-3.5 h-3.5" />
              </button>
            </div>
            {copied && <span className="text-emerald-600 text-[11px]">Copied!</span>}
            <p className="text-emerald-700">
              Classified as <span className="font-semibold">{lastCreated.category}</span> ({lastCreated.urgency} urgency)
              {lastCreated.assignedToName ? <> and assigned to <span className="font-semibold">{lastCreated.assignedToName}</span></> : ' — currently unassigned'}.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

import React, { useState } from 'react';
import {
  Search,
  TicketCheck,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Flame,
  MessageSquare,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { trackComplaint } from '../utils/storage';

const STATUS_META = {
  Open: { label: 'Open — awaiting review', cls: 'bg-blue-100 text-blue-800 border-blue-300' },
  'In Progress': { label: 'In Progress', cls: 'bg-amber-100 text-amber-800 border-amber-300' },
  Escalated: { label: 'Escalated to senior authority', cls: 'bg-rose-100 text-rose-800 border-rose-300' },
  Resolved: { label: 'Resolved', cls: 'bg-emerald-100 text-emerald-800 border-emerald-300' },
  Closed: { label: 'Closed', cls: 'bg-slate-200 text-slate-600 border-slate-300' },
};

export const PublicStatusPage = ({ onBack }) => {
  const [ticketId, setTicketId] = useState('');
  const [contact, setContact] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!ticketId.trim() || !contact.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await trackComplaint(ticketId.trim(), contact.trim());
      setResult(data);
    } catch (err) {
      setError(err?.message || 'Could not find that ticket.');
    } finally {
      setLoading(false);
    }
  };

  const meta = result ? (STATUS_META[result.status] || { label: result.status, cls: 'bg-slate-100 text-slate-700 border-slate-300' }) : null;

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900 flex flex-col font-sans">
      <header className="border-b border-slate-200 bg-white/90 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-sm">
              <TicketCheck className="w-5 h-5" />
            </div>
            <span className="font-bold text-base tracking-tight text-slate-900">Track Ticket</span>
          </div>
          <button onClick={onBack} className="px-3 py-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer flex items-center space-x-1.5">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back</span>
          </button>
        </div>
      </header>

      <main className="flex-1 max-w-3xl w-full mx-auto px-4 sm:px-6 py-10">
        <div className="bg-white border border-slate-200/90 shadow-xs rounded-2xl p-6 sm:p-8">
          <h1 className="text-lg font-extrabold text-slate-900">Check your ticket status</h1>
          <p className="text-xs text-slate-500 mt-1">
            Enter your Ticket ID (from your acknowledgement email/WhatsApp message) and the email or mobile
            number you used when you filed it.
          </p>

          <form onSubmit={handleSubmit} className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input
              value={ticketId}
              onChange={(e) => setTicketId(e.target.value)}
              placeholder="Ticket ID (e.g. RAJGIR-2026-1001)"
              className="bg-slate-50 border border-slate-300 rounded-xl px-3.5 py-2.5 text-sm font-mono text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <input
              value={contact}
              onChange={(e) => setContact(e.target.value)}
              placeholder="Email or mobile number used"
              className="bg-slate-50 border border-slate-300 rounded-xl px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <button
              type="submit"
              disabled={loading || !ticketId.trim() || !contact.trim()}
              className="sm:col-span-2 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-bold text-sm rounded-xl shadow-sm transition-all cursor-pointer flex items-center justify-center space-x-2"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              <span>{loading ? 'Checking...' : 'Check Status'}</span>
            </button>
          </form>

          {error && (
            <div className="mt-5 p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {result && (
          <div className="mt-6 bg-white border border-slate-200/90 shadow-xs rounded-2xl p-6 sm:p-8 animate-in fade-in duration-200">
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <span className="font-mono text-sm font-bold text-indigo-700 bg-indigo-50 px-2.5 py-1 rounded border border-indigo-200">{result.id}</span>
              <span className={`px-2.5 py-1 text-xs font-bold rounded-full border ${meta.cls}`}>{meta.label}</span>
              {result.slaBreached && (
                <span className="px-2 py-1 text-xs font-bold bg-rose-600 text-white rounded flex items-center space-x-1">
                  <Flame className="w-3 h-3" /><span>SLA Breached</span>
                </span>
              )}
              {result.escalationLevel > 0 && (
                <span className="px-2 py-1 text-xs font-bold bg-amber-500 text-white rounded">Escalation Tier {result.escalationLevel}</span>
              )}
            </div>
            <h2 className="text-base font-bold text-slate-900">{result.subject}</h2>
            <p className="text-xs text-slate-500 mt-1">{result.orgName} &bull; {result.category}</p>

            <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
                <div className="flex items-center space-x-1.5 text-slate-500 mb-1"><Clock className="w-3.5 h-3.5" /><span>Filed</span></div>
                <p className="text-slate-800 font-semibold">{result.createdAt ? new Date(result.createdAt).toLocaleString() : '—'}</p>
              </div>
              <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
                <div className="flex items-center space-x-1.5 text-slate-500 mb-1"><Clock className="w-3.5 h-3.5" /><span>Target Resolution</span></div>
                <p className="text-slate-800 font-semibold">{result.dueBy ? new Date(result.dueBy).toLocaleString() : '—'}</p>
              </div>
              <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
                <div className="flex items-center space-x-1.5 text-slate-500 mb-1"><CheckCircle2 className="w-3.5 h-3.5" /><span>Resolved</span></div>
                <p className="text-slate-800 font-semibold">{result.resolvedAt ? new Date(result.resolvedAt).toLocaleString() : 'Not yet'}</p>
              </div>
            </div>

            {result.replies && result.replies.length > 0 && (
              <div className="mt-5">
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2 flex items-center space-x-1.5">
                  <MessageSquare className="w-3.5 h-3.5" /><span>Correspondence</span>
                </h3>
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {result.replies.map((r, i) => (
                    <div key={i} className={`p-3 rounded-xl text-xs border ${r.fromSupport ? 'bg-indigo-50 border-indigo-200' : 'bg-slate-50 border-slate-200'}`}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold text-slate-800">{r.fromSupport ? 'Support Team' : 'You'}</span>
                        <span className="text-slate-400">{r.timestamp ? new Date(r.timestamp).toLocaleString() : ''}</span>
                      </div>
                      <p className="text-slate-600 whitespace-pre-wrap">{r.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
};

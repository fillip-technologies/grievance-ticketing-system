import React, { useState } from 'react';
import {
  X,
  User,
  Phone,
  Clock,
  Sparkles,
  Send,
  CheckCircle2,
  Flame,
  History,
  MessageSquare,
  Copy,
  Check,
  UserCog,
  AlertTriangle,
  Loader2,
  Hash
} from 'lucide-react';
import { suggestReply as fetchSuggestedReply } from '../utils/storage';

const buildAckReminderText = (ticket) => {
  const dueLabel = ticket.dueBy ? new Date(ticket.dueBy).toLocaleString() : 'within the SLA window';
  return [
    `Dear ${ticket.customerName},`,
    '',
    `This is a follow-up acknowledgement of your ${ticket.category} complaint.`,
    '',
    `Ticket Reference: ${ticket.id}`,
    `Subject: ${ticket.subject}`,
    ticket.aiSummary ? `Summary: ${ticket.aiSummary}` : null,
    `Target Resolution: ${dueLabel}`,
    '',
    'Our team is actively working on this. Please keep this reference number for follow-ups.',
    '',
    'Regards,',
    'Grievance Desk Team',
  ].filter(Boolean).join('\n');
};

const ROLE_ALLOWED_STATUSES = {
  OrgAdmin: ['Open', 'In Progress', 'Resolved', 'Escalated', 'Closed'],
  Resolver: ['In Progress', 'Resolved'],
  EscalationAuthority: ['In Progress', 'Resolved'],
};

// Every status button shown in the Quick Actions bar — a status only actually renders as
// enabled if the current user's role also allows it (see ROLE_ALLOWED_STATUSES above).
const ALL_STATUSES = ['Open', 'In Progress', 'Escalated', 'Resolved', 'Closed'];

export const TicketDetailModal = ({
  ticket,
  onClose,
  onStatusChange,
  onAddReply,
  currentUser,
  team = [],
  onReassign,
  onToggleAwaitingCustomer,
}) => {
  const [replyText, setReplyText] = useState('');
  const [copied, setCopied] = useState(false);
  const [receiptSentToast, setReceiptSentToast] = useState(false);
  const [reassignOpen, setReassignOpen] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [suggestSource, setSuggestSource] = useState(null);

  if (!ticket) return null;

  const canEditStatus = currentUser?.role === 'OrgAdmin' || ticket.assignedTo === currentUser?.id;
  const allowedStatuses = ROLE_ALLOWED_STATUSES[currentUser?.role] || [];

  const handleCopyTicketNumber = () => {
    navigator.clipboard.writeText(ticket.id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleResendAck = () => {
    if (!ticket.customerEmail) {
      setReceiptSentToast(true);
      setTimeout(() => setReceiptSentToast(false), 3000);
      return;
    }
    onAddReply(ticket.id, buildAckReminderText(ticket));
    setReceiptSentToast(true);
    setTimeout(() => setReceiptSentToast(false), 3000);
  };

  const handleSuggestReply = async () => {
    setSuggesting(true);
    setSuggestSource(null);
    try {
      const data = await fetchSuggestedReply(ticket.id);
      setReplyText(data.reply || '');
      setSuggestSource(data.source || null);
    } catch (err) {
      setSuggestSource(`Failed to generate a suggestion: ${err.message}`);
    } finally {
      setSuggesting(false);
    }
  };

  const handleReplySubmit = (e) => {
    e.preventDefault();
    if (!replyText.trim()) return;
    onAddReply(ticket.id, replyText.trim());
    setReplyText('');
    setSuggestSource(null);
  };

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'Open':
        return 'bg-blue-100 text-blue-800 border-blue-300';
      case 'In Progress':
        return 'bg-amber-100 text-amber-800 border-amber-300';
      case 'Escalated':
        return 'bg-rose-100 text-rose-800 border-rose-300 font-semibold';
      case 'Resolved':
        return 'bg-emerald-100 text-emerald-800 border-emerald-300';
      case 'Closed':
        return 'bg-slate-200 text-slate-600 border-slate-300';
      default:
        return 'bg-slate-100 text-slate-800 border-slate-300';
    }
  };

  const reassignCandidates = team.filter((m) => m.isActive);

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex justify-end p-0 sm:p-4 overflow-y-auto">
      <div className="w-full max-w-2xl bg-white h-full sm:h-auto sm:max-h-[92vh] sm:rounded-2xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="p-4 sm:p-6 bg-slate-900 text-white flex items-center justify-between border-b border-slate-800 shrink-0">
          <div>
            <div className="flex items-center space-x-2.5 flex-wrap gap-y-1.5">
              <span className="font-mono text-sm font-bold text-sky-400 bg-sky-950/80 px-2.5 py-0.5 rounded border border-sky-800/60 flex items-center space-x-1.5">
                <span>{ticket.id}</span>
                <button onClick={handleCopyTicketNumber} title="Copy Ticket Number" className="p-0.5 hover:text-white text-sky-300 transition-colors cursor-pointer">
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </span>

              <span className={`px-2.5 py-0.5 text-xs rounded-full border ${getStatusBadgeClass(ticket.status)}`}>
                {ticket.status}
              </span>

              {ticket.slaBreached && (
                <span className="px-2 py-0.5 text-xs font-bold bg-rose-600 text-white rounded flex items-center space-x-1">
                  <Flame className="w-3 h-3" />
                  <span>Response Overdue</span>
                </span>
              )}

              {ticket.awaitingCustomer && (
                <span className="px-2 py-0.5 text-xs font-bold bg-slate-600 text-white rounded flex items-center space-x-1">
                  <Clock className="w-3 h-3" />
                  <span>Waiting on Customer</span>
                </span>
              )}

              {ticket.escalationLevel > 0 && (
                <span className="px-2 py-0.5 text-xs font-bold bg-amber-600/90 text-white rounded">
                  Escalated (Level {ticket.escalationLevel})
                </span>
              )}
            </div>
            <h2 className="text-base font-bold text-white mt-1.5 line-clamp-1 font-sans">{ticket.subject}</h2>
          </div>

          <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-4 sm:p-6 overflow-y-auto flex-1 space-y-6">
          {ticket.needsAttention && (ticket.attentionReasons || []).length > 0 && (
            <div className="bg-amber-50 border border-amber-300 rounded-xl p-3 flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div className="text-xs text-amber-900">
                <p className="font-bold mb-1">This ticket needs attention:</p>
                <ul className="list-disc list-inside space-y-0.5">
                  {ticket.attentionReasons.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </div>
            </div>
          )}

          {/* Quick Actions Bar */}
          {canEditStatus && (
            <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 flex flex-wrap items-center justify-between gap-3 text-xs">
              <div className="flex items-center space-x-2">
                <span className="font-semibold text-slate-700">Status:</span>
                <div className="flex flex-wrap gap-1.5">
                  {ALL_STATUSES.map((st) => {
                    const allowed = allowedStatuses.includes(st);
                    return (
                      <button
                        key={st}
                        disabled={!allowed}
                        onClick={() => allowed && onStatusChange(ticket.id, st)}
                        title={!allowed ? 'Not permitted for your role' : undefined}
                        className={`px-3 py-1 rounded-lg text-xs font-medium border transition-all ${
                          ticket.status === st
                            ? 'bg-slate-900 text-white border-slate-900 font-semibold shadow-xs'
                            : allowed
                            ? 'bg-white text-slate-700 border-slate-300 hover:bg-slate-100 cursor-pointer'
                            : 'bg-slate-100 text-slate-300 border-slate-200 cursor-not-allowed'
                        }`}
                      >
                        {st}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="flex items-center space-x-2">
                {onToggleAwaitingCustomer && ticket.status !== 'Resolved' && ticket.status !== 'Closed' && (
                  <button
                    onClick={() => onToggleAwaitingCustomer(ticket.id, !ticket.awaitingCustomer)}
                    className={`px-3 py-1 rounded-lg font-bold transition-all cursor-pointer flex items-center space-x-1 border ${
                      ticket.awaitingCustomer
                        ? 'bg-slate-900 hover:bg-slate-800 text-white border-slate-900'
                        : 'bg-slate-50 hover:bg-slate-100 text-slate-700 border-slate-300'
                    }`}
                    title={ticket.awaitingCustomer ? 'Resume the response-time clock' : 'Pause the response-time clock while you wait for the customer to reply'}
                  >
                    <Clock className="w-3 h-3" />
                    <span>{ticket.awaitingCustomer ? 'Resume Timer' : 'Waiting on Customer'}</span>
                  </button>
                )}
                <button
                  onClick={handleResendAck}
                  className="px-3 py-1 bg-sky-50 hover:bg-sky-100 text-sky-800 border border-sky-300 font-bold rounded-lg transition-all cursor-pointer flex items-center space-x-1"
                  title="Send a confirmation email to the customer again"
                >
                  <Send className="w-3 h-3 text-sky-600" />
                  <span>Resend Confirmation Email</span>
                </button>
              </div>
            </div>
          )}

          {receiptSentToast && (
            <div className="p-3 bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs font-bold rounded-xl animate-in fade-in flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>
                {ticket.customerEmail
                  ? `Acknowledgement with Ticket #${ticket.id} sent to ${ticket.customerName}!`
                  : 'No customer email on file — nothing to send.'}
              </span>
            </div>
          )}

          {/* AI Intent & Routing Box */}
          <div className="bg-indigo-50/60 border border-indigo-200/80 rounded-xl p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2 text-indigo-900 font-bold text-xs">
                <Sparkles className="w-4 h-4 text-indigo-600" />
                <span>AI Summary</span>
              </div>
              <span className="text-[11px] font-mono text-indigo-700 bg-indigo-100 px-2 py-0.5 rounded font-semibold">
                AI Confidence: {Math.round(ticket.confidenceScore * 100)}%
              </span>
            </div>

            <div className="mt-2 grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
              <div>
                <span className="text-slate-500 block text-[10px] uppercase font-medium">Type</span>
                <span className="font-bold text-slate-900">{ticket.category}</span>
              </div>
              {ticket.sectionName && (
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-medium">Section</span>
                  <span className="font-bold text-violet-700">{ticket.sectionName}</span>
                </div>
              )}
              <div>
                <span className="text-slate-500 block text-[10px] uppercase font-medium">Priority</span>
                <span className="font-bold text-slate-900">{ticket.priority}</span>
              </div>
              <div className="relative">
                <span className="text-slate-500 block text-[10px] uppercase font-medium">Assigned To</span>
                <div className="flex items-center space-x-1.5">
                  <span className="font-bold text-slate-900">{ticket.assignedToName || 'Unassigned'}</span>
                  {onReassign && (
                    <button onClick={() => setReassignOpen((v) => !v)} className="text-indigo-600 hover:text-indigo-800 cursor-pointer" title="Reassign">
                      <UserCog className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
                {reassignOpen && (
                  <div className="absolute z-10 mt-1 w-48 bg-white border border-slate-200 rounded-xl shadow-lg p-1.5 text-xs">
                    {reassignCandidates.length === 0 && <div className="p-2 text-slate-400">No active team members</div>}
                    {reassignCandidates.map((m) => (
                      <button
                        key={m.id}
                        onClick={() => {
                          onReassign(ticket.id, m.id);
                          setReassignOpen(false);
                        }}
                        className="w-full text-left px-2.5 py-1.5 hover:bg-indigo-50 rounded-lg cursor-pointer flex items-center justify-between"
                      >
                        <span>{m.name}</span>
                        <span className="text-[10px] text-slate-400">{m.role}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {ticket.aiSummary && (
              <p className="mt-2 text-xs text-slate-700 bg-white/80 p-2.5 rounded-lg border border-indigo-100 italic">"{ticket.aiSummary}"</p>
            )}
          </div>

          {/* Customer Metadata Card */}
          <div className={`grid grid-cols-1 sm:grid-cols-3 ${ticket.externalReference ? 'lg:grid-cols-4' : ''} gap-3`}>
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs">
              <div className="flex items-center space-x-1.5 text-slate-500 mb-1"><User className="w-3.5 h-3.5" /><span>Customer Name</span></div>
              <p className="font-bold text-slate-900">{ticket.customerName}</p>
            </div>
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs">
              <div className="flex items-center space-x-1.5 text-slate-500 mb-1"><Phone className="w-3.5 h-3.5" /><span>Mobile Number</span></div>
              <p className="font-mono font-bold text-slate-900">{ticket.customerMobile || '—'}</p>
            </div>
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs">
              <div className="flex items-center space-x-1.5 text-slate-500 mb-1"><Clock className="w-3.5 h-3.5" /><span>Channel / Received</span></div>
              <p className="font-bold text-slate-900">
                {ticket.channel} ({new Date(ticket.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})
              </p>
            </div>
            {ticket.externalReference && (
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs">
                <div className="flex items-center space-x-1.5 text-slate-500 mb-1"><Hash className="w-3.5 h-3.5" /><span>Caller's Reference</span></div>
                <p className="font-mono font-bold text-slate-900">{ticket.externalReference}</p>
              </div>
            )}
          </div>

          {/* Original Message */}
          <div>
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-2">Original Complaint Message</h3>
            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs text-slate-800 whitespace-pre-wrap font-sans leading-relaxed">
              {ticket.description}
            </div>
          </div>

          {/* Reply Thread */}
          <div>
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-3 flex items-center space-x-1.5">
              <MessageSquare className="w-4 h-4 text-indigo-600" />
              <span>Replies ({ticket.replies.length})</span>
            </h3>

            <div className="space-y-3 mb-4">
              {ticket.replies.map((reply) => (
                <div key={reply.id} className={`p-3 rounded-xl border text-xs ${reply.isAgent ? 'bg-indigo-50/70 border-indigo-200 ml-4' : 'bg-slate-50 border-slate-200 mr-4'}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-bold text-slate-900">{reply.sender}</span>
                    <span className="text-[10px] text-slate-500">{new Date(reply.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                  <p className="text-slate-800 leading-relaxed whitespace-pre-wrap">{reply.text}</p>
                </div>
              ))}
            </div>

            {canEditStatus && (
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[10px] text-slate-500">
                    {ticket.customerEmail ? 'Response to customer (emailed automatically)' : 'Internal note'}
                  </span>
                  <button
                    type="button"
                    onClick={handleSuggestReply}
                    disabled={suggesting}
                    className="text-[11px] font-bold text-indigo-600 hover:text-indigo-800 disabled:opacity-60 cursor-pointer flex items-center space-x-1"
                    title="Draft a reply with AI — review and edit before sending"
                  >
                    {suggesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                    <span>{suggesting ? 'Drafting...' : 'Suggest Reply'}</span>
                  </button>
                </div>
                {suggestSource && (
                  <p className="text-[10px] text-slate-400 mb-1.5">Draft source: {suggestSource} — review before sending.</p>
                )}
                <form onSubmit={handleReplySubmit} className="flex space-x-2">
                  <textarea
                    rows={3}
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    placeholder={ticket.customerEmail ? 'Type response to customer (emailed automatically)...' : 'Type internal note...'}
                    className="flex-1 bg-white border border-slate-300 rounded-xl px-3.5 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                  />
                  <button type="submit" className="self-end px-4 py-2 font-semibold text-xs rounded-xl shadow-sm flex items-center space-x-1.5 transition-colors cursor-pointer bg-indigo-600 hover:bg-indigo-700 text-white">
                    <Send className="w-3.5 h-3.5" />
                    <span>Send</span>
                  </button>
                </form>
              </div>
            )}
          </div>

          {/* Audit Activity Logs */}
          <div>
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-2 flex items-center space-x-1.5">
              <History className="w-4 h-4 text-slate-500" />
              <span>Activity History</span>
            </h3>
            <div className="border border-slate-200 rounded-xl divide-y divide-slate-100 overflow-hidden text-xs">
              {ticket.activityLogs.map((log) => (
                <div key={log.id} className="p-3 bg-slate-50/50 flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                  <div>
                    <span className="font-bold text-slate-900">{log.action}</span>
                    <span className="text-slate-500 font-normal"> by {log.actor}</span>
                    <p className="text-slate-600 text-[11px] mt-0.5">{log.details}</p>
                  </div>
                  <span className="text-[10px] font-mono text-slate-400 shrink-0">{new Date(log.timestamp).toLocaleTimeString()}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex justify-between items-center text-xs shrink-0">
          <span className="text-slate-500 font-mono">Created: {new Date(ticket.createdAt).toLocaleString()}</span>
          <button onClick={onClose} className="px-4 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-800 font-medium rounded-lg transition-colors">
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

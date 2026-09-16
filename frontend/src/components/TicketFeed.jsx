import React from 'react';
import {
  Filter,
  Search,
  AlertCircle,
  Clock,
  Phone,
  Mail,
  User,
  Sparkles,
  ChevronRight,
  ShieldAlert,
  CheckCircle2,
  HelpCircle,
  Flame,
  ArrowUpDown,
  MessageSquare,
  Download,
  UserCog
} from 'lucide-react';

export const TicketFeed = ({
  tickets,
  filters,
  onFilterChange,
  onSelectTicket,
  onQuickStatusChange,
  currentUser,
}) => {
  // Filter logic
  const filteredTickets = tickets.filter((t) => {
    // Search matching
    const q = filters.searchQuery.toLowerCase().trim();
    if (q) {
      const matchId = t.id.toLowerCase().includes(q);
      const matchName = t.customerName.toLowerCase().includes(q);
      const matchMobile = t.customerMobile.toLowerCase().includes(q);
      const matchSubject = t.subject.toLowerCase().includes(q);
      if (!matchId && !matchName && !matchMobile && !matchSubject) {
        return false;
      }
    }

    // Status filter
    if (filters.status !== 'All' && t.status !== filters.status) {
      return false;
    }

    // Category filter
    if (filters.category !== 'All' && t.category !== filters.category) {
      return false;
    }

    // SLA Breached filter
    if (filters.slaBreachedOnly && !t.slaBreached) {
      return false;
    }

    return true;
  });

  const handleExportCSV = () => {
    if (filteredTickets.length === 0) return;

    const headers = [
      'Ticket ID',
      'Customer Name',
      'Customer Mobile',
      'Category',
      'Subject',
      'Status',
      'Priority',
      'Channel',
      'AI Confidence (%)',
      'Urgency',
      'SLA Breached',
      'Created At',
      'Due By',
      'Assigned To',
      'AI Summary',
      'Description'
    ];

    const escapeCSV = (val) => {
      if (val === null || val === undefined) return '""';
      const str = String(val).replace(/"/g, '""');
      return `"${str}"`;
    };

    const rows = filteredTickets.map((t) => [
      escapeCSV(t.id),
      escapeCSV(t.customerName),
      escapeCSV(t.customerMobile),
      escapeCSV(t.category),
      escapeCSV(t.subject),
      escapeCSV(t.status),
      escapeCSV(t.priority),
      escapeCSV(t.channel),
      escapeCSV(Math.round(t.confidenceScore * 100)),
      escapeCSV(t.urgency),
      escapeCSV(t.slaBreached ? 'Yes' : 'No'),
      escapeCSV(new Date(t.createdAt).toLocaleString()),
      escapeCSV(new Date(t.dueBy).toLocaleString()),
      escapeCSV(t.assignedTo),
      escapeCSV(t.aiSummary),
      escapeCSV(t.description)
    ]);

    const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    link.setAttribute('download', `tickets_report_${timestamp}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'Open':
        return 'bg-blue-50 text-blue-700 border-blue-200/80 font-medium';
      case 'In Progress':
        return 'bg-amber-50 text-amber-700 border-amber-200/80 font-medium';
      case 'Escalated':
        return 'bg-rose-50 text-rose-700 border-rose-300 font-semibold animate-pulse';
      case 'Resolved':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200/80 font-medium';
      case 'Closed':
        return 'bg-slate-200 text-slate-600 border-slate-300 font-medium';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  const getCategoryBadgeClass = (category) => {
    if (category === 'Support') {
      return 'bg-purple-50 text-purple-700 border-purple-200';
    }
    return 'bg-sky-50 text-sky-700 border-sky-200';
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden mb-8">
      {/* Header & Controls Bar */}
      <div className="p-4 sm:p-5 border-b border-slate-100 bg-slate-50/50 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <h2 className="text-base font-bold text-slate-900 font-sans tracking-tight">
              Grievance Ticket Feed
            </h2>
            <span className="px-2 py-0.5 text-xs font-semibold bg-slate-200/80 text-slate-700 rounded-full font-mono">
              {filteredTickets.length} {filteredTickets.length === 1 ? 'ticket' : 'tickets'}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time feed categorized automatically by AI. Click any record for detailed resolution logs.
          </p>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Category Tabs */}
          <div className="flex items-center bg-slate-200/60 p-1 rounded-lg text-xs font-medium text-slate-600">
            <button
              onClick={() => onFilterChange({ category: 'All' })}
              className={`px-2.5 py-1 rounded-md transition-all ${
                filters.category === 'All'
                  ? 'bg-white text-slate-900 shadow-xs font-semibold'
                  : 'hover:text-slate-900'
              }`}
            >
              All Categories
            </button>
            <button
              onClick={() => onFilterChange({ category: 'Support' })}
              className={`px-2.5 py-1 rounded-md transition-all flex items-center space-x-1 ${
                filters.category === 'Support'
                  ? 'bg-white text-purple-700 shadow-xs font-semibold'
                  : 'hover:text-slate-900'
              }`}
            >
              <span>Support</span>
            </button>
            <button
              onClick={() => onFilterChange({ category: 'Enquiry' })}
              className={`px-2.5 py-1 rounded-md transition-all flex items-center space-x-1 ${
                filters.category === 'Enquiry'
                  ? 'bg-white text-sky-700 shadow-xs font-semibold'
                  : 'hover:text-slate-900'
              }`}
            >
              <span>Enquiry</span>
            </button>
          </div>

          {/* Status Select Dropdown */}
          <select
            value={filters.status}
            onChange={(e) =>
              onFilterChange({
                status: e.target.value,
              })
            }
            className="bg-white border border-slate-300 text-slate-700 text-xs font-medium rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="All">All Statuses</option>
            <option value="Open">Open</option>
            <option value="In Progress">In Progress</option>
            <option value="Escalated">Escalated</option>
            <option value="Resolved">Resolved</option>
            <option value="Closed">Closed</option>
          </select>

          {/* SLA Breached Toggle */}
          <button
            onClick={() =>
              onFilterChange({ slaBreachedOnly: !filters.slaBreachedOnly })
            }
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border flex items-center space-x-1.5 transition-all ${
              filters.slaBreachedOnly
                ? 'bg-rose-600 text-white border-rose-600 shadow-xs'
                : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
            }`}
          >
            <Flame
              className={`w-3.5 h-3.5 ${
                filters.slaBreachedOnly ? 'text-white' : 'text-rose-500'
              }`}
            />
            <span>SLA Breached Only</span>
          </button>

          {/* Download CSV Button */}
          <button
            id="btn-export-csv"
            onClick={handleExportCSV}
            disabled={filteredTickets.length === 0}
            title="Export all currently filtered tickets to CSV"
            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-40 disabled:hover:bg-emerald-600 flex items-center space-x-1.5 transition-all shadow-xs cursor-pointer"
          >
            <Download className="w-3.5 h-3.5 text-white" />
            <span>Download CSV</span>
          </button>
        </div>
      </div>

      {/* Ticket List View */}
      {filteredTickets.length === 0 ? (
        <div className="py-16 text-center px-4">
          <div className="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center mx-auto text-slate-400 mb-3">
            <Filter className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-bold text-slate-800">
            No tickets match current filters
          </h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            Try resetting search query, changing status dropdown, or clearing SLA Breach toggle.
          </p>
          <button
            onClick={() =>
              onFilterChange({
                searchQuery: '',
                status: 'All',
                category: 'All',
                slaBreachedOnly: false,
              })
            }
            className="mt-4 px-3.5 py-1.5 text-xs font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-colors"
          >
            Reset All Filters
          </button>
        </div>
      ) : (
        <div className="divide-y divide-slate-100">
          {/* Desktop Table Header */}
          <div className="hidden lg:grid grid-cols-12 gap-4 px-6 py-3 bg-slate-50/80 text-[11px] font-semibold text-slate-500 tracking-wider uppercase border-b border-slate-100">
            <div className="col-span-2 flex items-center space-x-1">
              <span>Ticket ID</span>
            </div>
            <div className="col-span-3">Customer / Mobile</div>
            <div className="col-span-3">Subject & AI Summary</div>
            <div className="col-span-2">Category & Intent</div>
            <div className="col-span-2 text-right">Status & Action</div>
          </div>

          {/* Ticket Rows */}
          {filteredTickets.map((ticket) => (
            <div
              key={ticket.id}
              onClick={() => onSelectTicket(ticket)}
              className="group p-4 sm:p-5 lg:px-6 lg:py-4 hover:bg-indigo-50/30 transition-all cursor-pointer flex flex-col lg:grid lg:grid-cols-12 lg:items-center gap-3 lg:gap-4 border-l-4 border-l-transparent hover:border-l-indigo-600"
            >
              {/* Ticket ID & Channel & SLA Badge */}
              <div className="lg:col-span-2 flex items-center justify-between lg:justify-start lg:space-x-2">
                <div className="flex items-center space-x-2">
                  <span className="font-mono text-xs font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                    {ticket.id}
                  </span>
                  {ticket.channel === 'WhatsApp' && (
                    <span
                      className="px-1.5 py-0.5 text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300 rounded flex items-center space-x-0.5"
                      title="Ingested via WhatsApp Business API"
                    >
                      <MessageSquare className="w-2.5 h-2.5 text-emerald-600" />
                      <span>WA</span>
                    </span>
                  )}
                  {ticket.channel === 'Phone' && (
                    <span
                      className="px-1.5 py-0.5 text-[10px] font-bold bg-indigo-100 text-indigo-800 border border-indigo-300 rounded flex items-center space-x-0.5"
                      title="Logged from a Help Desk phone call"
                    >
                      <Phone className="w-2.5 h-2.5 text-indigo-600" />
                      <span>Call</span>
                    </span>
                  )}
                  {ticket.slaBreached && (
                    <span
                      className="px-1.5 py-0.5 text-[10px] font-bold bg-rose-100 text-rose-700 border border-rose-300 rounded"
                      title="SLA Breached"
                    >
                      SLA
                    </span>
                  )}
                </div>

                <div className="flex items-center space-x-1.5 lg:hidden">
                  <span
                    className={`px-2 py-0.5 text-[10px] uppercase font-bold rounded border ${getStatusBadgeClass(
                      ticket.status
                    )}`}
                  >
                    {ticket.status}
                  </span>
                </div>
              </div>

              {/* Customer Name & Mobile */}
              <div className="lg:col-span-3 flex flex-col">
                <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-900">
                  <User className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <span className="truncate">{ticket.customerName}</span>
                </div>
                <div className="flex items-center space-x-1.5 text-[11px] text-slate-500 font-mono mt-0.5">
                  <Phone className="w-3 h-3 text-slate-400 shrink-0" />
                  <span>{ticket.customerMobile}</span>
                </div>
              </div>

              {/* Subject & Short Description */}
              <div className="lg:col-span-3 flex flex-col">
                <p className="text-xs font-medium text-slate-900 line-clamp-1 group-hover:text-indigo-900 transition-colors">
                  {ticket.subject}
                </p>
                <p className="text-[11px] text-slate-500 line-clamp-1 mt-0.5">
                  {ticket.aiSummary || ticket.description}
                </p>
                <p className="text-[10px] text-slate-400 flex items-center space-x-1 mt-0.5">
                  <UserCog className="w-2.5 h-2.5" />
                  <span>{ticket.assignedToName ? `Assigned: ${ticket.assignedToName}` : 'Unassigned'}</span>
                  {ticket.sectionName && (
                    <span className="ml-1.5 inline-flex items-center px-1.5 py-0.5 text-[9px] font-semibold rounded border bg-violet-50 text-violet-700 border-violet-200">
                      {ticket.sectionName}
                    </span>
                  )}
                </p>
              </div>

              {/* Category label & AI Confidence Score */}
              <div className="lg:col-span-2 flex items-center space-x-2">
                <span
                  className={`inline-flex items-center px-2.5 py-1 text-xs font-semibold rounded-md border ${getCategoryBadgeClass(
                    ticket.category
                  )}`}
                >
                  {ticket.category === 'Support' ? (
                    <AlertCircle className="w-3 h-3 mr-1" />
                  ) : (
                    <HelpCircle className="w-3 h-3 mr-1" />
                  )}
                  {ticket.category}
                </span>

                {/* AI Confidence Indicator */}
                <div
                  className="flex items-center text-[10px] font-mono text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200"
                  title="Gemini Webhook Classification Confidence"
                >
                  <Sparkles className="w-2.5 h-2.5 text-indigo-500 mr-1" />
                  <span>{Math.round(ticket.confidenceScore * 100)}%</span>
                </div>
              </div>

              {/* Status Pill & Action */}
              <div className="lg:col-span-2 flex items-center justify-between lg:justify-end space-x-2 mt-2 lg:mt-0 pt-2 lg:pt-0 border-t lg:border-t-0 border-slate-100">
                <div className="hidden lg:block">
                  <span
                    className={`inline-flex items-center px-2.5 py-1 text-xs rounded-full border ${getStatusBadgeClass(
                      ticket.status
                    )}`}
                  >
                    {ticket.status}
                  </span>
                </div>

                <div className="flex items-center space-x-1.5 text-xs text-indigo-600 font-medium group-hover:translate-x-1 transition-transform ml-auto">
                  <span>Details</span>
                  <ChevronRight className="w-4 h-4" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

import React, { useState, useMemo } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
} from 'recharts';
import {
  BarChart3,
  TrendingUp,
  PieChart as PieIcon,
  Calendar,
  Layers,
  Sparkles,
  TicketCheck,
  Clock,
  AlertTriangle,
  CheckCircle2,
  Filter,
  User,
  Radio
} from 'lucide-react';

const CATEGORY_COLORS = {
  Support: '#f43f5e', // rose-500
  Enquiry: '#3b82f6', // blue-500
  Billing: '#eab308', // yellow-500
  Technical: '#a855f7', // purple-500
  General: '#64748b', // slate-500
};

const STATUS_COLORS = {
  Open: '#3b82f6', // blue
  'In Progress': '#eab308', // amber
  Resolved: '#10b981', // emerald
  Escalated: '#f43f5e', // rose
  Closed: '#64748b', // slate
};

const CHANNEL_COLORS = {
  WhatsApp: '#10b981', // emerald
  Webmail: '#0284c7', // sky
  Webhook: '#a855f7', // purple
  Manual: '#6366f1', // indigo
};

export const TicketAnalytics = ({
  tickets,
  currentUser,
}) => {
  const [timeRange, setTimeRange] = useState('all');
  const [selectedChannel, setSelectedChannel] = useState('all');

  // Filter tickets by range and channel
  const filteredTickets = useMemo(() => {
    let result = [...tickets];

    if (selectedChannel !== 'all') {
      result = result.filter(
        (t) => t.channel?.toLowerCase() === selectedChannel.toLowerCase()
      );
    }

    if (timeRange !== 'all') {
      const now = new Date();
      const cutoffDays = timeRange === '7days' ? 7 : 30;
      const cutoff = new Date(now.getTime() - cutoffDays * 24 * 3600 * 1000);
      result = result.filter((t) => new Date(t.createdAt) >= cutoff);
    }

    return result;
  }, [tickets, timeRange, selectedChannel]);

  // Metric summaries
  const totalCount = filteredTickets.length;
  const openCount = filteredTickets.filter((t) => t.status === 'Open').length;
  const resolvedCount = filteredTickets.filter((t) => t.status === 'Resolved' || t.status === 'Closed').length;
  const escalatedCount = filteredTickets.filter(
    (t) => t.status === 'Escalated' || t.slaBreached
  ).length;

  const avgConfidence = useMemo(() => {
    if (totalCount === 0) return 0;
    const sum = filteredTickets.reduce((acc, t) => acc + (t.confidenceScore || 0.9), 0);
    return Math.round((sum / totalCount) * 100);
  }, [filteredTickets, totalCount]);

  // Chart 1 Data: Tickets Created Over Time (grouped by date)
  const timeTrendData = useMemo(() => {
    const map = {};

    // Sort tickets chronologically
    const sorted = [...filteredTickets].sort(
      (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
    );

    if (sorted.length === 0) {
      // Fallback timeline for preview if empty
      const today = new Date();
      for (let i = 6; i >= 0; i--) {
        const d = new Date(today.getTime() - i * 24 * 3600 * 1000);
        const label = d.toLocaleDateString([], { month: 'short', day: 'numeric' });
        map[label] = { date: label, fullDate: d.toISOString(), Support: 0, Enquiry: 0, Total: 0 };
      }
    } else {
      sorted.forEach((t) => {
        const d = new Date(t.createdAt);
        const label = d.toLocaleDateString([], { month: 'short', day: 'numeric' });
        if (!map[label]) {
          map[label] = {
            date: label,
            fullDate: d.toISOString(),
            Support: 0,
            Enquiry: 0,
            Total: 0,
          };
        }
        const cat = t.category === 'Enquiry' ? 'Enquiry' : 'Support';
        map[label][cat] += 1;
        map[label].Total += 1;
      });
    }

    return Object.values(map);
  }, [filteredTickets]);

  // Chart 2 Data: Distribution by Category
  const categoryData = useMemo(() => {
    const counts = {};
    filteredTickets.forEach((t) => {
      const cat = t.category || 'General';
      counts[cat] = (counts[cat] || 0) + 1;
    });

    if (Object.keys(counts).length === 0) {
      return [
        { name: 'Support', value: 0 },
        { name: 'Enquiry', value: 0 },
      ];
    }

    return Object.entries(counts).map(([name, value]) => ({
      name,
      value,
    }));
  }, [filteredTickets]);

  // Chart 3 Data: Status Distribution Bar Chart
  const statusData = useMemo(() => {
    const counts = {
      Open: 0,
      'In Progress': 0,
      Resolved: 0,
      Escalated: 0,
      Closed: 0,
    };

    filteredTickets.forEach((t) => {
      const st = t.status || 'Open';
      counts[st] = (counts[st] || 0) + 1;
    });

    return Object.entries(counts).map(([status, count]) => ({
      status,
      count,
    }));
  }, [filteredTickets]);

  // Chart 4 Data: Channel Distribution
  const channelData = useMemo(() => {
    const counts = {};
    filteredTickets.forEach((t) => {
      const ch = t.channel || 'Manual';
      counts[ch] = (counts[ch] || 0) + 1;
    });

    return Object.entries(counts).map(([channel, count]) => ({
      channel,
      count,
    }));
  }, [filteredTickets]);

  // Custom Tooltip Component for Dark Theme
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-slate-950 border border-slate-800 p-3 rounded-xl shadow-2xl text-xs space-y-1 z-50">
          <p className="font-bold text-white mb-1 border-b border-slate-800 pb-1">{label}</p>
          {payload.map((entry, index) => (
            <div key={`item-${index}`} className="flex items-center justify-between gap-4">
              <span className="flex items-center space-x-1.5" style={{ color: entry.color || entry.fill }}>
                <span
                  className="w-2 h-2 rounded-full inline-block"
                  style={{ backgroundColor: entry.color || entry.fill }}
                />
                <span className="text-slate-300 font-medium">{entry.name}:</span>
              </span>
              <span className="font-bold font-mono text-white">{entry.value}</span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Control Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex items-center space-x-4">
          <div className="w-12 h-12 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 text-indigo-400 flex items-center justify-center shrink-0 shadow-lg shadow-indigo-600/10">
            <BarChart3 className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold text-white tracking-tight">
                Ticket Analytics & Visual Trends
              </h1>
              <span className="bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-[10px] font-mono px-2 py-0.5 rounded font-semibold uppercase">
                Recharts Engine
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1 flex items-center space-x-2">
              <User className="w-3.5 h-3.5 text-slate-500" />
              <span>
                Showing metrics for <strong>{currentUser?.name || 'Logged-In User'}</strong> ({currentUser?.role || 'User'})
              </span>
            </p>
          </div>
        </div>

        {/* Controls: Time Filter & Channel Filter */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Time Range Selector */}
          <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800">
            <button
              onClick={() => setTimeRange('all')}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                timeRange === 'all'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              All Time
            </button>
            <button
              onClick={() => setTimeRange('30days')}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                timeRange === '30days'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Last 30 Days
            </button>
            <button
              onClick={() => setTimeRange('7days')}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                timeRange === '7days'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Last 7 Days
            </button>
          </div>

          {/* Channel Dropdown */}
          <div className="relative">
            <select
              value={selectedChannel}
              onChange={(e) => setSelectedChannel(e.target.value)}
              className="bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded-xl px-3 py-2 pr-8 focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
            >
              <option value="all">All Ingestion Channels</option>
              <option value="whatsapp">WhatsApp Channel</option>
              <option value="webmail">Webmail Mailboxes</option>
              <option value="webhook">Direct Webhook</option>
            </select>
          </div>
        </div>
      </div>

      {/* Metric Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-lg flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Total Ingested Tickets
            </p>
            <div className="text-2xl font-bold text-white mt-1 font-mono">{totalCount}</div>
            <p className="text-[10px] text-slate-500 mt-1">Across active workspace</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center shrink-0">
            <TicketCheck className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-lg flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Open & Active
            </p>
            <div className="text-2xl font-bold text-sky-400 mt-1 font-mono">{openCount}</div>
            <p className="text-[10px] text-sky-500 mt-1">Awaiting resolution</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-sky-500/20 text-sky-400 border border-sky-500/30 flex items-center justify-center shrink-0">
            <Clock className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-lg flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Resolved & Closed
            </p>
            <div className="text-2xl font-bold text-emerald-400 mt-1 font-mono">{resolvedCount}</div>
            <p className="text-[10px] text-emerald-500 mt-1">SLA fulfilled successfully</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-lg flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              AI Intent Confidence
            </p>
            <div className="text-2xl font-bold text-amber-300 mt-1 font-mono">{avgConfidence}%</div>
            <p className="text-[10px] text-amber-500 mt-1">Gemini routing accuracy</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center justify-center shrink-0">
            <Sparkles className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Main Charts Row 1: Line / Area Chart + Pie Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Chart 1: Tickets Created Over Time (8 cols) */}
        <div className="lg:col-span-8 bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center space-x-2">
              <TrendingUp className="w-5 h-5 text-indigo-400" />
              <div>
                <h3 className="text-sm font-bold text-white">Tickets Created Over Time</h3>
                <p className="text-[11px] text-slate-400">
                  Daily incoming grievance volume segmented by AI intent category
                </p>
              </div>
            </div>
            <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-2 py-1 rounded">
              Trend Analysis
            </span>
          </div>

          <div className="h-72 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={timeTrendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorSupport" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#f43f5e" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="colorEnquiry" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="date" stroke="#64748b" tick={{ fontSize: 11 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  wrapperStyle={{ paddingTop: '10px', fontSize: '11px', color: '#94a3b8' }}
                />
                <Area
                  type="monotone"
                  dataKey="Support"
                  name="Support Grievances"
                  stroke="#f43f5e"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorSupport)"
                />
                <Area
                  type="monotone"
                  dataKey="Enquiry"
                  name="Enquiries / Requests"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorEnquiry)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Distribution by Category Pie Chart (4 cols) */}
        <div className="lg:col-span-4 bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center space-x-2">
              <PieIcon className="w-5 h-5 text-indigo-400" />
              <div>
                <h3 className="text-sm font-bold text-white">Distribution by Category</h3>
                <p className="text-[11px] text-slate-400">Share of ticket classifications</p>
              </div>
            </div>
          </div>

          <div className="h-64 w-full flex items-center justify-center">
            {totalCount === 0 ? (
              <div className="text-xs text-slate-500 text-center py-10">No tickets found for selected filter</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={categoryData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={85}
                    paddingAngle={4}
                    dataKey="value"
                  >
                    {categoryData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={CATEGORY_COLORS[entry.name] || '#6366f1'}
                        stroke="#0f172a"
                        strokeWidth={2}
                      />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: '11px', color: '#94a3b8' }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* Main Charts Row 2: Status Breakdown & Ingestion Channel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Chart 3: Ticket Status Breakdown Bar Chart (6 cols) */}
        <div className="lg:col-span-6 bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center space-x-2">
              <Layers className="w-5 h-5 text-sky-400" />
              <div>
                <h3 className="text-sm font-bold text-white">Tickets by Lifecycle Status</h3>
                <p className="text-[11px] text-slate-400">Open, In Progress, Resolved & Escalated</p>
              </div>
            </div>
          </div>

          <div className="h-60 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={statusData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="status" stroke="#64748b" tick={{ fontSize: 11 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="count" name="Tickets" radius={[6, 6, 0, 0]}>
                  {statusData.map((entry, index) => (
                    <Cell
                      key={`cell-st-${index}`}
                      fill={STATUS_COLORS[entry.status] || '#3b82f6'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 4: Ingestion Channel Breakdown Bar Chart (6 cols) */}
        <div className="lg:col-span-6 bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center space-x-2">
              <Radio className="w-5 h-5 text-emerald-400" />
              <div>
                <h3 className="text-sm font-bold text-white">Ingestion Channel Distribution</h3>
                <p className="text-[11px] text-slate-400">
                  WhatsApp vs Webmail Mailboxes vs Direct Webhook
                </p>
              </div>
            </div>
          </div>

          <div className="h-60 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={channelData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="channel" stroke="#64748b" tick={{ fontSize: 11 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="count" name="Tickets" radius={[6, 6, 0, 0]}>
                  {channelData.map((entry, index) => (
                    <Cell
                      key={`cell-ch-${index}`}
                      fill={CHANNEL_COLORS[entry.channel] || '#10b981'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};

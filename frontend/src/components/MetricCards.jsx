import React from 'react';
import {
  Inbox,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ArrowUpRight,
  TrendingUp,
  Filter
} from 'lucide-react';

export const MetricCards = ({
  openCount,
  escalatedCount,
  resolvedCount,
  totalCount,
  activeFilter,
  slaBreachedOnly,
  onSelectFilter,
}) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
      {/* 1. Open Tickets */}
      <div
        onClick={() => onSelectFilter('Open', false)}
        className={`group relative overflow-hidden rounded-2xl border p-5 transition-all cursor-pointer ${
          activeFilter === 'Open' && !slaBreachedOnly
            ? 'bg-slate-900 text-white border-indigo-500/80 shadow-xl shadow-indigo-500/10 ring-2 ring-indigo-500/30'
            : 'bg-white hover:bg-slate-50/90 text-slate-900 border-slate-200/90 shadow-sm hover:border-indigo-300 hover:shadow-md'
        }`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3.5">
            <div
              className={`p-3 rounded-xl transition-all ${
                activeFilter === 'Open' && !slaBreachedOnly
                  ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                  : 'bg-indigo-50 text-indigo-600 border border-indigo-100'
              }`}
            >
              <Inbox className="w-5 h-5" />
            </div>
            <div>
              <p
                className={`text-[11px] font-bold uppercase tracking-wider ${
                  activeFilter === 'Open' && !slaBreachedOnly
                    ? 'text-indigo-300'
                    : 'text-slate-500'
                }`}
              >
                Open Queue
              </p>
              <h3 className="text-2xl font-black font-mono tracking-tight mt-0.5">
                {openCount}
              </h3>
            </div>
          </div>
          <div className="text-right">
            <span
              className={`inline-flex items-center text-[10px] font-bold px-2.5 py-1 rounded-full ${
                activeFilter === 'Open' && !slaBreachedOnly
                  ? 'bg-indigo-400/20 text-indigo-200 border border-indigo-400/30'
                  : 'bg-indigo-50 text-indigo-700 border border-indigo-100'
              }`}
            >
              <Clock className="w-3 h-3 mr-1 text-indigo-500" />
              Active
            </span>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
          <span
            className={
              activeFilter === 'Open' && !slaBreachedOnly
                ? 'text-slate-400'
                : 'text-slate-500'
            }
          >
            {totalCount > 0
              ? `${Math.round((openCount / totalCount) * 100)}% of total load`
              : '0% of total load'}
          </span>
          <span
            className={`font-semibold text-xs flex items-center group-hover:translate-x-1 transition-transform ${
              activeFilter === 'Open' && !slaBreachedOnly
                ? 'text-indigo-400'
                : 'text-indigo-600'
            }`}
          >
            Filter Open <ArrowUpRight className="w-3.5 h-3.5 ml-0.5" />
          </span>
        </div>
      </div>

      {/* 2. Escalated (SLA Breached) */}
      <div
        onClick={() => onSelectFilter('All', true)}
        className={`group relative overflow-hidden rounded-2xl border p-5 transition-all cursor-pointer ${
          slaBreachedOnly
            ? 'bg-slate-900 text-white border-rose-500/80 shadow-xl shadow-rose-500/10 ring-2 ring-rose-500/30'
            : 'bg-white hover:bg-slate-50/90 text-slate-900 border-slate-200/90 shadow-sm hover:border-rose-300 hover:shadow-md'
        }`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3.5">
            <div
              className={`p-3 rounded-xl transition-all ${
                slaBreachedOnly
                  ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                  : 'bg-rose-50 text-rose-600 border border-rose-100'
              }`}
            >
              <AlertTriangle className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <p
                className={`text-[11px] font-bold uppercase tracking-wider ${
                  slaBreachedOnly ? 'text-rose-300' : 'text-slate-500'
                }`}
              >
                SLA Breached
              </p>
              <h3 className="text-2xl font-black font-mono tracking-tight mt-0.5 text-rose-600 dark:text-rose-400">
                {escalatedCount}
              </h3>
            </div>
          </div>
          <div className="text-right">
            <span
              className={`inline-flex items-center text-[10px] font-bold px-2.5 py-1 rounded-full ${
                slaBreachedOnly
                  ? 'bg-rose-500/20 text-rose-200 border border-rose-400/30'
                  : 'bg-rose-50 text-rose-700 border border-rose-100'
              }`}
            >
              Needs Immediate Action
            </span>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
          <span
            className={slaBreachedOnly ? 'text-slate-400' : 'text-slate-500'}
          >
            Escalation triggers active
          </span>
          <span
            className={`font-semibold text-xs flex items-center group-hover:translate-x-1 transition-transform ${
              slaBreachedOnly ? 'text-rose-400' : 'text-rose-600'
            }`}
          >
            Filter Breached <ArrowUpRight className="w-3.5 h-3.5 ml-0.5" />
          </span>
        </div>
      </div>

      {/* 3. Resolved */}
      <div
        onClick={() => onSelectFilter('Resolved', false)}
        className={`group relative overflow-hidden rounded-2xl border p-5 transition-all cursor-pointer ${
          activeFilter === 'Resolved' && !slaBreachedOnly
            ? 'bg-slate-900 text-white border-emerald-500/80 shadow-xl shadow-emerald-500/10 ring-2 ring-emerald-500/30'
            : 'bg-white hover:bg-slate-50/90 text-slate-900 border-slate-200/90 shadow-sm hover:border-emerald-300 hover:shadow-md'
        }`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3.5">
            <div
              className={`p-3 rounded-xl transition-all ${
                activeFilter === 'Resolved' && !slaBreachedOnly
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  : 'bg-emerald-50 text-emerald-600 border border-emerald-100'
              }`}
            >
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div>
              <p
                className={`text-[11px] font-bold uppercase tracking-wider ${
                  activeFilter === 'Resolved' && !slaBreachedOnly
                    ? 'text-emerald-300'
                    : 'text-slate-500'
                }`}
              >
                Resolved
              </p>
              <h3 className="text-2xl font-black font-mono tracking-tight mt-0.5 text-emerald-600 dark:text-emerald-400">
                {resolvedCount}
              </h3>
            </div>
          </div>
          <div className="text-right">
            <span
              className={`inline-flex items-center text-[10px] font-bold px-2.5 py-1 rounded-full ${
                activeFilter === 'Resolved' && !slaBreachedOnly
                  ? 'bg-emerald-500/20 text-emerald-200 border border-emerald-400/30'
                  : 'bg-emerald-50 text-emerald-700 border border-emerald-100'
              }`}
            >
              <TrendingUp className="w-3 h-3 mr-1 text-emerald-500" />
              Completed
            </span>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
          <span
            className={
              activeFilter === 'Resolved' && !slaBreachedOnly
                ? 'text-slate-400'
                : 'text-slate-500'
            }
          >
            Closed customer cases
          </span>
          <span
            className={`font-semibold text-xs flex items-center group-hover:translate-x-1 transition-transform ${
              activeFilter === 'Resolved' && !slaBreachedOnly
                ? 'text-emerald-400'
                : 'text-emerald-600'
            }`}
          >
            Filter Resolved <ArrowUpRight className="w-3.5 h-3.5 ml-0.5" />
          </span>
        </div>
      </div>
    </div>
  );
};

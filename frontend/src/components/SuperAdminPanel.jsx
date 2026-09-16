import React, { useState, useEffect } from 'react';
import { Building2, Users, TicketCheck, ShieldOff, ShieldCheck, RefreshCw } from 'lucide-react';
import { fetchOrganizations, updateOrganizationStatus } from '../utils/storage';

export const SuperAdminPanel = ({ showToast }) => {
  const [organizations, setOrganizations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState(null);

  const load = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await fetchOrganizations();
      setOrganizations(data.organizations || []);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to load organizations.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleToggleStatus = async (org) => {
    const next = org.status === 'Active' ? 'Suspended' : 'Active';
    try {
      await updateOrganizationStatus(org.id, next);
      await load();
      showToast?.(`${org.name} is now ${next}.`);
    } catch (err) {
      showToast?.(`Failed: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl border border-slate-200/90 shadow-xs p-6 sm:p-8">
        <div className="flex items-center justify-between pb-6 border-b border-slate-100">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-slate-900 text-white flex items-center justify-center shadow-md">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">Platform Organizations</h2>
              <p className="text-xs text-slate-500 mt-0.5">Oversight only — Super Admin does not see any organization's tickets.</p>
            </div>
          </div>
          <button onClick={load} className="p-2 text-slate-500 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer" title="Refresh">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {errorMsg && <div className="mt-4 p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs">{errorMsg}</div>}

        <div className="mt-6 divide-y divide-slate-100">
          {organizations.length === 0 && !loading ? (
            <div className="py-12 text-center text-xs text-slate-500">No organizations have registered yet.</div>
          ) : (
            organizations.map((org) => (
              <div key={org.id} className="py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-bold text-slate-900">{org.name}</span>
                    <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-md border ${
                      org.status === 'Active' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-rose-50 text-rose-700 border-rose-200'
                    }`}>
                      {org.status}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                    /{org.slug} &bull; registered {org.createdAt ? new Date(org.createdAt).toLocaleDateString() : '—'}
                  </div>
                </div>

                <div className="flex items-center space-x-4">
                  <span className="flex items-center space-x-1.5 text-xs text-slate-600">
                    <Users className="w-3.5 h-3.5 text-slate-400" />
                    <span>{org.userCount} users</span>
                  </span>
                  <span className="flex items-center space-x-1.5 text-xs text-slate-600">
                    <TicketCheck className="w-3.5 h-3.5 text-slate-400" />
                    <span>{org.ticketCount} tickets</span>
                  </span>
                  <button
                    onClick={() => handleToggleStatus(org)}
                    className={`px-3 py-1.5 rounded-lg text-[11px] font-semibold border flex items-center space-x-1.5 transition-all cursor-pointer ${
                      org.status === 'Active'
                        ? 'bg-white text-rose-600 border-rose-200 hover:bg-rose-50'
                        : 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
                    }`}
                  >
                    {org.status === 'Active' ? <ShieldOff className="w-3.5 h-3.5" /> : <ShieldCheck className="w-3.5 h-3.5" />}
                    <span>{org.status === 'Active' ? 'Suspend' : 'Reactivate'}</span>
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

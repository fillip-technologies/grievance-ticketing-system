import React, { useState, useEffect } from 'react';
import {
  Users,
  UserPlus,
  Mail,
  Phone,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Copy,
  KeyRound,
  Gavel,
  Wrench,
  Pencil,
  Trash2,
  Save,
  X,
  Layers,
  Plus,
} from 'lucide-react';
import { createTeamMember, updateTeamMember, deleteTeamMember, fetchSections, createSection, updateSection, deleteSection } from '../utils/storage';

const ROLE_META = {
  Resolver: { label: 'Resolver', icon: Wrench, cls: 'bg-indigo-50 text-indigo-700 border-indigo-200' },
  EscalationAuthority: { label: 'Escalation Authority', icon: Gavel, cls: 'bg-amber-50 text-amber-700 border-amber-200' },
};

const NO_SECTION = '';

export const TeamManager = ({ team, onTeamChanged, showToast }) => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [mobile, setMobile] = useState('');
  const [role, setRole] = useState('Resolver');
  const [escalationLevel, setEscalationLevel] = useState(1);
  const [sectionId, setSectionId] = useState(NO_SECTION);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [lastCreated, setLastCreated] = useState(null);
  const [copied, setCopied] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editRole, setEditRole] = useState('Resolver');
  const [editEscalationLevel, setEditEscalationLevel] = useState(1);
  const [editSectionId, setEditSectionId] = useState(NO_SECTION);
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [removingId, setRemovingId] = useState(null);

  // ---------- Sections ----------
  const [sections, setSections] = useState([]);
  const [sectionsLoading, setSectionsLoading] = useState(true);
  const [showSectionForm, setShowSectionForm] = useState(false);
  const [sectionName, setSectionName] = useState('');
  const [sectionDescription, setSectionDescription] = useState('');
  const [sectionSubmitting, setSectionSubmitting] = useState(false);
  const [sectionError, setSectionError] = useState(null);
  const [editingSectionId, setEditingSectionId] = useState(null);
  const [editSectionName, setEditSectionName] = useState('');
  const [editSectionDescription, setEditSectionDescription] = useState('');

  const loadSections = async () => {
    setSectionsLoading(true);
    try {
      const data = await fetchSections();
      setSections(data.sections || []);
    } catch (err) {
      showToast?.(`Failed to load departments: ${err.message}`);
    } finally {
      setSectionsLoading(false);
    }
  };

  useEffect(() => {
    loadSections();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCreateSection = async (e) => {
    e.preventDefault();
    setSectionError(null);
    if (!sectionName.trim()) {
      setSectionError('Department name is required.');
      return;
    }
    setSectionSubmitting(true);
    try {
      await createSection({ name: sectionName.trim(), description: sectionDescription.trim() });
      setSectionName('');
      setSectionDescription('');
      setShowSectionForm(false);
      await loadSections();
      showToast?.(`Department "${sectionName.trim()}" created.`);
    } catch (err) {
      setSectionError(err.message || 'Failed to create department.');
    } finally {
      setSectionSubmitting(false);
    }
  };

  const handleStartEditSection = (section) => {
    setEditingSectionId(section.id);
    setEditSectionName(section.name);
    setEditSectionDescription(section.description || '');
  };

  const handleSaveSectionEdit = async (section) => {
    try {
      await updateSection(section.id, { name: editSectionName.trim(), description: editSectionDescription.trim() });
      setEditingSectionId(null);
      await loadSections();
      showToast?.(`Department "${editSectionName.trim()}" updated.`);
    } catch (err) {
      showToast?.(`Failed: ${err.message}`);
    }
  };

  const handleToggleSectionActive = async (section) => {
    try {
      await updateSection(section.id, { isActive: !section.isActive });
      await loadSections();
      showToast?.(`Department "${section.name}" ${section.isActive ? 'deactivated' : 'reactivated'}.`);
    } catch (err) {
      showToast?.(`Failed: ${err.message}`);
    }
  };

  const handleDeleteSection = async (section) => {
    if (!confirm(`Delete the "${section.name}" department? Resolvers assigned to it move to the general pool, and its tickets keep their history but lose the department tag. This can't be undone.`)) return;
    try {
      await deleteSection(section.id);
      await loadSections();
      await onTeamChanged();
      showToast?.(`Department "${section.name}" deleted.`);
    } catch (err) {
      showToast?.(`Failed: ${err.message}`);
    }
  };

  const resolverCount = team.filter((m) => m.role === 'Resolver').length;
  const authorityCount = team.filter((m) => m.role === 'EscalationAuthority').length;

  const activeResolverCount = team.filter((m) => m.role === 'Resolver' && m.isActive).length;
  const activeAuthorityTiers = new Set(
    team.filter((m) => m.role === 'EscalationAuthority' && m.isActive).map((m) => m.escalationLevel || 1)
  );
  const readinessWarnings = [];
  if (activeResolverCount === 0) {
    readinessWarnings.push('No active Resolver — new complaints will go unassigned until you add or reactivate one.');
  }
  if (!activeAuthorityTiers.has(1)) {
    readinessWarnings.push('No active Escalation Authority at Tier 1 — breached tickets will be flagged for you instead of reaching a resolver automatically.');
  }

  const handleCreate = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    if (!name.trim() || !email.trim()) {
      setErrorMsg('Name and email are required.');
      return;
    }
    setSubmitting(true);
    try {
      const data = await createTeamMember({
        name: name.trim(),
        email: email.trim(),
        mobile: mobile.trim(),
        role,
        escalationLevel: role === 'EscalationAuthority' ? Number(escalationLevel) : 1,
        sectionId: role === 'Resolver' && sectionId ? sectionId : null,
      });
      setLastCreated({ ...data.member, temporaryPassword: data.temporaryPassword, inviteEmailSent: data.inviteEmailSent });
      setName('');
      setEmail('');
      setMobile('');
      setEscalationLevel(1);
      setSectionId(NO_SECTION);
      await Promise.all([onTeamChanged(), loadSections()]);
      showToast(`${data.member.name} added as ${ROLE_META[data.member.role]?.label || data.member.role}.`);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to add team member.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleActive = async (member) => {
    try {
      await updateTeamMember(member.id, { isActive: !member.isActive });
      await Promise.all([onTeamChanged(), loadSections()]);
      showToast(`${member.name} ${member.isActive ? 'deactivated' : 'reactivated'}.`);
    } catch (err) {
      showToast(`Failed: ${err.message}`);
    }
  };

  const handleStartEdit = (member) => {
    setEditingId(member.id);
    setEditRole(member.role);
    setEditEscalationLevel(member.escalationLevel || 1);
    setEditSectionId(member.sectionId || NO_SECTION);
  };

  const handleCancelEdit = () => {
    setEditingId(null);
  };

  const handleSaveEdit = async (member) => {
    setEditSubmitting(true);
    try {
      await updateTeamMember(member.id, {
        role: editRole,
        escalationLevel: editRole === 'EscalationAuthority' ? Number(editEscalationLevel) : 1,
        sectionId: editRole === 'Resolver' && editSectionId ? editSectionId : null,
        clearSection: editRole !== 'Resolver' || !editSectionId,
      });
      setEditingId(null);
      await Promise.all([onTeamChanged(), loadSections()]);
      showToast(
        editRole === member.role
          ? `${member.name} updated.`
          : `${member.name} moved from ${ROLE_META[member.role]?.label || member.role} to ${ROLE_META[editRole]?.label || editRole}.`
      );
    } catch (err) {
      showToast(`Failed: ${err.message}`);
    } finally {
      setEditSubmitting(false);
    }
  };

  const handleRemove = async (member) => {
    if (!confirm(`Remove ${member.name} from the team? Any tickets currently assigned to them will become unassigned. This can't be undone — they'll need to be re-added (and re-invited) to come back.`)) return;
    setRemovingId(member.id);
    try {
      await deleteTeamMember(member.id);
      await Promise.all([onTeamChanged(), loadSections()]);
      showToast(`${member.name} removed from the team.`);
    } catch (err) {
      showToast(`Failed: ${err.message}`);
    } finally {
      setRemovingId(null);
    }
  };

  const handleCopyPassword = () => {
    if (!lastCreated) return;
    navigator.clipboard.writeText(lastCreated.temporaryPassword);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {readinessWarnings.length > 0 && (
        <div className="bg-amber-50 border border-amber-300 rounded-2xl p-4 flex items-start gap-3">
          <ShieldAlert className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-bold text-amber-900">Escalation ladder needs attention</p>
            <ul className="mt-1 text-xs text-amber-800 list-disc list-inside space-y-0.5">
              {readinessWarnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </div>
        </div>
      )}

      <div className="bg-white rounded-2xl border border-slate-200/90 shadow-xs p-6 sm:p-8">
        <div className="flex items-center space-x-3 pb-6 border-b border-slate-100">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-md shadow-indigo-600/20">
            <Users className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-900">Team Management</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Resolvers receive new tickets via round-robin auto-assignment. Escalation Authorities
              receive tickets that breach their SLA window.
            </p>
          </div>
        </div>

        {/* Add member form */}
        <form onSubmit={handleCreate} className={`grid grid-cols-1 sm:grid-cols-2 ${role === 'EscalationAuthority' ? 'lg:grid-cols-6' : 'lg:grid-cols-6'} gap-3 mt-6`}>
          <div className="lg:col-span-1">
            <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wider mb-1">Full Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Priya Nair" className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          </div>
          <div className="lg:col-span-1">
            <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wider mb-1">Email</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="priya@company.com" className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          </div>
          <div className="lg:col-span-1">
            <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wider mb-1">Mobile (optional)</label>
            <input value={mobile} onChange={(e) => setMobile(e.target.value)} placeholder="+91 90000 00000" className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          </div>
          <div className="lg:col-span-1">
            <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wider mb-1">Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500">
              <option value="Resolver">Resolver</option>
              <option value="EscalationAuthority">Escalation Authority</option>
            </select>
          </div>
          {role === 'EscalationAuthority' ? (
            <div className="lg:col-span-1">
              <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wider mb-1">Ladder Tier</label>
              <select
                value={escalationLevel}
                onChange={(e) => setEscalationLevel(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {[1, 2, 3, 4].map((lvl) => (
                  <option key={lvl} value={lvl}>Tier {lvl}{lvl === 1 ? ' (first-line)' : ''}</option>
                ))}
              </select>
            </div>
          ) : (
            <div className="lg:col-span-1">
              <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wider mb-1">Department (optional)</label>
              <select
                value={sectionId}
                onChange={(e) => setSectionId(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value={NO_SECTION}>General pool</option>
                {sections.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
          )}
          <div className="lg:col-span-1 flex items-end">
            <button type="submit" disabled={submitting} className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white font-semibold text-xs rounded-xl shadow-md transition-all flex items-center justify-center space-x-1.5 cursor-pointer">
              <UserPlus className="w-3.5 h-3.5" />
              <span>{submitting ? 'Adding...' : 'Add Member'}</span>
            </button>
          </div>
        </form>
        {role === 'Resolver' && (
          <p className="mt-2 text-[11px] text-slate-500">
            A Resolver assigned to a department only receives tickets the AI routes to that department (auto-assigned
            regardless of the org's general auto-assign setting) — not generic Support/Enquiry tickets.
          </p>
        )}
        {role === 'EscalationAuthority' && (
          <p className="mt-2 text-[11px] text-slate-500">
            An unresolved ticket auto-escalates to Tier 1, then — if still unresolved after the org's
            re-escalation window — climbs to Tier 2, and so on, if higher tiers are configured.
          </p>
        )}

        {errorMsg && (
          <div className="mt-3 p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs flex items-start space-x-2">
            <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}

        {lastCreated && (
          <div className="mt-4 p-4 bg-indigo-50 border border-indigo-200 rounded-xl text-xs text-indigo-900 space-y-2">
            <div className="flex items-center space-x-2 font-semibold">
              <KeyRound className="w-4 h-4 text-indigo-600" />
              <span>{lastCreated.name} was added.</span>
            </div>
            {lastCreated.inviteEmailSent ? (
              <p className="text-indigo-700">An invite email with login credentials was sent to {lastCreated.email}.</p>
            ) : (
              <>
                <p className="text-indigo-700">
                  SMTP isn't configured yet, so the invite email wasn't sent — share this temporary password manually:
                </p>
                <div className="flex items-center space-x-2 bg-white border border-indigo-200 rounded-lg px-3 py-2 font-mono">
                  <span className="flex-1">{lastCreated.temporaryPassword}</span>
                  <button type="button" onClick={handleCopyPassword} className="text-indigo-600 hover:text-indigo-800 cursor-pointer">
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                </div>
                {copied && <span className="text-emerald-600 text-[11px]">Copied!</span>}
              </>
            )}
          </div>
        )}
      </div>

      {/* Departments */}
      <div className="bg-white rounded-2xl border border-slate-200/90 shadow-xs p-6 sm:p-8">
        <div className="flex items-center justify-between pb-6 border-b border-slate-100">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-violet-600 text-white flex items-center justify-center shadow-md shadow-violet-600/20">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">Departments</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Custom routing beyond Support/Enquiry — e.g. "Sales" or "HR". A message the AI matches to a
                department auto-assigns to that department's Resolver(s), even if general auto-assignment is off.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowSectionForm((v) => !v)}
            className="px-3 py-2 bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold rounded-xl shadow-xs flex items-center space-x-1.5 transition-colors cursor-pointer shrink-0"
          >
            {showSectionForm ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
            <span>{showSectionForm ? 'Cancel' : 'Add Department'}</span>
          </button>
        </div>

        {showSectionForm && (
          <form onSubmit={handleCreateSection} className="mt-4 p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="sm:col-span-1">
                <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wider mb-1">Name</label>
                <input value={sectionName} onChange={(e) => setSectionName(e.target.value)} placeholder="e.g. Sales" className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-violet-500" />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wider mb-1">
                  Scope description <span className="text-slate-400 font-normal normal-case">(helps the AI tell this department apart from others)</span>
                </label>
                <input value={sectionDescription} onChange={(e) => setSectionDescription(e.target.value)} placeholder="e.g. Pricing questions, product demos, purchase requests, quotes" className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-violet-500" />
              </div>
            </div>
            {sectionError && <p className="text-xs text-rose-600">{sectionError}</p>}
            <button type="submit" disabled={sectionSubmitting} className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-60 text-white font-semibold text-xs rounded-xl cursor-pointer">
              {sectionSubmitting ? 'Creating...' : 'Create Department'}
            </button>
          </form>
        )}

        <div className="mt-4">
          {sectionsLoading ? (
            <div className="py-6 text-center text-xs text-slate-500">Loading departments...</div>
          ) : sections.length === 0 ? (
            <div className="py-6 text-center text-xs text-slate-500">
              No departments yet — everything routes through the general Support/Enquiry pipeline.
            </div>
          ) : (
            <div className="divide-y divide-slate-100 border border-slate-100 rounded-xl overflow-hidden">
              {sections.map((s) => {
                const isEditingSection = editingSectionId === s.id;
                return (
                  <div key={s.id} className="px-4 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-white">
                    {isEditingSection ? (
                      <div className="flex-1 grid grid-cols-1 sm:grid-cols-3 gap-2">
                        <input value={editSectionName} onChange={(e) => setEditSectionName(e.target.value)} className="bg-slate-50 border border-slate-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-violet-500" />
                        <input value={editSectionDescription} onChange={(e) => setEditSectionDescription(e.target.value)} className="sm:col-span-2 bg-slate-50 border border-slate-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-violet-500" />
                      </div>
                    ) : (
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="text-xs font-bold text-slate-900">{s.name}</span>
                          <span className="text-[10px] font-mono text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                            {s.resolverCount} resolver{s.resolverCount === 1 ? '' : 's'}
                          </span>
                          {!s.isActive && (
                            <span className="px-2 py-0.5 text-[10px] font-semibold rounded-md border bg-slate-100 text-slate-500 border-slate-200">Inactive</span>
                          )}
                        </div>
                        {s.description && <p className="text-[11px] text-slate-500 mt-0.5">{s.description}</p>}
                      </div>
                    )}
                    <div className="flex items-center space-x-2 shrink-0">
                      {isEditingSection ? (
                        <>
                          <button onClick={() => handleSaveSectionEdit(s)} className="px-2.5 py-1.5 rounded-lg text-[11px] font-semibold bg-violet-600 text-white hover:bg-violet-500 flex items-center space-x-1 cursor-pointer">
                            <Save className="w-3.5 h-3.5" /><span>Save</span>
                          </button>
                          <button onClick={() => setEditingSectionId(null)} className="px-2.5 py-1.5 rounded-lg text-[11px] font-semibold bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 flex items-center space-x-1 cursor-pointer">
                            <X className="w-3.5 h-3.5" /><span>Cancel</span>
                          </button>
                        </>
                      ) : (
                        <>
                          <button onClick={() => handleStartEditSection(s)} className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 cursor-pointer" title="Edit">
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleToggleSectionActive(s)}
                            className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold border cursor-pointer ${s.isActive ? 'bg-white text-rose-600 border-rose-200 hover:bg-rose-50' : 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'}`}
                          >
                            {s.isActive ? 'Deactivate' : 'Reactivate'}
                          </button>
                          <button onClick={() => handleDeleteSection(s)} className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 cursor-pointer" title="Delete department">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Team list */}
      <div className="bg-white rounded-2xl border border-slate-200/90 shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900">Team ({team.length})</h3>
          <div className="text-[11px] text-slate-500 font-mono">
            {resolverCount} Resolver{resolverCount === 1 ? '' : 's'} &bull; {authorityCount} Escalation Authorit{authorityCount === 1 ? 'y' : 'ies'}
          </div>
        </div>

        {team.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-500">
            No team members yet. Add a Resolver above so new complaints have someone to auto-assign to.
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {team.map((member) => {
              const meta = ROLE_META[member.role] || { label: member.role, icon: Users, cls: 'bg-slate-100 text-slate-700 border-slate-200' };
              const Icon = meta.icon;
              const isEditing = editingId === member.id;
              return (
                <div key={member.id} className="px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center space-x-3">
                    <div className="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 font-bold text-xs shrink-0">
                      {member.name.slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      {isEditing ? (
                        <div className="flex items-center space-x-2">
                          <select
                            value={editRole}
                            onChange={(e) => setEditRole(e.target.value)}
                            className="bg-slate-50 border border-slate-300 rounded-lg px-2 py-1 text-[11px] font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          >
                            <option value="Resolver">Resolver</option>
                            <option value="EscalationAuthority">Escalation Authority</option>
                          </select>
                          {editRole === 'EscalationAuthority' && (
                            <select
                              value={editEscalationLevel}
                              onChange={(e) => setEditEscalationLevel(e.target.value)}
                              className="bg-slate-50 border border-slate-300 rounded-lg px-2 py-1 text-[11px] font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500"
                            >
                              {[1, 2, 3, 4].map((lvl) => (
                                <option key={lvl} value={lvl}>Tier {lvl}{lvl === 1 ? ' (first-line)' : ''}</option>
                              ))}
                            </select>
                          )}
                          {editRole === 'Resolver' && (
                            <select
                              value={editSectionId}
                              onChange={(e) => setEditSectionId(e.target.value)}
                              className="bg-slate-50 border border-slate-300 rounded-lg px-2 py-1 text-[11px] font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500"
                            >
                              <option value={NO_SECTION}>General pool</option>
                              {sections.map((s) => (
                                <option key={s.id} value={s.id}>{s.name}</option>
                              ))}
                            </select>
                          )}
                        </div>
                      ) : (
                        <div className="flex items-center space-x-2">
                          <span className="text-xs font-bold text-slate-900">{member.name}</span>
                          <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-semibold rounded-md border ${meta.cls}`}>
                            <Icon className="w-2.5 h-2.5 mr-1" />
                            {meta.label}
                          </span>
                          {member.role === 'Resolver' && member.sectionName && (
                            <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-semibold rounded-md border bg-violet-50 text-violet-700 border-violet-200">
                              <Layers className="w-2.5 h-2.5 mr-1" />
                              {member.sectionName}
                            </span>
                          )}
                          {member.role === 'EscalationAuthority' && (
                            <span className="px-2 py-0.5 text-[10px] font-semibold rounded-md border bg-slate-50 text-slate-600 border-slate-200">
                              Tier {member.escalationLevel || 1}
                            </span>
                          )}
                          {!member.isActive && (
                            <span className="px-2 py-0.5 text-[10px] font-semibold rounded-md border bg-slate-100 text-slate-500 border-slate-200">Inactive</span>
                          )}
                        </div>
                      )}
                      <div className="flex items-center space-x-3 mt-1 text-[11px] text-slate-500">
                        <span className="flex items-center space-x-1"><Mail className="w-3 h-3" /><span>{member.email}</span></span>
                        {member.mobile && <span className="flex items-center space-x-1"><Phone className="w-3 h-3" /><span>{member.mobile}</span></span>}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    {isEditing ? (
                      <>
                        <button
                          onClick={() => handleSaveEdit(member)}
                          disabled={editSubmitting}
                          className="px-3 py-1.5 rounded-lg text-[11px] font-semibold border flex items-center space-x-1.5 transition-all cursor-pointer bg-indigo-600 text-white border-indigo-600 hover:bg-indigo-500 disabled:opacity-60"
                        >
                          <Save className="w-3.5 h-3.5" />
                          <span>{editSubmitting ? 'Saving...' : 'Save'}</span>
                        </button>
                        <button
                          onClick={handleCancelEdit}
                          disabled={editSubmitting}
                          className="px-3 py-1.5 rounded-lg text-[11px] font-semibold border flex items-center space-x-1.5 transition-all cursor-pointer bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                        >
                          <X className="w-3.5 h-3.5" />
                          <span>Cancel</span>
                        </button>
                      </>
                    ) : (
                      <>
                        <span className="text-[11px] font-mono text-slate-500 bg-slate-100 px-2 py-1 rounded-md">
                          {member.openTicketCount} open
                        </span>
                        <button
                          onClick={() => handleStartEdit(member)}
                          title={member.role === 'Resolver' ? 'Edit role — e.g. promote to Escalation Authority' : 'Edit role / ladder tier'}
                          className="px-3 py-1.5 rounded-lg text-[11px] font-semibold border flex items-center space-x-1.5 transition-all cursor-pointer bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                          <span>Edit</span>
                        </button>
                        <button
                          onClick={() => handleToggleActive(member)}
                          className={`px-3 py-1.5 rounded-lg text-[11px] font-semibold border flex items-center space-x-1.5 transition-all cursor-pointer ${
                            member.isActive
                              ? 'bg-white text-rose-600 border-rose-200 hover:bg-rose-50'
                              : 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
                          }`}
                        >
                          {member.isActive ? <XCircle className="w-3.5 h-3.5" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                          <span>{member.isActive ? 'Deactivate' : 'Reactivate'}</span>
                        </button>
                        <button
                          onClick={() => handleRemove(member)}
                          disabled={removingId === member.id}
                          title="Remove from team"
                          className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer disabled:opacity-60"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

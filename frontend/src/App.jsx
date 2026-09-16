import React, { useState, useEffect, useMemo } from 'react';
import { Navbar } from './components/Navbar';
import { MetricCards } from './components/MetricCards';
import { TicketFeed } from './components/TicketFeed';
import { TicketDetailModal } from './components/TicketDetailModal';
import { HomeScreen } from './components/HomeScreen';
import { AuthModal } from './components/AuthModal';
import { ForceChangePasswordModal } from './components/ForceChangePasswordModal';
import { ChannelsManager } from './components/ChannelsManager';
import { OrganizationSettings } from './components/OrganizationSettings';
import { TeamManager } from './components/TeamManager';
import { SuperAdminPanel } from './components/SuperAdminPanel';
import { TicketAnalytics } from './components/TicketAnalytics';
import { VoiceAssistantModal } from './components/VoiceAssistantModal';
import { PublicStatusPage } from './components/PublicStatusPage';
import { HelpDeskForm } from './components/HelpDeskForm';
import { ShieldCheck, Mic, LayoutDashboard, BarChart3, Radio, Users, Settings, AlertTriangle, X, PhoneCall } from 'lucide-react';
import {
  getCurrentUser,
  logoutUser,
  fetchTickets,
  fetchMailboxes,
  updateTicketStatus,
  reassignTicket,
  addReply,
  setAwaitingCustomer,
  createMailbox,
  deleteMailbox,
  updateMailboxStatus,
  fetchTeam,
} from './utils/storage';

const TABS_BY_ROLE = {
  OrgAdmin: [
    { key: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { key: 'helpdesk', label: 'Help Desk', icon: PhoneCall },
    { key: 'analytics', label: 'Analytics', icon: BarChart3 },
    { key: 'channels', label: 'Channels', icon: Radio },
    { key: 'team', label: 'Team', icon: Users },
    { key: 'settings', label: 'Settings', icon: Settings },
  ],
  Resolver: [
    { key: 'dashboard', label: 'My Queue', icon: LayoutDashboard },
    { key: 'analytics', label: 'Analytics', icon: BarChart3, iconColor: 'text-indigo-300' },
  ],
  EscalationAuthority: [
    { key: 'dashboard', label: 'Escalated Queue', icon: LayoutDashboard },
    { key: 'analytics', label: 'Analytics', icon: BarChart3, iconColor: 'text-indigo-300' },
  ],
};

export default function App() {
  const [showPublicTracker, setShowPublicTracker] = useState(() => window.location.pathname === '/track');
  const [currentUser, setCurrentUser] = useState(() => getCurrentUser());
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState('login');
  const [activeTab, setActiveTab] = useState('dashboard');

  const [tickets, setTickets] = useState([]);
  const [mailboxes, setMailboxes] = useState([]);
  const [team, setTeam] = useState([]);

  // Live dashboard refresh — re-fetches tickets/mailboxes from the DB periodically so
  // tickets created by the background IMAP poller / WhatsApp webhook show up without a manual reload.
  const [autoSyncEnabled, setAutoSyncEnabled] = useState(true);
  const [isAutoPolling, setIsAutoPolling] = useState(false);

  const [filters, setFilters] = useState({
    searchQuery: '',
    status: 'All',
    category: 'All',
    slaBreachedOnly: false,
  });

  const [selectedTicket, setSelectedTicket] = useState(null);
  const [toastMessage, setToastMessage] = useState(null);
  const [voiceModalOpen, setVoiceModalOpen] = useState(false);
  const [attentionBannerDismissed, setAttentionBannerDismissed] = useState(false);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const isSuperAdmin = currentUser?.role === 'SuperAdmin';
  const isOrgAdmin = currentUser?.role === 'OrgAdmin';
  const tabs = useMemo(() => TABS_BY_ROLE[currentUser?.role] || [], [currentUser]);

  useEffect(() => {
    if (currentUser && !isSuperAdmin && !tabs.some((t) => t.key === activeTab)) {
      setActiveTab(tabs[0]?.key || 'dashboard');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUser, tabs]);

  const refreshTickets = async () => {
    try {
      const data = await fetchTickets();
      setTickets(data.tickets || []);
    } catch (e) {
      console.warn('Failed to load tickets:', e);
    }
  };

  const refreshMailboxes = async () => {
    if (!isOrgAdmin) return;
    try {
      const data = await fetchMailboxes();
      setMailboxes(data.mailboxes || []);
    } catch (e) {
      console.warn('Failed to load mailboxes:', e);
    }
  };

  const refreshTeam = async () => {
    if (!isOrgAdmin) return;
    try {
      const data = await fetchTeam();
      setTeam(data.team || []);
    } catch (e) {
      console.warn('Failed to load team:', e);
    }
  };

  const refreshAll = async () => {
    setIsAutoPolling(true);
    await Promise.all([refreshTickets(), refreshMailboxes()]);
    setIsAutoPolling(false);
  };

  // Load user data on auth change
  useEffect(() => {
    if (currentUser && !isSuperAdmin) {
      refreshTickets();
      refreshMailboxes();
      refreshTeam();
    } else {
      setTickets([]);
      setMailboxes([]);
      setTeam([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUser]);

  // Automatic background dashboard refresh
  useEffect(() => {
    if (!currentUser || isSuperAdmin || !autoSyncEnabled) return;
    const interval = setInterval(() => refreshAll(), 25000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUser, autoSyncEnabled]);

  // Deep-link support: notification emails link to /?ticket=TKT-XXXX so a resolver/authority
  // clicking "Open this ticket" lands straight on the right ticket instead of the login screen.
  useEffect(() => {
    if (!currentUser || isSuperAdmin) return;
    const params = new URLSearchParams(window.location.search);
    const ticketId = params.get('ticket');
    if (!ticketId) return;
    if (tickets.length === 0) return; // wait for the first fetch before deciding it's missing
    const match = tickets.find((t) => t.id === ticketId);
    if (match) {
      setSelectedTicket(match);
      setActiveTab('dashboard');
    } else {
      showToast(`Ticket ${ticketId} was not found in your queue.`);
    }
    const url = new URL(window.location.href);
    url.searchParams.delete('ticket');
    window.history.replaceState({}, '', url.toString());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUser, tickets]);

  const handleToggleAutoSync = () => {
    setAutoSyncEnabled((prev) => {
      const next = !prev;
      showToast(next ? 'Live dashboard refresh resumed (every 25s)' : 'Live dashboard refresh stopped');
      return next;
    });
  };

  const metrics = useMemo(() => {
    const open = tickets.filter((t) => t.status === 'Open' || t.status === 'In Progress').length;
    const escalated = tickets.filter((t) => t.status === 'Escalated' || t.slaBreached).length;
    const resolved = tickets.filter((t) => t.status === 'Resolved').length;
    return { open, escalated, resolved, total: tickets.length };
  }, [tickets]);

  // Tickets the automated pipeline couldn't fully process (no contact email, a notification
  // that failed to send, or an escalation with no authority configured) — needs a human look.
  const attentionTickets = useMemo(() => tickets.filter((t) => t.needsAttention), [tickets]);

  const applyTicket = (updated) => {
    setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    setSelectedTicket((prev) => (prev && prev.id === updated.id ? updated : prev));
  };

  const handleStatusChange = async (ticketId, newStatus) => {
    try {
      const data = await updateTicketStatus(ticketId, newStatus);
      applyTicket(data.ticket);
      showToast(`Ticket ${ticketId} status updated to ${newStatus}`);
    } catch (e) {
      showToast(`Failed to update status: ${e.message}`);
    }
  };

  const handleQuickStatusChange = (ticketId, newStatus, e) => {
    e.stopPropagation();
    handleStatusChange(ticketId, newStatus);
  };

  const handleReassignTicket = async (ticketId, userId) => {
    try {
      const data = await reassignTicket(ticketId, userId);
      applyTicket(data.ticket);
      showToast(`Ticket ${ticketId} reassigned`);
    } catch (e) {
      showToast(`Failed to reassign: ${e.message}`);
    }
  };

  const handleAddReply = async (ticketId, replyText) => {
    try {
      const data = await addReply(ticketId, replyText);
      applyTicket(data.ticket);
      showToast(`Reply sent for ticket ${ticketId}`);
    } catch (e) {
      showToast(`Failed to send reply: ${e.message}`);
    }
  };

  const handleToggleAwaitingCustomer = async (ticketId, awaiting) => {
    try {
      const data = await setAwaitingCustomer(ticketId, awaiting);
      applyTicket(data.ticket);
      showToast(awaiting ? `SLA clock paused for ${ticketId} — awaiting customer reply` : `SLA clock resumed for ${ticketId}`);
    } catch (e) {
      showToast(`Failed to update: ${e.message}`);
    }
  };

  // Mailbox management actions
  const handleAddMailbox = async (mb) => {
    try {
      const data = await createMailbox(mb);
      setMailboxes((prev) => [...prev, data.mailbox]);
      showToast(`Connected mailbox: ${data.mailbox.emailAddress}`);
    } catch (e) {
      showToast(`Failed to add mailbox: ${e.message}`);
    }
  };

  const handleDeleteMailbox = async (id) => {
    try {
      await deleteMailbox(id);
      setMailboxes((prev) => prev.filter((m) => m.id !== id));
      showToast('Mailbox disconnected.');
    } catch (e) {
      showToast(`Failed to disconnect mailbox: ${e.message}`);
    }
  };

  const handleToggleMailboxStatus = async (id) => {
    const target = mailboxes.find((m) => m.id === id);
    if (!target) return;
    const next = target.status === 'Connected' ? 'Paused' : 'Connected';
    try {
      const data = await updateMailboxStatus(id, next);
      setMailboxes((prev) => prev.map((m) => (m.id === id ? data.mailbox : m)));
    } catch (e) {
      showToast(`Failed to update mailbox: ${e.message}`);
    }
  };

  const handleMailboxSynced = (updatedMailbox) => {
    setMailboxes((prev) => prev.map((m) => (m.id === updatedMailbox.id ? updatedMailbox : m)));
    refreshTickets();
  };

  const handleFilterChange = (updated) => {
    setFilters((prev) => ({ ...prev, ...updated }));
  };

  const handleMetricCardClick = (status, slaOnly) => {
    if (slaOnly) {
      setFilters({ searchQuery: '', status: 'All', category: 'All', slaBreachedOnly: true });
    } else {
      setFilters({ searchQuery: '', status, category: 'All', slaBreachedOnly: false });
    }
  };

  const handleLogout = () => {
    logoutUser();
    setCurrentUser(null);
    showToast('Logged out successfully.');
  };

  // Voice command execution
  const handleExecuteVoiceResult = (result) => {
    if (result.tab) setActiveTab(result.tab);

    switch (result.action) {
      case 'NAVIGATE':
        showToast(`Voice AI: Navigated to ${result.tab}`);
        break;
      case 'FILTER_CATEGORY':
        setFilters((prev) => ({ ...prev, category: result.category || 'All' }));
        showToast(`Voice AI: Filtered by ${result.category}`);
        break;
      case 'FILTER_STATUS':
        setFilters((prev) => ({ ...prev, status: result.status || 'All', slaBreachedOnly: false }));
        showToast(`Voice AI: Filtered by ${result.status} status`);
        break;
      case 'TOGGLE_SLA':
        setFilters((prev) => ({ ...prev, slaBreachedOnly: true }));
        showToast('Voice AI: Showing SLA Breached tickets');
        break;
      case 'SEARCH':
        if (result.searchQuery) {
          setFilters((prev) => ({ ...prev, searchQuery: result.searchQuery }));
          showToast(`Voice AI: Searched for "${result.searchQuery}"`);
        }
        break;
      case 'RESET_FILTERS':
        setFilters({ searchQuery: '', status: 'All', category: 'All', slaBreachedOnly: false });
        showToast('Voice AI: All filters reset');
        break;
      case 'DOWNLOAD_CSV': {
        const btn = document.getElementById('btn-export-csv');
        if (btn) btn.click();
        showToast('Voice AI: Exporting tickets CSV...');
        break;
      }
      default:
        break;
    }
  };

  if (showPublicTracker) {
    return (
      <PublicStatusPage
        onBack={() => {
          window.history.pushState({}, '', '/');
          setShowPublicTracker(false);
        }}
      />
    );
  }

  if (!currentUser) {
    return (
      <>
        <HomeScreen
          onOpenLogin={() => {
            setAuthModalMode('login');
            setAuthModalOpen(true);
          }}
          onOpenSignup={() => {
            setAuthModalMode('signup');
            setAuthModalOpen(true);
          }}
          onOpenTracker={() => {
            window.history.pushState({}, '', '/track');
            setShowPublicTracker(true);
          }}
        />
        <AuthModal
          isOpen={authModalOpen}
          initialMode={authModalMode}
          onClose={() => setAuthModalOpen(false)}
          onSuccessLogin={(user) => {
            setCurrentUser(user);
            showToast(`Welcome, ${user.name}!`);
          }}
        />
      </>
    );
  }

  if (currentUser.mustResetPassword) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center">
        <ForceChangePasswordModal
          isOpen
          onChanged={(updatedUser) => {
            setCurrentUser(updatedUser);
            showToast('Password updated. Welcome!');
          }}
        />
      </div>
    );
  }

  if (isSuperAdmin) {
    return (
      <div className="min-h-screen bg-slate-100 text-slate-900 font-sans flex flex-col antialiased overflow-x-hidden w-full">
        {toastMessage && (
          <div className="fixed bottom-5 right-5 z-50 bg-slate-900 text-white px-4 py-3 rounded-xl shadow-2xl border border-slate-800 flex items-center space-x-3 text-xs font-medium">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
            <span>{toastMessage}</span>
          </div>
        )}
        <Navbar currentUser={currentUser} activeTab="organizations" onTabChange={() => {}} tabs={[]} onLogout={handleLogout} />
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <SuperAdminPanel showToast={showToast} />
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900 font-sans flex flex-col antialiased overflow-x-hidden w-full">
      {toastMessage && (
        <div className="fixed bottom-5 right-5 z-50 bg-slate-900 text-white px-4 py-3 rounded-xl shadow-2xl border border-slate-800 flex items-center space-x-3 text-xs font-medium animate-in fade-in slide-in-from-bottom-3 duration-200">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
          <span>{toastMessage}</span>
        </div>
      )}

      <Navbar
        currentUser={currentUser}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        tabs={tabs}
        searchQuery={filters.searchQuery}
        onSearchChange={(q) => handleFilterChange({ searchQuery: q })}
        openTicketsCount={metrics.open}
        onLogout={handleLogout}
        onOpenVoiceModal={() => setVoiceModalOpen(true)}
        isAutoPolling={isAutoPolling}
        autoSyncEnabled={autoSyncEnabled}
        onToggleAutoSync={handleToggleAutoSync}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {isOrgAdmin && attentionTickets.length > 0 && !attentionBannerDismissed && (
          <div className="mb-6 bg-amber-50 border border-amber-300 rounded-2xl p-4 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-bold text-amber-900">
                {attentionTickets.length} ticket{attentionTickets.length !== 1 ? 's' : ''} need{attentionTickets.length === 1 ? 's' : ''} attention
              </p>
              <p className="text-xs text-amber-800 mt-0.5">
                The automated pipeline couldn't fully process these — a missing contact email, a failed
                notification, or an escalation with no authority configured.
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {attentionTickets.slice(0, 8).map((t) => (
                  <button
                    key={t.id}
                    onClick={() => { setActiveTab('dashboard'); setSelectedTicket(t); }}
                    className="text-[11px] font-mono font-bold bg-white border border-amber-300 text-amber-900 px-2 py-1 rounded-lg hover:bg-amber-100 transition-colors cursor-pointer"
                    title={(t.attentionReasons || []).join(' | ')}
                  >
                    {t.id}
                  </button>
                ))}
                {attentionTickets.length > 8 && (
                  <span className="text-[11px] text-amber-700 px-2 py-1">+{attentionTickets.length - 8} more</span>
                )}
              </div>
            </div>
            <button
              onClick={() => setAttentionBannerDismissed(true)}
              className="p-1 text-amber-500 hover:text-amber-800 rounded-lg hover:bg-amber-100 transition-colors cursor-pointer shrink-0"
              title="Dismiss for this session"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {activeTab === 'dashboard' && (
          <>
            <MetricCards
              openCount={metrics.open}
              escalatedCount={metrics.escalated}
              resolvedCount={metrics.resolved}
              totalCount={metrics.total}
              activeFilter={filters.status}
              slaBreachedOnly={filters.slaBreachedOnly}
              onSelectFilter={handleMetricCardClick}
            />
            <TicketFeed
              tickets={tickets}
              filters={filters}
              onFilterChange={handleFilterChange}
              onSelectTicket={(t) => setSelectedTicket(t)}
              onQuickStatusChange={handleQuickStatusChange}
              currentUser={currentUser}
            />
          </>
        )}

        {isOrgAdmin && activeTab === 'helpdesk' && (
          <HelpDeskForm
            onCreated={(ticket) => {
              setTickets((prev) => [ticket, ...prev]);
              showToast(`Ticket ${ticket.id} created from phone call.`);
            }}
          />
        )}

        {activeTab === 'analytics' && <TicketAnalytics tickets={tickets} currentUser={currentUser} />}

        {isOrgAdmin && activeTab === 'channels' && (
          <ChannelsManager
            mailboxes={mailboxes}
            onAddMailbox={handleAddMailbox}
            onDeleteMailbox={handleDeleteMailbox}
            onToggleMailboxStatus={handleToggleMailboxStatus}
            onMailboxSynced={handleMailboxSynced}
            showToast={showToast}
          />
        )}

        {isOrgAdmin && activeTab === 'team' && (
          <TeamManager team={team} onTeamChanged={refreshTeam} showToast={showToast} />
        )}

        {isOrgAdmin && activeTab === 'settings' && <OrganizationSettings showToast={showToast} />}
      </main>

      <VoiceAssistantModal
        isOpen={voiceModalOpen}
        onClose={() => setVoiceModalOpen(false)}
        currentTab={activeTab}
        onExecuteVoiceResult={handleExecuteVoiceResult}
      />

      <div className="fixed bottom-6 left-6 z-40">
        <button
          onClick={() => setVoiceModalOpen(true)}
          className="flex items-center space-x-2 bg-gradient-to-r from-indigo-600 via-sky-600 to-blue-600 hover:from-indigo-500 hover:to-sky-500 text-white font-bold text-xs px-4 py-3 rounded-full shadow-2xl border-2 border-indigo-400/40 hover:scale-105 active:scale-95 transition-all cursor-pointer group"
        >
          <div className="w-6 h-6 rounded-full bg-white/20 flex items-center justify-center">
            <Mic className="w-3.5 h-3.5 text-amber-300 animate-pulse group-hover:scale-110 transition-transform" />
          </div>
          <span className="font-extrabold tracking-tight">Voice Command AI</span>
          <span className="px-2 py-0.5 text-[9px] bg-slate-900/80 text-amber-300 font-mono rounded-full border border-amber-400/40">
            हिंदी / English
          </span>
        </button>
      </div>

      <TicketDetailModal
        ticket={selectedTicket}
        onClose={() => setSelectedTicket(null)}
        onStatusChange={handleStatusChange}
        onAddReply={handleAddReply}
        currentUser={currentUser}
        team={team}
        onReassign={isOrgAdmin ? handleReassignTicket : undefined}
        onToggleAwaitingCustomer={handleToggleAwaitingCustomer}
      />

      <AuthModal
        isOpen={authModalOpen}
        initialMode={authModalMode}
        onClose={() => setAuthModalOpen(false)}
        onSuccessLogin={(user) => {
          setCurrentUser(user);
          showToast(`Welcome, ${user.name}!`);
        }}
      />

      <footer className="bg-white border-t border-slate-200 text-slate-500 py-6 px-4 sm:px-6 lg:px-8 text-xs mt-12">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-indigo-500" />
            <span className="font-semibold text-slate-700">Grievance Desk Platform</span>
            <span>&bull; {currentUser.orgName}</span>
          </div>
          <div className="flex items-center space-x-4 text-slate-400">
            <span>Powered by Gemini AI</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

import React, { useState } from 'react';
import {
  TicketCheck,
  Search,
  LogOut,
  Shield,
  Menu,
  X,
  Mic,
  Building2
} from 'lucide-react';

const ROLE_LABELS = {
  SuperAdmin: 'Super Admin',
  OrgAdmin: 'Org Admin',
  Resolver: 'Resolver',
  EscalationAuthority: 'Escalation Authority',
};

export const Navbar = ({
  currentUser,
  activeTab,
  onTabChange,
  tabs = [],
  searchQuery,
  onSearchChange,
  openTicketsCount = 0,
  onLogout,
  onOpenVoiceModal,
  isAutoPolling = false,
  autoSyncEnabled = false,
  onToggleAutoSync,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const getInitials = (name) => {
    if (!name) return 'GD';
    const parts = name.trim().split(' ');
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  };

  const handleTabClick = (tab) => {
    onTabChange(tab);
    setMobileMenuOpen(false);
  };

  return (
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-slate-200 text-slate-900 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-3">

        {/* Left Section: Brand Logo & Title */}
        <div className="flex items-center space-x-3 shrink-0">
          <button
            onClick={() => handleTabClick(tabs[0]?.key || 'dashboard')}
            className="flex items-center space-x-2.5 text-left focus:outline-none cursor-pointer group"
          >
            <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-sm group-hover:scale-105 transition-transform">
              <TicketCheck className="w-5 h-5" />
            </div>
            <div className="hidden sm:flex flex-col leading-tight">
              <span className="font-extrabold text-base tracking-tight text-slate-900 group-hover:text-indigo-600 transition-colors">
                Grievance Desk
              </span>
              {currentUser?.orgName && (
                <span className="flex items-center space-x-1 text-[10px] font-mono text-slate-500">
                  <Building2 className="w-2.5 h-2.5" />
                  <span>{currentUser.orgName}</span>
                </span>
              )}
            </div>
          </button>
        </div>

        {/* Center Section: Desktop Navigation Tabs */}
        <nav className="hidden lg:flex items-center space-x-1 bg-slate-100 p-1 rounded-xl shrink-0">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => handleTabClick(tab.key)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-all cursor-pointer whitespace-nowrap ${
                  active
                    ? 'bg-white text-indigo-700 shadow-xs'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {Icon && <Icon className="w-3.5 h-3.5" />}
                <span>{tab.label}</span>
                {tab.key === 'dashboard' && openTicketsCount > 0 && (
                  <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono font-bold ${
                    active ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-200 text-slate-600'
                  }`}>
                    {openTicketsCount}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Right Action Controls: Search, Voice AI & User Badge */}
        <div className="flex items-center space-x-2 shrink-0">
          {/* Search Input */}
          {onSearchChange && (
            <div className="relative hidden xl:block w-44">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value)}
                placeholder="Search tickets..."
                className="w-full bg-slate-100 border border-transparent rounded-xl pl-8 pr-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:bg-white transition-all h-9"
              />
            </div>
          )}

          {/* Live refresh indicator */}
          {onToggleAutoSync && (
            <button
              onClick={onToggleAutoSync}
              title={autoSyncEnabled ? 'Live refresh is on — click to pause' : 'Live refresh is off — click to resume'}
              className="hidden md:flex items-center space-x-1.5 bg-slate-100 hover:bg-slate-200 px-2.5 py-1.5 rounded-xl h-9 shrink-0 transition-colors cursor-pointer"
            >
              <span className={`h-2 w-2 rounded-full ${autoSyncEnabled ? (isAutoPolling ? 'bg-emerald-500 animate-pulse' : 'bg-emerald-500') : 'bg-slate-400'}`} />
              <span className="text-[11px] font-semibold text-slate-600">
                {autoSyncEnabled ? 'Live' : 'Paused'}
              </span>
            </button>
          )}

          {/* Voice Command Button */}
          {onOpenVoiceModal && (
            <button
              onClick={onOpenVoiceModal}
              title="Open Voice Command Assistant (Hindi / Hinglish / English)"
              className="flex items-center space-x-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-2.5 sm:px-3 py-2 rounded-xl shadow-sm transition-colors active:scale-[0.98] cursor-pointer h-9 shrink-0"
            >
              <Mic className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Voice AI</span>
            </button>
          )}

          {/* Logged-in User Profile Badge */}
          {currentUser && (
            <div className="flex items-center space-x-2 bg-slate-100 px-2 sm:px-2.5 py-1 rounded-xl h-9 shrink-0">
              <div className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 font-bold text-[11px] flex items-center justify-center shrink-0">
                {getInitials(currentUser.name)}
              </div>
              <div className="hidden md:block text-left pr-1">
                <div className="text-[11px] font-bold text-slate-800 leading-none">
                  {currentUser.name.split(' ')[0]}
                </div>
                <div className="text-[9px] text-slate-500 flex items-center space-x-1 leading-none mt-0.5">
                  <span>{ROLE_LABELS[currentUser.role] || currentUser.role}</span>
                  {currentUser.role === 'OrgAdmin' || currentUser.role === 'SuperAdmin' ? (
                    <Shield className="w-2.5 h-2.5 text-amber-500 fill-amber-500" />
                  ) : null}
                </div>
              </div>

              <button
                onClick={onLogout}
                className="p-1 text-slate-400 hover:text-rose-600 hover:bg-white rounded-lg transition-colors cursor-pointer"
                title="Log out"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Mobile & Tablet Navigation Toggle Button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 text-slate-500 hover:text-slate-900 bg-slate-100 rounded-xl lg:hidden cursor-pointer h-9 w-9 flex items-center justify-center shrink-0"
            title="Toggle Navigation Menu"
          >
            {mobileMenuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer Menu for Navigation Tabs */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-t border-slate-200 bg-white px-4 py-3 space-y-2 animate-in slide-in-from-top-2 duration-150">
          {onSearchChange && (
            <div className="relative mb-2">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value)}
                placeholder="Search ticket ID, name, mobile..."
                className="w-full bg-slate-100 border border-transparent rounded-xl pl-8 pr-3 py-2 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>
          )}

          <div className="grid grid-cols-2 gap-2">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const active = activeTab === tab.key;
              return (
                <button
                  key={tab.key}
                  onClick={() => handleTabClick(tab.key)}
                  className={`p-2.5 rounded-xl text-xs font-semibold flex items-center space-x-2 ${
                    active ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {Icon && <Icon className="w-4 h-4" />}
                  <span>{tab.label}{tab.key === 'dashboard' && openTicketsCount > 0 ? ` (${openTicketsCount})` : ''}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </header>
  );
};

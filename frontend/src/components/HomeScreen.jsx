import React from 'react';
import {
  TicketCheck,
  Mail,
  MessageSquare,
  Bot,
  Clock,
  UserPlus,
  ArrowRight,
  Sparkles,
} from 'lucide-react';

export const HomeScreen = ({
  onOpenLogin,
  onOpenSignup,
  onOpenTracker,
}) => {
  return (
    <div className="min-h-screen bg-white text-slate-900 flex flex-col font-sans selection:bg-indigo-100">
      {/* Top Header Navigation */}
      <header className="border-b border-slate-200 bg-white/90 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-sm">
              <TicketCheck className="w-5 h-5" />
            </div>
            <span className="font-bold text-lg tracking-tight text-slate-900">
              Grievance Desk
            </span>
          </div>

          <div className="flex items-center space-x-1 sm:space-x-2">
            {onOpenTracker && (
              <button
                onClick={onOpenTracker}
                className="px-3 sm:px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
              >
                Track a Ticket
              </button>
            )}
            <button
              onClick={onOpenLogin}
              className="px-3 sm:px-4 py-2 text-xs font-semibold text-slate-700 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
            >
              Log In
            </button>
            <button
              onClick={onOpenSignup}
              className="px-3 sm:px-4 py-2 text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg shadow-sm transition-colors cursor-pointer flex items-center space-x-1.5"
            >
              <UserPlus className="w-3.5 h-3.5" />
              <span>Create Account</span>
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-16 sm:py-24 bg-gradient-to-b from-indigo-50/60 to-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div className="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-xs font-medium mb-6">
            <Sparkles className="w-3.5 h-3.5 text-amber-500" />
            <span>AI-Powered Complaint Management</span>
          </div>

          <h1 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight leading-tight">
            Every complaint, sorted and routed automatically
          </h1>

          <p className="mt-4 text-sm sm:text-base text-slate-600 max-w-xl mx-auto leading-relaxed">
            Complaints from Email and WhatsApp land in one simple dashboard, already
            categorized by AI. Assign the right person, track SLAs, and never lose a
            complaint again.
          </p>

          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
            <button
              onClick={onOpenSignup}
              className="w-full sm:w-auto px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-xl shadow-md flex items-center justify-center space-x-2 transition-colors cursor-pointer"
            >
              <span>Get Started Free</span>
              <ArrowRight className="w-4 h-4" />
            </button>

            <button
              onClick={onOpenLogin}
              className="w-full sm:w-auto px-6 py-3 bg-white hover:bg-slate-50 border border-slate-300 text-slate-700 font-semibold text-sm rounded-xl transition-colors cursor-pointer"
            >
              Log In
            </button>
          </div>

          <p className="mt-6 text-[11px] text-slate-500">
            New here? Register your organization — you'll become its admin and can
            invite team members afterward.
          </p>
        </div>
      </section>

      {/* Feature Grid */}
      <section className="py-16 bg-slate-50 border-t border-slate-100">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
              Everything you need, nothing you don't
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div className="bg-white border border-slate-200 rounded-2xl p-6">
              <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center mb-4">
                <Bot className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-bold text-slate-900 mb-2">
                AI Categorization
              </h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                Every complaint is read and sorted by AI the moment it arrives — no
                manual tagging needed.
              </p>
            </div>

            <div className="bg-white border border-slate-200 rounded-2xl p-6">
              <div className="w-10 h-10 rounded-xl bg-sky-50 text-sky-600 flex items-center justify-center mb-4">
                <Mail className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-bold text-slate-900 mb-2">
                Email &amp; WhatsApp Intake
              </h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                Connect your inbox and WhatsApp Business number in a couple of
                minutes — complaints start flowing straight to your dashboard.
              </p>
            </div>

            <div className="bg-white border border-slate-200 rounded-2xl p-6">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center mb-4">
                <Clock className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-bold text-slate-900 mb-2">
                SLA Tracking &amp; Escalation
              </h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                Set response windows and an escalation ladder once — overdue
                complaints automatically climb to the next person.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto py-8 bg-white border-t border-slate-100 text-xs text-slate-500 text-center">
        <p className="flex items-center justify-center gap-1.5">
          <MessageSquare className="w-3.5 h-3.5" />
          Grievance Desk Platform
        </p>
      </footer>
    </div>
  );
};

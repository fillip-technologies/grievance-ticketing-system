import React, { useState } from 'react';
import { Mail, MessageSquare, Smartphone } from 'lucide-react';
import { MailboxManager } from './MailboxManager';
import { WhatsAppChannelConfig } from './WhatsAppChannelConfig';
import { SmsChannelConfig } from './SmsChannelConfig';

export const ChannelsManager = ({
  mailboxes,
  onAddMailbox,
  onDeleteMailbox,
  onToggleMailboxStatus,
  onMailboxSynced,
  showToast,
}) => {
  const [activeChannel, setActiveChannel] = useState('email');

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      <div>
        <h1 className="text-lg font-extrabold text-slate-900 tracking-tight">Channels</h1>
        <p className="text-xs text-slate-500 mt-0.5">Set up where complaints come from and how customers are notified — Email, WhatsApp, and SMS.</p>
      </div>

      <div className="inline-flex items-center bg-slate-100 p-1 rounded-xl">
        <button
          onClick={() => setActiveChannel('email')}
          className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-all cursor-pointer ${
            activeChannel === 'email' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-800'
          }`}
        >
          <Mail className="w-3.5 h-3.5 text-sky-600" />
          <span>Email</span>
        </button>
        <button
          onClick={() => setActiveChannel('whatsapp')}
          className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-all cursor-pointer ${
            activeChannel === 'whatsapp' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-800'
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5 text-emerald-600" />
          <span>WhatsApp</span>
        </button>
        <button
          onClick={() => setActiveChannel('sms')}
          className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-all cursor-pointer ${
            activeChannel === 'sms' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-800'
          }`}
        >
          <Smartphone className="w-3.5 h-3.5 text-indigo-600" />
          <span>SMS</span>
        </button>
      </div>

      {activeChannel === 'email' && (
        <MailboxManager
          mailboxes={mailboxes}
          onAddMailbox={onAddMailbox}
          onDeleteMailbox={onDeleteMailbox}
          onToggleMailboxStatus={onToggleMailboxStatus}
          onMailboxSynced={onMailboxSynced}
        />
      )}
      {activeChannel === 'whatsapp' && <WhatsAppChannelConfig showToast={showToast} />}
      {activeChannel === 'sms' && <SmsChannelConfig showToast={showToast} />}
    </div>
  );
};

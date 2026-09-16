// Voice action types:
// NAVIGATE | FILTER_CATEGORY | FILTER_STATUS | SEARCH | SYNC_MAILBOX |
// RESET_FILTERS | TOGGLE_SLA | CREATE_TICKET | DOWNLOAD_CSV | UNKNOWN

import { voiceCommand } from './storage';

/**
 * Local fallback voice command parser supporting Hindi, Hinglish & English
 */
export function parseVoiceCommandLocally(transcript) {
  const text = transcript.trim().toLowerCase();

  // 1. Navigation Commands
  if (
    text.includes('analytics') ||
    text.includes('एनालिटिक्स') ||
    text.includes('trend') ||
    text.includes('chart') ||
    text.includes('graph') ||
    text.includes('report')
  ) {
    return {
      action: 'NAVIGATE',
      tab: 'analytics',
      spokenResponseHindi: 'जी, एनालिटिक्स और ट्रेंड्स पेज खोला जा रहा है।',
      spokenResponseEnglish: 'Navigating to Analytics & Trends dashboard.',
    };
  }

  if (
    text.includes('webmail') ||
    text.includes('mailbox') ||
    text.includes('वेबमेल') ||
    text.includes('मेलबॉक्स') ||
    text.includes('hostinger') ||
    text.includes('email')
  ) {
    if (text.includes('sync') || text.includes('सिंक') || text.includes('fetch') || text.includes('refresh')) {
      return {
        action: 'SYNC_MAILBOX',
        tab: 'channels',
        spokenResponseHindi: 'होस्टिंगर वेबमेल सिंक चालू किया जा रहा है। 17 नए ईमेल अपडेट किए गए।',
        spokenResponseEnglish: 'Syncing Hostinger Mail inbox and updating dashboard.',
      };
    }
    return {
      action: 'NAVIGATE',
      tab: 'channels',
      spokenResponseHindi: 'जी, चैनल्स पेज खोला जा रहा है।',
      spokenResponseEnglish: 'Navigating to Channels.',
    };
  }

  if (
    text.includes('whatsapp') ||
    text.includes('व्हाट्सएप') ||
    text.includes('chat') ||
    text.includes('wa intake')
  ) {
    return {
      action: 'NAVIGATE',
      tab: 'channels',
      spokenResponseHindi: 'जी, चैनल्स पेज खोला जा रहा है।',
      spokenResponseEnglish: 'Navigating to Channels.',
    };
  }

  if (
    text.includes('ai engine') ||
    text.includes('engine settings') ||
    text.includes('सेटिंग्स') ||
    text.includes('settings') ||
    text.includes('api key')
  ) {
    return {
      action: 'NAVIGATE',
      tab: 'settings',
      spokenResponseHindi: 'जी, AI इंजन और API सेटिंग्स खोली जा रही हैं।',
      spokenResponseEnglish: 'Opening AI Engine & API Settings.',
    };
  }

  if (
    text.includes('dashboard') ||
    text.includes('डैशबोर्ड') ||
    text.includes('home') ||
    text.includes('मुख्य पृष्ठ') ||
    text.includes('ticket feed')
  ) {
    return {
      action: 'NAVIGATE',
      tab: 'dashboard',
      spokenResponseHindi: 'जी, मुख्य डैशबोर्ड पर वापस जा रहे हैं।',
      spokenResponseEnglish: 'Navigating back to Main Dashboard.',
    };
  }

  // 2. Filter Commands
  if (
    text.includes('support') ||
    text.includes('सपोर्ट') ||
    text.includes('grievance') ||
    text.includes('शिकायत') ||
    text.includes('technical issue')
  ) {
    return {
      action: 'FILTER_CATEGORY',
      tab: 'dashboard',
      category: 'Support',
      spokenResponseHindi: 'सपोर्ट और ग्रीवांस कैटेगरी के टिकट्स फ़िल्टर कर दिए गए हैं।',
      spokenResponseEnglish: 'Filtering tickets by Support category.',
    };
  }

  if (
    text.includes('enquiry') ||
    text.includes('inquiry') ||
    text.includes('इन्क्वायरी') ||
    text.includes('पूछताछ') ||
    text.includes('billing')
  ) {
    return {
      action: 'FILTER_CATEGORY',
      tab: 'dashboard',
      category: 'Enquiry',
      spokenResponseHindi: 'इन्क्वायरी टिकट्स फ़िल्टर कर दिए गए हैं।',
      spokenResponseEnglish: 'Filtering tickets by Enquiry category.',
    };
  }

  if (
    text.includes('open ticket') ||
    text.includes('ओपन टिकट') ||
    text.includes('open filter') ||
    text.includes('ओपन दिखाओ')
  ) {
    return {
      action: 'FILTER_STATUS',
      tab: 'dashboard',
      status: 'Open',
      spokenResponseHindi: 'केवल ओपन टिकट्स दिखाए जा रहे हैं।',
      spokenResponseEnglish: 'Filtering by Open status tickets.',
    };
  }

  if (
    text.includes('resolved') ||
    text.includes('सॉल्व') ||
    text.includes('सुलझा') ||
    text.includes('closed')
  ) {
    return {
      action: 'FILTER_STATUS',
      tab: 'dashboard',
      status: 'Resolved',
      spokenResponseHindi: 'सॉल्व और रिज़ॉल्वड टिकट्स दिखाए जा रहे हैं।',
      spokenResponseEnglish: 'Filtering by Resolved tickets.',
    };
  }

  if (
    text.includes('escalated') ||
    text.includes('एस्केलेटेड') ||
    text.includes('urgent') ||
    text.includes('अति आवश्यक')
  ) {
    return {
      action: 'FILTER_STATUS',
      tab: 'dashboard',
      status: 'Escalated',
      spokenResponseHindi: 'एस्केलेटेड और अर्जेंट टिकट्स दिखाए जा रहे हैं।',
      spokenResponseEnglish: 'Filtering by Escalated tickets.',
    };
  }

  if (
    text.includes('sla') ||
    text.includes('breached') ||
    text.includes('लेट') ||
    text.includes('overdue')
  ) {
    return {
      action: 'TOGGLE_SLA',
      tab: 'dashboard',
      spokenResponseHindi: 'SLA ब्रीच वाले लेट टिकट्स फ़िल्टर किए गए हैं।',
      spokenResponseEnglish: 'Filtering SLA Breached tickets.',
    };
  }

  if (
    text.includes('reset') ||
    text.includes('clear') ||
    text.includes('रीसेट') ||
    text.includes('हटाओ') ||
    text.includes('show all') ||
    text.includes('सब दिखाओ')
  ) {
    return {
      action: 'RESET_FILTERS',
      tab: 'dashboard',
      category: 'All',
      status: 'All',
      searchQuery: '',
      spokenResponseHindi: 'सभी फ़िल्टर और सर्च रीसेट कर दिए गए हैं।',
      spokenResponseEnglish: 'All filters and search queries reset.',
    };
  }

  if (
    text.includes('download') ||
    text.includes('csv') ||
    text.includes('डाउनलोड') ||
    text.includes('export')
  ) {
    return {
      action: 'DOWNLOAD_CSV',
      spokenResponseHindi: 'टिकट डेटा की CSV फाइल डाउनलोड की जा रही है।',
      spokenResponseEnglish: 'Exporting ticket feed as CSV file.',
    };
  }

  // 3. Search command extraction: "search for Vikash", "dhoondo Rajgir", "find Payment"
  const searchMatch =
    text.match(/(?:search|find|dhoondo|dhoondho|khojo|dekho|search for|lookup)\s+(.+)/i) ||
    text.match(/(.+)\s+(dhoondo|search karo|khojo)/i);

  if (searchMatch) {
    const term = (searchMatch[1] || searchMatch[2]).trim();
    if (term) {
      return {
        action: 'SEARCH',
        tab: 'dashboard',
        searchQuery: term,
        spokenResponseHindi: `"${term}" के लिए टिकट्स खोजे जा रहे हैं।`,
        spokenResponseEnglish: `Searching tickets for "${term}".`,
      };
    }
  }

  return {
    action: 'UNKNOWN',
    spokenResponseHindi: `क्षमा करें, "${transcript}" कमांड समझ नहीं आई। आप "सपोर्ट टिकट्स दिखाओ", "एनालिटिक्स खोलो" या "वेबमेल सिंक करो" बोल सकते हैं।`,
    spokenResponseEnglish: `Sorry, command "${transcript}" was not recognized. Try saying "Show support tickets", "Open analytics", or "Sync webmail".`,
  };
}

/**
 * Main function invoking server-side AI voice interpreter with client fallback
 */
export async function processVoiceCommand(transcript, currentTab) {
  try {
    const data = await voiceCommand({ transcript, currentTab });
    if (data && data.action && data.action !== 'UNKNOWN') {
      return data;
    }
  } catch (err) {
    console.warn('AI Voice Command API offline, falling back to client parser:', err);
  }

  return parseVoiceCommandLocally(transcript);
}

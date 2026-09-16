import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  X,
  Sparkles,
  Zap,
  Globe,
  Send,
  HelpCircle,
  BarChart3,
  Mail,
  MessageSquare,
  LayoutDashboard,
  RefreshCw,
  Search,
  CheckCircle2,
  AlertCircle,
  Radio
} from 'lucide-react';
import { processVoiceCommand } from '../utils/voiceCommandParser';

export const VoiceAssistantModal = ({
  isOpen,
  onClose,
  currentTab,
  onExecuteVoiceResult,
}) => {
  const [isListening, setIsListening] = useState(false);
  const [langMode, setLangMode] = useState('hi-IN');
  const [transcript, setTranscript] = useState('');
  const [manualInput, setManualInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [speechEnabled, setSpeechEnabled] = useState(true);
  const [lastResult, setLastResult] = useState(null);
  const [commandHistory, setCommandHistory] = useState([]);

  const [speechError, setSpeechError] = useState(null);

  const recognitionRef = useRef(null);
  const transcriptRef = useRef('');

  // Speak response using browser Speech Synthesis
  const speakText = (text, lang) => {
    if (!speechEnabled || typeof window === 'undefined' || !('speechSynthesis' in window)) {
      return;
    }
    window.speechSynthesis.cancel(); // Stop prior speech
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang === 'hi-IN' ? 'hi-IN' : 'en-IN';
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
  };

  const handleProcessCommand = async (commandText) => {
    if (!commandText.trim()) return;
    setIsProcessing(true);

    const result = await processVoiceCommand(commandText, currentTab);
    setLastResult(result);

    // Speak vocal feedback
    const vocalText =
      langMode === 'hi-IN'
        ? result.spokenResponseHindi || result.spokenResponseEnglish
        : result.spokenResponseEnglish || result.spokenResponseHindi;

    speakText(vocalText, langMode);

    // Add to history
    setCommandHistory((prev) => [
      {
        id: `cmd-${Date.now()}`,
        query: commandText,
        result,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
      ...prev.slice(0, 4),
    ]);

    setIsProcessing(false);

    // Execute actual dashboard mutations
    onExecuteVoiceResult(result);
  };

  // Keep a ref to handleProcessCommand for speech recognition handlers
  const processCommandRef = useRef(handleProcessCommand);
  useEffect(() => {
    processCommandRef.current = handleProcessCommand;
  });

  // Initialize Web Speech API if supported
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const SpeechRecognition =
        window.SpeechRecognition || window.webkitSpeechRecognition;

      if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = langMode;

        recognition.onstart = () => {
          setIsListening(true);
          setSpeechError(null);
        };

        recognition.onresult = (event) => {
          let currentText = '';
          for (let i = event.resultIndex; i < event.results.length; ++i) {
            currentText += event.results[i][0].transcript;
          }
          setTranscript(currentText);
          transcriptRef.current = currentText;
        };

        recognition.onerror = (event) => {
          console.warn('Speech recognition error:', event.error);
          setIsListening(false);
          if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
            setSpeechError(
              'Microphone permission blocked or restricted in preview frame. Click "Allow Microphone" in browser address bar or use the command box below.'
            );
          } else if (event.error === 'no-speech') {
            setSpeechError('No speech was detected. Please try clicking the microphone again and speaking clearly.');
          }
        };

        recognition.onend = () => {
          setIsListening(false);
          if (transcriptRef.current && transcriptRef.current.trim()) {
            const spokenText = transcriptRef.current.trim();
            transcriptRef.current = '';
            processCommandRef.current(spokenText);
          }
        };

        recognitionRef.current = recognition;
      }
    }
  }, [langMode]);

  // Update language on recognition instance
  useEffect(() => {
    if (recognitionRef.current) {
      recognitionRef.current.lang = langMode;
    }
  }, [langMode]);

  if (!isOpen) return null;

  const handleStartListening = () => {
    setSpeechError(null);
    setTranscript('');
    transcriptRef.current = '';
    if (!recognitionRef.current) {
      setSpeechError(
        'Browser Speech Recognition API is not supported natively in this browser window. Please use the Voice Command Box or Quick Chips below!'
      );
      return;
    }
    try {
      recognitionRef.current.start();
    } catch (e) {
      console.warn('Recognition already started:', e);
    }
  };

  const handleStopListening = () => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {
        console.warn('Error stopping recognition:', e);
      }
    }
    setIsListening(false);
    if (transcriptRef.current && transcriptRef.current.trim()) {
      const textToRun = transcriptRef.current.trim();
      transcriptRef.current = '';
      handleProcessCommand(textToRun);
    }
  };

  const handleQuickChipClick = (cmd) => {
    setTranscript(cmd);
    handleProcessCommand(cmd);
  };

  const handleManualSubmit = (e) => {
    e.preventDefault();
    if (!manualInput.trim()) return;
    setTranscript(manualInput);
    handleProcessCommand(manualInput);
    setManualInput('');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh] text-slate-100">
        
        {/* Header */}
        <div className="px-6 py-4 bg-slate-950/90 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-sky-500 flex items-center justify-center text-white shadow-lg shadow-indigo-600/30">
              <Sparkles className="w-5 h-5 text-amber-300 fill-amber-300" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-base font-extrabold text-white tracking-tight">
                  AI Voice Command Assistant
                </h2>
                <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 rounded-full">
                  Hindi • Hinglish • English
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Speak or type commands to operate the entire Grievance Desk dashboard
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setSpeechEnabled(!speechEnabled)}
              title={speechEnabled ? 'Mute Speech Synthesis' : 'Enable Speech Synthesis'}
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors cursor-pointer"
            >
              {speechEnabled ? (
                <Volume2 className="w-4 h-4 text-emerald-400" />
              ) : (
                <VolumeX className="w-4 h-4 text-slate-500" />
              )}
            </button>

            <button
              onClick={onClose}
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Body Container */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          
          {/* Language Selector Pills */}
          <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-950/80 p-3 rounded-xl border border-slate-800/80">
            <div className="flex items-center space-x-2 text-xs text-slate-400">
              <Globe className="w-4 h-4 text-sky-400" />
              <span className="font-semibold text-slate-300">Speech Language:</span>
            </div>

            <div className="flex items-center space-x-1.5">
              <button
                onClick={() => setLangMode('hi-IN')}
                className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                  langMode === 'hi-IN'
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                    : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                🇮🇳 Hindi (हिंदी)
              </button>

              <button
                onClick={() => setLangMode('en-IN')}
                className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                  langMode === 'en-IN'
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                    : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                🗣️ Hinglish (हिंग्लिश)
              </button>

              <button
                onClick={() => setLangMode('en-US')}
                className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                  langMode === 'en-US'
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                    : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                🌐 English
              </button>
            </div>
          </div>

          {/* Speech Error / Permission Alert Notice */}
          {speechError && (
            <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-start space-x-3 text-xs text-amber-200 animate-in fade-in">
              <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div className="flex-1 space-y-1">
                <p className="font-semibold text-amber-300">{speechError}</p>
                <p className="text-[11px] text-amber-200/80">
                  Tip: You can also type commands in Hindi ("सपोर्ट टिकट दिखाओ"), Hinglish ("Support grievance filter karo"), or English below, or click any Quick Chip!
                </p>
              </div>
              <button
                onClick={() => setSpeechError(null)}
                className="text-amber-400 hover:text-amber-200 p-0.5 rounded cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Main Microphone Voice Hub */}
          <div className="bg-gradient-to-b from-slate-950 to-slate-900 border border-slate-800 rounded-2xl p-6 text-center space-y-4 relative overflow-hidden">
            
            {/* Ambient Pulse Ring */}
            {isListening && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="w-48 h-48 rounded-full bg-indigo-500/10 animate-ping" />
                <div className="w-32 h-32 rounded-full bg-sky-500/20 animate-pulse" />
              </div>
            )}

            <div className="relative z-10 flex flex-col items-center">
              <button
                onClick={isListening ? handleStopListening : handleStartListening}
                className={`w-20 h-20 rounded-full flex items-center justify-center transition-all cursor-pointer shadow-xl ${
                  isListening
                    ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-600/50 scale-110 animate-pulse'
                    : 'bg-gradient-to-tr from-indigo-600 to-sky-500 hover:from-indigo-500 hover:to-sky-400 text-white shadow-indigo-600/40 hover:scale-105'
                }`}
              >
                {isListening ? (
                  <MicOff className="w-9 h-9 text-white animate-bounce" />
                ) : (
                  <Mic className="w-9 h-9 text-white" />
                )}
              </button>

              <div className="mt-3 space-y-1">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-300 block">
                  {isListening ? '🎙️ Listening... Speak Now!' : 'Click Microphone to Speak'}
                </span>
                <p className="text-[11px] text-slate-400 max-w-xs mx-auto">
                  {isListening
                    ? 'Listening in Hindi / Hinglish / English...'
                    : 'Tap microphone and give your dashboard command.'}
                </p>
              </div>

              {/* Audio Wave Visualizer */}
              {isListening && (
                <div className="flex items-center space-x-1.5 mt-3 h-6">
                  <div className="w-1.5 bg-sky-400 rounded-full animate-bounce h-4" />
                  <div className="w-1.5 bg-indigo-400 rounded-full animate-bounce h-6 delay-100" />
                  <div className="w-1.5 bg-emerald-400 rounded-full animate-bounce h-3 delay-150" />
                  <div className="w-1.5 bg-amber-400 rounded-full animate-bounce h-5 delay-200" />
                  <div className="w-1.5 bg-sky-400 rounded-full animate-bounce h-4 delay-75" />
                </div>
              )}

              {/* Realtime Live Transcript Box */}
              {(transcript || isListening) && (
                <div className="mt-4 w-full bg-slate-950 p-3 rounded-xl border border-slate-800 text-xs font-mono text-sky-300 min-h-[44px] flex items-center justify-between">
                  <span className="truncate">
                    {transcript || 'Listening for speech input...'}
                  </span>
                  {transcript && !isListening && (
                    <button
                      onClick={() => handleProcessCommand(transcript)}
                      disabled={isProcessing}
                      className="ml-2 px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-lg text-[11px] cursor-pointer shrink-0"
                    >
                      {isProcessing ? 'Processing...' : 'Run Command'}
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Voice Text Command Input Fallback */}
          <form onSubmit={handleManualSubmit} className="space-y-2">
            <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider">
              Type Voice Command (Hindi / Hinglish / English)
            </label>
            <div className="flex items-center space-x-2">
              <input
                type="text"
                value={manualInput}
                onChange={(e) => setManualInput(e.target.value)}
                placeholder='e.g. "Support tickets filter karo", "एनालिटिक्स खोलो", "Sync hostinger webmail"'
                className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <button
                type="submit"
                disabled={!manualInput.trim() || isProcessing}
                className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-bold text-xs rounded-xl transition-all cursor-pointer flex items-center space-x-1.5 shrink-0"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Execute</span>
              </button>
            </div>
          </form>

          {/* Last Executed Voice Action Output */}
          {lastResult && (
            <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-2 animate-in fade-in">
              <div className="flex items-center justify-between text-xs border-b border-slate-800 pb-2">
                <div className="flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span className="font-bold text-white">Action Executed:</span>
                  <span className="font-mono text-amber-300 font-bold bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/30">
                    {lastResult.action}
                  </span>
                </div>
                {lastResult.tab && (
                  <span className="text-[10px] text-slate-400 font-mono">
                    Target Tab: {lastResult.tab}
                  </span>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs pt-1">
                <div className="p-2.5 bg-slate-900 rounded-lg border border-slate-800/80">
                  <span className="text-[10px] text-slate-400 uppercase font-bold block mb-1">
                    🇮🇳 Hindi Response:
                  </span>
                  <p className="text-slate-200 text-xs font-sans">
                    {lastResult.spokenResponseHindi}
                  </p>
                </div>

                <div className="p-2.5 bg-slate-900 rounded-lg border border-slate-800/80">
                  <span className="text-[10px] text-slate-400 uppercase font-bold block mb-1">
                    🌐 English Response:
                  </span>
                  <p className="text-slate-200 text-xs font-sans">
                    {lastResult.spokenResponseEnglish}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Quick Voice Command Cheat Sheet Chips */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-1.5 text-xs font-bold text-slate-300">
                <Zap className="w-4 h-4 text-amber-400" />
                <span>Quick Voice Command Chips (Click to test):</span>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {/* Hindi Commands */}
              <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1.5">
                <span className="text-[10px] font-bold text-sky-400 uppercase tracking-wider block border-b border-slate-800 pb-1">
                  🇮🇳 Hindi Commands
                </span>
                <div className="flex flex-col gap-1 text-xs">
                  <button
                    onClick={() => handleQuickChipClick('एनालिटिक्स खोलो')}
                    className="text-left px-2 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white transition-colors cursor-pointer text-[11px]"
                  >
                    • "एनालिटिक्स खोलो"
                  </button>
                  <button
                    onClick={() => handleQuickChipClick('सपोर्ट टिकट दिखाओ')}
                    className="text-left px-2 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white transition-colors cursor-pointer text-[11px]"
                  >
                    • "सपोर्ट टिकट दिखाओ"
                  </button>
                  <button
                    onClick={() => handleQuickChipClick('वेबमेल सिंक करो')}
                    className="text-left px-2 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white transition-colors cursor-pointer text-[11px]"
                  >
                    • "वेबमेल सिंक करो"
                  </button>
                  <button
                    onClick={() => handleQuickChipClick('सभी फ़िल्टर हटाओ')}
                    className="text-left px-2 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white transition-colors cursor-pointer text-[11px]"
                  >
                    • "सभी फ़िल्टर हटाओ"
                  </button>
                </div>
              </div>

              {/* Hinglish Commands */}
              <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1.5">
                <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider block border-b border-slate-800 pb-1">
                  🗣️ Hinglish Commands
                </span>
                <div className="flex flex-col gap-1 text-xs">
                  <button
                    onClick={() => handleQuickChipClick('Dashboard open karo')}
                    className="text-left px-2 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white transition-colors cursor-pointer text-[11px]"
                  >
                    • "Dashboard open karo"
                  </button>
                  <button
                    onClick={() => handleQuickChipClick('Support grievance filter karo')}
                    className="text-left px-2 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white transition-colors cursor-pointer text-[11px]"
                  >
                    • "Support grievance filter karo"
                  </button>
                  <button
                    onClick={() => handleQuickChipClick('Hostinger mail sync karo')}
                    className="text-left px-2 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white transition-colors cursor-pointer text-[11px]"
                  >
                    • "Hostinger mail sync karo"
                  </button>
                  <button
                    onClick={() => handleQuickChipClick('Critical tickets dikhao')}
                    className="text-left px-2 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white transition-colors cursor-pointer text-[11px]"
                  >
                    • "Critical tickets dikhao"
                  </button>
                </div>
              </div>

              {/* English Commands */}
              <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1.5">
                <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider block border-b border-slate-800 pb-1">
                  🌐 English Commands
                </span>
                <div className="flex flex-col gap-1 text-xs">
                  <button
                    onClick={() => handleQuickChipClick('Show WhatsApp intake')}
                    className="text-left px-2 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white transition-colors cursor-pointer text-[11px]"
                  >
                    • "Show WhatsApp intake"
                  </button>
                  <button
                    onClick={() => handleQuickChipClick('Filter Enquiry category')}
                    className="text-left px-2 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white transition-colors cursor-pointer text-[11px]"
                  >
                    • "Filter Enquiry category"
                  </button>
                  <button
                    onClick={() => handleQuickChipClick('Export CSV report')}
                    className="text-left px-2 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white transition-colors cursor-pointer text-[11px]"
                  >
                    • "Export CSV report"
                  </button>
                  <button
                    onClick={() => handleQuickChipClick('Open AI Engine settings')}
                    className="text-left px-2 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white transition-colors cursor-pointer text-[11px]"
                  >
                    • "Open AI Engine settings"
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Command Log History */}
          {commandHistory.length > 0 && (
            <div className="space-y-2 pt-2 border-t border-slate-800">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block">
                Recent Voice Logs
              </span>
              <div className="space-y-1.5">
                {commandHistory.map((item) => (
                  <div
                    key={item.id}
                    className="p-2.5 bg-slate-950 rounded-lg border border-slate-800 flex items-center justify-between text-xs"
                  >
                    <div className="flex items-center space-x-2">
                      <Radio className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                      <span className="text-slate-200 font-mono">"{item.query}"</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-500/10 text-indigo-300 border border-indigo-500/30">
                        {item.result.action}
                      </span>
                      <span className="text-[10px] text-slate-500 font-mono">{item.time}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
};

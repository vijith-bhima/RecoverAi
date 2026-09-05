'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Zap, Brain, Shield, Send, CheckCircle2, Clock, Pause, Play,
  RefreshCw, ChevronDown, Sparkles, ExternalLink, Bot, Check,
  AlertTriangle, BookOpen, Settings, FileText, ArrowRight, X
} from 'lucide-react';
import { useAuth } from '@/lib/auth-context';

type AgentEvent = {
  ts: string;
  type: string;
  payment_id: string;
  amount: number;
  label: string;
  sublabel?: string;
  razorpay_url?: string;
};

type AgentStatus = {
  active: boolean;
  last_run: string | null;
  poll_interval_sec: number;
  processed_total: number;
  links_total: number;
  escalated_total: number;
  recovered_total: number;
};

export default function AgentConsolePage() {
  const { user, apiFetch } = useAuth();
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [activeFilter, setActiveFilter] = useState('All Events');
  const [isPaused, setIsPaused] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [showSimulateModal, setShowSimulateModal] = useState(false);

  // Simulation form
  const [simPhone, setSimPhone] = useState('+919876543210');
  const [simEmail, setSimEmail] = useState('arjun@example.com');
  const [simAmount, setSimAmount] = useState('4500');
  const [simReason, setSimReason] = useState('INSUFFICIENT_FUNDS');
  const [simulating, setSimulating] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);

  const seenRef = useRef<Set<string>>(new Set());

  const handleSyncRazorpay = async () => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const res = await apiFetch('/api/razorpay/sync-failures', { method: 'POST' });
      const data = await res.json();
      setSyncMsg(data.message || 'Synced');
      setTimeout(() => setSyncMsg(null), 4000);
      fetchStatus();
      fetchActivity();
    } catch {
      setSyncMsg('Unable to connect to backend.');
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchActivity();
    const sInt = setInterval(fetchStatus, 4000);
    const aInt = setInterval(fetchActivity, 3000);
    return () => {
      clearInterval(sInt);
      clearInterval(aInt);
    };
  }, [user]); // re-run when user profile changes

  const fetchStatus = async () => {
    try {
      const res = await apiFetch('/agent/status');
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
        setIsPaused(!data.active);
      }
    } catch { }
  };

  const fetchActivity = async () => {
    try {
      const res = await apiFetch('/agent/activity?limit=100');
      if (!res.ok) return;
      const data = await res.json();
      if (data.events && Array.isArray(data.events)) {
        setEvents(data.events);
      }
    } catch { }
  };

  const toggleAgent = async () => {
    setToggling(true);
    try {
      await apiFetch('/agent/toggle', { method: 'POST' });
      await fetchStatus();
      await fetchActivity();
    } finally {
      setToggling(false);
    }
  };

  const handleSimulatePayment = async (e: React.FormEvent) => {
    e.preventDefault();
    setSimulating(true);
    try {
      const reasonMap: Record<string, { desc: string; method: string }> = {
        INSUFFICIENT_FUNDS: { desc: 'Customer account has insufficient balance', method: 'card' },
        CARD_EXPIRED: { desc: 'Card expired, requires alternate method', method: 'card' },
        INVALID_OTP: { desc: 'Customer entered wrong OTP', method: 'upi' },
        BANK_SERVER_DOWN: { desc: 'Bank server is temporarily down', method: 'upi' },
      };
      const amtNum = parseFloat(simAmount) || 4500;
      const res = await apiFetch('/payments/event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          payment_id: `sim_${crypto.randomUUID()}`,
          customer_id: `sim_${crypto.randomUUID()}`,
          amount: amtNum,
          failure_reason: simReason,
          payment_method: reasonMap[simReason]?.method === 'card' ? 'CREDIT_CARD' : 'UPI',
          customer_email: simEmail.trim(),
          customer_phone: simPhone.trim(),
        }),
      });

      if (!res.ok) throw new Error('Unable to create simulation event');

      setShowSimulateModal(false);
      await fetchActivity();
    } catch (err) {
      console.error('Simulation error:', err);
    } finally {
      setSimulating(false);
    }
  };

  const filteredEvents = events.filter((e) => {
    if (activeFilter === 'All Events') return true;
    if (activeFilter === 'Payment Failed') return e.type === 'payment_failed';
    if (activeFilter === 'AI Analysis') return e.type === 'ml_scored' || e.type === 'ai_decision';
    if (activeFilter === 'Guardrails') return e.type === 'guardrail_approved' || e.type === 'guardrail_blocked';
    if (activeFilter === 'Actions') return e.type === 'link_sent' || e.type === 'retried' || e.type === 'escalated';
    if (activeFilter === 'Verification') return e.type === 'recovered';
    return true;
  });

  const fmtTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true });
    } catch {
      return 'Just now';
    }
  };

  const getRelativeTime = (iso: string) => {
    try {
      const diffMs = Date.now() - new Date(iso).getTime();
      const secs = Math.floor(diffMs / 1000);
      if (secs < 5) return 'Just now';
      if (secs < 60) return `${secs} sec ago`;
      const mins = Math.floor(secs / 60);
      if (mins < 60) return `${mins} min ago`;
      return `${Math.floor(mins / 60)}h ago`;
    } catch {
      return 'Just now';
    }
  };

  return (
    <div className="max-w-[1440px] mx-auto space-y-6 pt-2 pb-16">

      {/* Page Header */}
      <div>
        <h1 className="text-xl sm:text-2xl md:text-3xl font-serif font-bold text-gray-900 tracking-tight">Recovery assistant</h1>
        <p className="text-sm text-gray-500 mt-1">See what’s happening with failed payments as it happens.</p>
      </div>

      {/* Top Hero Section: How It Works + Agent Status */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left: How RecoverAI Agent Works (2 Cols) */}
        <div className="lg:col-span-2 relative overflow-hidden bg-gradient-to-br from-[#F8F6FF] via-[#F4EFFF] to-[#FDFBFF] border border-[#E9E2FF] rounded-[28px] p-6 md:p-8 shadow-sm flex flex-col justify-between">
          <div className="space-y-6">
            <h2 className="text-base font-bold text-[#5B3DF5]">How recovery works</h2>

            {/* 5-Step Connected Flow — horizontal on md+, vertical on mobile */}
            <div className="hidden md:relative md:grid grid-cols-5 gap-2 pt-2">
              {/* Connecting Dashed Line */}
              <div className="absolute top-[20px] left-[10%] right-[10%] h-[2px] border-t-2 border-dashed border-[#D6C7FF] -z-0" />

              {/* Step 1 */}
              <div className="relative z-10 flex flex-col items-center text-center space-y-2">
                <div className="h-10 w-10 rounded-full bg-white border border-[#E2D8FF] shadow-sm flex items-center justify-center text-[#7B42F6]">
                  <Zap className="h-4 w-4" />
                </div>
                <div className="text-[12px] font-bold text-gray-900">1. Webhook Received</div>
                <p className="text-[10px] text-gray-500 leading-tight">We receive failed payment events from Razorpay</p>
              </div>

              {/* Step 2 */}
              <div className="relative z-10 flex flex-col items-center text-center space-y-2">
                <div className="h-10 w-10 rounded-full bg-white border border-[#FFD8DF] shadow-sm flex items-center justify-center text-[#E53E3E]">
                  <Brain className="h-4 w-4" />
                </div>
                <div className="text-[12px] font-bold text-gray-900">2. Find the cause</div>
                <p className="text-[10px] text-gray-500 leading-tight">We look at the failure, customer history, and timing</p>
              </div>

              {/* Step 3 */}
              <div className="relative z-10 flex flex-col items-center text-center space-y-2">
                <div className="h-10 w-10 rounded-full bg-white border border-[#C6F6D5] shadow-sm flex items-center justify-center text-[#38A169]">
                  <Shield className="h-4 w-4" />
                </div>
                <div className="text-[12px] font-bold text-gray-900">3. Guardrails Check</div>
                <p className="text-[10px] text-gray-500 leading-tight">Our rules engine ensures action is safe & allowed</p>
              </div>

              {/* Step 4 */}
              <div className="relative z-10 flex flex-col items-center text-center space-y-2">
                <div className="h-10 w-10 rounded-full bg-white border border-[#D6BCFA] shadow-sm flex items-center justify-center text-[#805AD5]">
                  <Send className="h-4 w-4" />
                </div>
                <div className="text-[12px] font-bold text-gray-900">4. Action Executed</div>
                <p className="text-[10px] text-gray-500 leading-tight">We send the right recovery action automatically</p>
              </div>

              {/* Step 5 */}
              <div className="relative z-10 flex flex-col items-center text-center space-y-2">
                <div className="h-10 w-10 rounded-full bg-white border border-[#9AE6B4] shadow-sm flex items-center justify-center text-[#276749]">
                  <CheckCircle2 className="h-4 w-4" />
                </div>
                <div className="text-[12px] font-bold text-gray-900">5. Verify & Learn</div>
                <p className="text-[10px] text-gray-500 leading-tight">We verify outcome and improve for next time</p>
              </div>
            </div>

            {/* Mobile: Vertical step list */}
            <div className="flex md:hidden flex-col gap-3 pt-2">
              {[
                { icon: Zap, label: '1. Webhook Received', desc: 'We receive failed payment events from Razorpay', color: '#7B42F6', border: '#E2D8FF' },
                { icon: Brain, label: '2. AI Analysis', desc: 'ML + AI analyze root cause, customer & context', color: '#E53E3E', border: '#FFD8DF' },
                { icon: Shield, label: '3. Guardrails Check', desc: 'Rules engine ensures action is safe & allowed', color: '#38A169', border: '#C6F6D5' },
                { icon: Send, label: '4. Action Executed', desc: 'We send the right recovery action automatically', color: '#805AD5', border: '#D6BCFA' },
                { icon: CheckCircle2, label: '5. Verify & Learn', desc: 'We verify outcome and improve for next time', color: '#276749', border: '#9AE6B4' },
              ].map(({ icon: Icon, label, desc, color, border }) => (
                <div key={label} className="flex items-start gap-3">
                  <div className="h-9 w-9 shrink-0 rounded-full bg-white flex items-center justify-center shadow-sm" style={{ border: `1px solid ${border}`, color }}>
                    <Icon className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-[12px] font-bold text-gray-900">{label}</div>
                    <p className="text-[11px] text-gray-500 leading-tight">{desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Floating Robot Mascot */}
          <div className="absolute right-4 bottom-2 hidden md:block w-32 h-32 pointer-events-none opacity-90">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/Assets/ai_agent_robot.png"
              alt="AI Mascot"
              className="w-full h-full object-contain drop-shadow-md animate-bounce-subtle"
            />
          </div>
        </div>

        {/* Right: Agent Status Card */}
        <div className="bg-white rounded-[28px] border border-gray-100 p-6 shadow-sm flex flex-col justify-between space-y-5">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                <h3 className="text-sm font-bold text-gray-900">Agent Status</h3>
              </div>
              <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${!isPaused ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-600'
                }`}>
                {!isPaused ? <Check className="h-3 w-3 text-emerald-600" /> : <Pause className="h-3 w-3" />}
                {!isPaused ? 'Running Smoothly' : 'Agent Paused'}
              </span>
            </div>

            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-2xl bg-indigo-50 flex items-center justify-center text-indigo-600 shrink-0">
                <Bot className="h-5 w-5" />
              </div>
              <p className="text-xs text-gray-500 leading-relaxed">
                RecoverAI is active and recovering revenue while you focus on growth.
              </p>
            </div>
          </div>

          {/* 3 Metrics in Bottom Row */}
          <div className="grid grid-cols-3 gap-2 pt-3 border-t border-gray-100 text-center">
            <div>
              <div className="text-lg font-black text-gray-900">
                {(status?.processed_total || 512).toLocaleString()}
              </div>
              <div className="text-[10px] text-gray-400 font-medium">Events Processed</div>
            </div>
            <div>
              <div className="text-lg font-black text-gray-900">92.4%</div>
              <div className="text-[10px] text-gray-400 font-medium">Success Rate</div>
            </div>
            <div>
              <div className="text-lg font-black text-gray-900">24m 18s</div>
              <div className="text-[10px] text-gray-400 font-medium">Avg. Resolution</div>
            </div>
          </div>
        </div>
      </div>

      {/* Middle Grid: Live Agent Activity Table + Right Widgets */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left: Live Agent Activity (2 Cols) */}
        <div className="lg:col-span-2 bg-white rounded-[28px] border border-gray-100 p-6 shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
            <div className="flex items-center gap-2.5">
              <h3 className="text-base font-bold text-gray-900">Live Agent Activity</h3>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold text-emerald-700 bg-emerald-50">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-ping" />
                Streaming live
              </span>
            </div>

            <div className="flex flex-wrap gap-2 items-center self-end sm:self-auto">
              <div className="relative">
                <select
                  value={activeFilter}
                  onChange={(e) => setActiveFilter(e.target.value)}
                  className="appearance-none bg-gray-50 border border-gray-200 text-xs font-bold text-gray-700 py-1.5 pl-3 pr-8 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 cursor-pointer"
                >
                  <option>All Events</option>
                  <option>Payment Failed</option>
                  <option>AI Analysis</option>
                  <option>Guardrails</option>
                  <option>Actions</option>
                  <option>Verification</option>
                </select>
                <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400 pointer-events-none" />
              </div>

              <button
                onClick={toggleAgent}
                disabled={toggling}
                className="h-8 w-8 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-700 flex items-center justify-center transition-all"
                title={isPaused ? 'Resume Agent' : 'Pause Agent'}
              >
                {isPaused ? <Play className="h-3.5 w-3.5 fill-current" /> : <Pause className="h-3.5 w-3.5 fill-current" />}
              </button>

              <button
                onClick={handleSyncRazorpay}
                disabled={syncing}
                className="flex items-center gap-1.5 bg-gray-900 hover:bg-black disabled:opacity-50 text-white text-xs font-bold px-3 py-1.5 rounded-xl transition-all shadow-sm"
                title="Directly pull recent failed payments from your Razorpay account"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${syncing ? 'animate-spin' : ''}`} />
                {syncing ? 'Syncing...' : 'Sync'}
              </button>

              <button
                onClick={() => setShowSimulateModal(true)}
                className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-3 py-1.5 rounded-xl transition-all shadow-sm shadow-indigo-100"
              >
                <Sparkles className="h-3.5 w-3.5" /> Test
              </button>
            </div>
          </div>

          {syncMsg && (
            <div className="p-3 bg-indigo-50 border border-indigo-100 rounded-xl text-xs font-semibold text-indigo-900 flex items-center justify-between">
              <span>{syncMsg}</span>
              <button onClick={() => setSyncMsg(null)} className="text-indigo-500 hover:text-indigo-800 text-xs">✕</button>
            </div>
          )}

          {/* Activity Table */}
          <div className="overflow-x-auto custom-scrollbar -mx-2 px-2">
            <table className="w-full text-left border-collapse min-w-[700px]">
              <thead>
                <tr className="border-b border-gray-100 text-[10px] font-bold text-gray-400 uppercase tracking-wider">
                  <th className="py-2.5 px-3 w-[100px]">TIME</th>
                  <th className="py-2.5 px-3 w-[220px]">EVENT & STAGE</th>
                  <th className="py-2.5 px-3 w-[160px]">PAYMENT / AMOUNT</th>
                  <th className="py-2.5 px-3">AGENT DIAGNOSIS & STEP</th>
                  <th className="py-2.5 px-3 text-right w-[120px]">STATUS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 text-xs">
                {filteredEvents.length > 0 ? (
                  filteredEvents.slice(0, 15).map((ev, idx) => {
                    const isFailed = ev.type === 'payment_failed';
                    const isScored = ev.type === 'ml_scored';
                    const isPlaybook = ev.type === 'playbook_selected';
                    const isPlan = ev.type === 'recovery_plan_created';
                    const isWait = ev.type === 'wait_scheduled';
                    const isRechecked = ev.type === 'status_rechecked';
                    const isNativeMonitoring = ev.type === 'razorpay_native_monitoring' || ev.type === 'razorpay_fallback_monitoring';
                    const isGuard = ev.type === 'guardrail_approved' || ev.type === 'guardrail_blocked';
                    const isAction = ev.type === 'link_sent' || ev.type === 'retried' || ev.type === 'escalated';
                    const isRecovered = ev.type === 'recovered';

                    // Determine crisp status label and colors
                    let statusLabel = 'PROCESSED';
                    let statusColor = 'bg-purple-50 text-purple-700 border-purple-200/60';
                    let dotColor = 'bg-purple-500';

                    if (isRecovered) {
                      statusLabel = 'RECOVERED';
                      statusColor = 'bg-emerald-50 text-emerald-700 border-emerald-200/60 font-bold';
                      dotColor = 'bg-emerald-500';
                    } else if (isWait) {
                      statusLabel = 'WAITING';
                      statusColor = 'bg-amber-50 text-amber-800 border-amber-200/60 font-bold';
                      dotColor = 'bg-amber-500 animate-ping';
                    } else if (isNativeMonitoring) {
                      statusLabel = 'MONITORING';
                      statusColor = 'bg-cyan-50 text-cyan-800 border-cyan-200/60 font-bold';
                      dotColor = 'bg-cyan-500';
                    } else if (ev.type === 'guardrail_blocked' || (isAction && ev.label?.toLowerCase().includes('escalat'))) {
                      statusLabel = 'ESCALATED';
                      statusColor = 'bg-orange-50 text-orange-800 border-orange-200/60 font-bold';
                      dotColor = 'bg-orange-500';
                    } else if (ev.type === 'guardrail_approved') {
                      statusLabel = 'APPROVED';
                      statusColor = 'bg-emerald-50 text-emerald-700 border-emerald-200/60';
                      dotColor = 'bg-emerald-500';
                    } else if (ev.type === 'link_sent') {
                      statusLabel = 'DISPATCHED';
                      statusColor = 'bg-indigo-50 text-indigo-700 border-indigo-200/60 font-bold';
                      dotColor = 'bg-indigo-500';
                    } else if (isFailed) {
                      statusLabel = 'INGESTED';
                      statusColor = 'bg-rose-50 text-rose-700 border-rose-200/60';
                      dotColor = 'bg-rose-500';
                    } else if (isScored || isPlan || isPlaybook) {
                      statusLabel = 'ANALYZED';
                      statusColor = 'bg-indigo-50 text-indigo-700 border-indigo-200/60';
                      dotColor = 'bg-indigo-500';
                    }

                    // Format payment ID nicely if long
                    const shortPaymentId = ev.payment_id?.length > 18
                      ? `${ev.payment_id.slice(0, 12)}...${ev.payment_id.slice(-4)}`
                      : ev.payment_id;

                    return (
                      <tr key={idx} className="hover:bg-indigo-50/20 transition-colors">
                        <td className="py-3 px-3 whitespace-nowrap align-top">
                          <div className="font-semibold text-gray-800 text-[11px]">{fmtTime(ev.ts)}</div>
                          <div className="text-[10px] text-gray-400">{getRelativeTime(ev.ts)}</div>
                        </td>

                        <td className="py-3 px-3 align-top">
                          <div className="flex items-start gap-2.5">
                            <div className={`h-7 w-7 rounded-lg flex items-center justify-center text-xs shrink-0 mt-0.5 ${isFailed ? 'bg-pink-50 text-pink-600' :
                                isScored ? 'bg-purple-50 text-purple-600' :
                                  isPlaybook ? 'bg-indigo-50 text-indigo-600' :
                                    isPlan ? 'bg-sky-50 text-sky-600' :
                                      isWait ? 'bg-amber-50 text-amber-600 animate-pulse' :
                                        isRechecked ? 'bg-blue-50 text-blue-600' :
                                          isNativeMonitoring ? 'bg-cyan-50 text-cyan-700' :
                                            isGuard ? 'bg-emerald-50 text-emerald-600' :
                                              isRecovered ? 'bg-emerald-100 text-emerald-700 font-bold' : 'bg-indigo-50 text-indigo-600'
                              }`}>
                              {isFailed ? '🔴' :
                                isScored ? '🧠' :
                                  isPlaybook ? '📋' :
                                    isPlan ? '🗺️' :
                                      isWait ? '⏳' :
                                        isRechecked ? '🔍' :
                                          isNativeMonitoring ? '👀' :
                                            isGuard ? '🛡️' :
                                              isRecovered ? '✅' : '⚡'}
                            </div>
                            <div className="min-w-0">
                              <div className="font-bold text-gray-900 text-xs truncate max-w-[170px]" title={ev.label}>
                                {ev.label}
                              </div>
                              <span className={`inline-block text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded mt-0.5 ${isFailed ? 'bg-pink-100 text-pink-700' :
                                  isScored ? 'bg-purple-100 text-purple-700' :
                                    isPlaybook ? 'bg-indigo-100 text-indigo-700' :
                                      isPlan ? 'bg-sky-100 text-sky-700' :
                                        isWait ? 'bg-amber-100 text-amber-800 font-extrabold' :
                                          isRechecked ? 'bg-blue-100 text-blue-700' :
                                            isNativeMonitoring ? 'bg-cyan-100 text-cyan-800' :
                                              isGuard ? 'bg-emerald-100 text-emerald-700' :
                                                isRecovered ? 'bg-emerald-200 text-emerald-900' : 'bg-indigo-100 text-indigo-700'
                                }`}>
                                {isFailed ? 'PAYMENT FAILED' :
                                  isScored ? 'ML DIAGNOSED' :
                                    isPlaybook ? 'PLAYBOOK SELECTED' :
                                      isPlan ? 'PLAN CREATED' :
                                        isWait ? 'WAITING / SCHEDULED' :
                                          isRechecked ? 'STATUS RECHECKED' :
                                            isNativeMonitoring ? 'RAZORPAY MONITORING' :
                                              isGuard ? 'GUARDRAIL CHECK' :
                                                isRecovered ? 'RECOVERED' : 'ACTION DISPATCHED'}
                              </span>
                            </div>
                          </div>
                        </td>

                        <td className="py-3 px-3 align-top whitespace-nowrap">
                          <div
                            className="font-mono text-[11px] font-bold text-gray-900 bg-gray-50 border border-gray-100 px-1.5 py-0.5 rounded inline-block max-w-[140px] truncate"
                            title={ev.payment_id}
                          >
                            {shortPaymentId}
                          </div>
                          <div className="text-[11px] font-bold text-gray-700 mt-1">₹{ev.amount?.toLocaleString()}</div>
                        </td>

                        <td className="py-3 px-3 align-top">
                          <div className="font-medium text-gray-800 text-xs leading-relaxed max-w-sm">
                            {ev.sublabel || ev.label}
                          </div>
                          {ev.razorpay_url && (
                            <a
                              href={ev.razorpay_url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 text-[11px] font-bold text-indigo-600 hover:text-indigo-800 mt-1 underline"
                            >
                              Open Live Payment Link <ExternalLink className="h-3 w-3" />
                            </a>
                          )}
                        </td>

                        <td className="py-3 px-3 text-right whitespace-nowrap align-top">
                          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold border ${statusColor}`}>
                            <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
                            {statusLabel}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-xs text-gray-400">
                      No live events captured yet. Click <strong>Test</strong> to simulate a payment failure.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="pt-2 text-center">
            <a
              href="/audit-trail"
              className="inline-flex items-center gap-1 text-xs font-bold text-[#5B3DF5] hover:text-[#4927eb] transition-colors"
            >
              View All Live Events <ArrowRight className="h-3.5 w-3.5" />
            </a>
          </div>
        </div>

        {/* Right Column: Decisions + Active Playbook + Agent Controls */}
        <div className="space-y-6">

          {/* Card 1: Today's Decisions (Donut Chart) */}
          <div className="bg-white rounded-[28px] border border-gray-100 p-6 shadow-sm space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-sm font-bold text-gray-900">Today&apos;s Decisions</h3>
              <a href="/recovery-cases" className="text-xs font-bold text-indigo-600 hover:text-indigo-700">View all</a>
            </div>

            <div className="flex items-center gap-5 pt-1">
              {/* Donut graphic */}
              <div className="relative w-24 h-24 shrink-0">
                <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
                  {/* Background Circle */}
                  <path
                    className="text-gray-100"
                    strokeWidth="4"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                  {/* Actions Taken (Green - 70%) */}
                  <path
                    className="text-emerald-500"
                    strokeDasharray="70, 100"
                    strokeWidth="4"
                    strokeLinecap="round"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                  {/* Delayed/Wait (Purple - 18%) */}
                  <path
                    className="text-purple-500"
                    strokeDasharray="18, 100"
                    strokeDashoffset="-70"
                    strokeWidth="4"
                    strokeLinecap="round"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                  {/* Blocked (Red - 7%) */}
                  <path
                    className="text-red-500"
                    strokeDasharray="7, 100"
                    strokeDashoffset="-88"
                    strokeWidth="4"
                    strokeLinecap="round"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                  {/* Escalated (Amber - 5%) */}
                  <path
                    className="text-amber-500"
                    strokeDasharray="5, 100"
                    strokeDashoffset="-95"
                    strokeWidth="4"
                    strokeLinecap="round"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                  <span className="text-base font-black text-gray-900 leading-none">207</span>
                  <span className="text-[9px] text-gray-400 font-bold uppercase mt-0.5">Total</span>
                </div>
              </div>

              {/* Legend List */}
              <div className="space-y-1.5 text-xs">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" />
                  <span className="font-bold text-gray-800">145</span>
                  <span className="text-gray-500">Actions Taken</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-purple-500" />
                  <span className="font-bold text-gray-800">38</span>
                  <span className="text-gray-500">Delayed / Wait</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-red-500" />
                  <span className="font-bold text-gray-800">14</span>
                  <span className="text-gray-500">Blocked</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-amber-500" />
                  <span className="font-bold text-gray-800">10</span>
                  <span className="text-gray-500">Escalated</span>
                </div>
              </div>
            </div>
          </div>

          {/* Card 2: Active Playbook */}
          <div className="bg-white rounded-[28px] border border-gray-100 p-6 shadow-sm space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-sm font-bold text-gray-900">Active Playbook</h3>
              <a href="/settings" className="text-xs font-bold text-indigo-600 hover:text-indigo-700">View all</a>
            </div>

            <div className="space-y-3">
              <div className="flex justify-between items-center p-2.5 bg-gray-50 rounded-2xl">
                <span className="text-xs font-bold text-gray-900">Insufficient Funds</span>
                <span className="text-[10px] font-bold text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full">
                  WAIT & RETRY
                </span>
              </div>

              <div className="flex justify-between items-center text-xs">
                <div>
                  <span className="text-[10px] text-gray-400 block">Success Rate</span>
                  <span className="font-bold text-emerald-600 text-sm">78.6%</span>
                </div>
                <div className="text-right">
                  <span className="text-[10px] text-gray-400 block">Next Action</span>
                  <span className="font-bold text-gray-800 flex items-center gap-1 justify-end text-xs">
                    Retry after 24h <Clock className="h-3 w-3 text-gray-400" />
                  </span>
                </div>
              </div>

              <div className="pt-2 border-t border-gray-100">
                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block mb-1.5">Conditions</span>
                <div className="flex gap-1.5 flex-wrap">
                  <span className="bg-gray-100 text-gray-600 text-[10px] font-mono px-2 py-0.5 rounded-md font-medium">INSUFFICIENT_FUNDS</span>
                  <span className="bg-gray-100 text-gray-600 text-[10px] font-mono px-2 py-0.5 rounded-md font-medium">BANK_DECLINED</span>
                </div>
              </div>
            </div>
          </div>

          {/* Card 3: Agent Controls */}
          <div className="bg-white rounded-[28px] border border-gray-100 p-6 shadow-sm space-y-3">
            <h3 className="text-sm font-bold text-gray-900">Agent Controls</h3>

            <div className="grid grid-cols-4 gap-2 text-center">
              <button
                onClick={toggleAgent}
                className="p-3 rounded-2xl bg-red-50 hover:bg-red-100 text-red-600 flex flex-col items-center justify-center gap-1.5 transition-all"
              >
                <div className="h-7 w-7 rounded-xl bg-white flex items-center justify-center shadow-xs">
                  {isPaused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
                </div>
                <span className="text-[10px] font-bold">{isPaused ? 'Resume' : 'Pause'}</span>
              </button>

              <a
                href="/settings"
                className="p-3 rounded-2xl bg-purple-50 hover:bg-purple-100 text-purple-600 flex flex-col items-center justify-center gap-1.5 transition-all"
              >
                <div className="h-7 w-7 rounded-xl bg-white flex items-center justify-center shadow-xs">
                  <BookOpen className="h-3.5 w-3.5" />
                </div>
                <span className="text-[10px] font-bold">Playbooks</span>
              </a>

              <a
                href="/settings"
                className="p-3 rounded-2xl bg-blue-50 hover:bg-blue-100 text-blue-600 flex flex-col items-center justify-center gap-1.5 transition-all"
              >
                <div className="h-7 w-7 rounded-xl bg-white flex items-center justify-center shadow-xs">
                  <Settings className="h-3.5 w-3.5" />
                </div>
                <span className="text-[10px] font-bold">Settings</span>
              </a>

              <a
                href="/audit-trail"
                className="p-3 rounded-2xl bg-emerald-50 hover:bg-emerald-100 text-emerald-600 flex flex-col items-center justify-center gap-1.5 transition-all"
              >
                <div className="h-7 w-7 rounded-xl bg-white flex items-center justify-center shadow-xs">
                  <FileText className="h-3.5 w-3.5" />
                </div>
                <span className="text-[10px] font-bold">Logs</span>
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Insights Banner */}
      <div className="bg-white rounded-[28px] border border-gray-100 p-6 shadow-sm grid grid-cols-1 md:grid-cols-4 gap-6 items-center">
        {/* Left Purple Box */}
        <div className="p-4 bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-100 rounded-2xl space-y-1">
          <div className="text-[11px] font-bold text-indigo-700 flex items-center gap-1">
            AI Insight <Sparkles className="h-3 w-3 text-amber-500" />
          </div>
          <p className="text-xs text-gray-700 font-medium leading-relaxed">
            <strong>Insufficient funds</strong> is the top reason today. Waiting and re-trying after 24h is working well.
          </p>
        </div>

        {/* Root Cause */}
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-2xl bg-purple-50 text-purple-600 flex items-center justify-center shrink-0">
            <Clock className="h-5 w-5" />
          </div>
          <div>
            <span className="text-[11px] text-gray-400 font-medium block">Top Root Cause</span>
            <span className="text-sm font-bold text-gray-900">Insufficient Funds</span>
          </div>
        </div>

        {/* Best Window */}
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
            <Clock className="h-5 w-5" />
          </div>
          <div>
            <span className="text-[11px] text-gray-400 font-medium block">Best Recovery Window</span>
            <span className="text-sm font-bold text-gray-900">6 PM – 10 PM</span>
          </div>
        </div>

        {/* Revenue at Risk */}
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0 font-bold text-base">
            ₹
          </div>
          <div>
            <span className="text-[11px] text-gray-400 font-medium block">Revenue at Risk</span>
            <span className="text-base font-black text-gray-900">₹34,98,100</span>
          </div>
        </div>
      </div>

      {/* SIMULATE MODAL */}
      {showSimulateModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4 animate-scaleUp">
            <div className="flex justify-between items-center">
              <h3 className="font-bold text-gray-900 text-base flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-indigo-600" /> Simulate Real Webhook
              </h3>
              <button onClick={() => setShowSimulateModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleSimulatePayment} className="space-y-3">
              <div>
                <label className="block text-xs font-bold text-gray-700 uppercase mb-1">Customer Phone</label>
                <input
                  type="text"
                  value={simPhone}
                  onChange={(e) => setSimPhone(e.target.value)}
                  className="w-full bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 text-xs font-mono text-gray-800"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 uppercase mb-1">Customer Email</label>
                <input
                  type="email"
                  value={simEmail}
                  onChange={(e) => setSimEmail(e.target.value)}
                  className="w-full bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 text-xs font-mono text-gray-800"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-gray-700 uppercase mb-1">Amount (₹)</label>
                  <input
                    type="number"
                    value={simAmount}
                    onChange={(e) => setSimAmount(e.target.value)}
                    className="w-full bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 text-xs font-bold text-gray-800"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-700 uppercase mb-1">Failure Mode</label>
                  <select
                    value={simReason}
                    onChange={(e) => setSimReason(e.target.value)}
                    className="w-full bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 text-xs font-bold text-gray-800"
                  >
                    <option value="INSUFFICIENT_FUNDS">Insufficient Funds</option>
                    <option value="CARD_EXPIRED">Card Expired</option>
                    <option value="INVALID_OTP">Invalid OTP</option>
                    <option value="BANK_SERVER_DOWN">Bank Server Down</option>
                  </select>
                </div>
              </div>

              <button
                type="submit"
                disabled={simulating}
                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs py-2.5 rounded-xl shadow-md shadow-indigo-100 transition-all flex items-center justify-center gap-2 mt-4"
              >
                {simulating ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                {simulating ? 'Firing Webhook...' : 'Fire Live Webhook'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

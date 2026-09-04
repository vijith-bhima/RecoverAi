'use client';

import React, { useState, useEffect } from 'react';
import {
  Search, Filter, ClipboardList, RefreshCcw, Hourglass,
  ShieldAlert, ShoppingCart, Zap, CheckCircle2, AlertTriangle,
  ArrowRight, ExternalLink, X, Send, Play, Check
} from 'lucide-react';
import { useAuth } from '@/lib/auth-context';

type CaseItem = {
  payment_id: string;
  customer_id: string;
  amount: number;
  failure_reason: string;
  payment_method: string;
  status: string;
  timestamp: string;
  previous_attempts: number;
  reason?: string;
  event_type?: string;
};

export default function RecoveryCasesPage() {
  const { user, apiFetch } = useAuth();
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [escalations, setEscalations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterTab, setFilterTab] = useState<'all' | 'escalated' | 'failed' | 'abandoned'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Action modal
  const [selectedCase, setSelectedCase] = useState<CaseItem | null>(null);
  const [actionNotes, setActionNotes] = useState('');
  const [resolving, setResolving] = useState(false);
  const [actionResult, setActionResult] = useState<{ status: string; link_url?: string } | null>(null);
  const [resolveError, setResolveError] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
  }, [user, apiFetch]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [payRes, escRes] = await Promise.allSettled([
        apiFetch('/payments'),
        apiFetch('/recovery/escalations'),
      ]);

      if (payRes.status === 'fulfilled' && payRes.value.ok) {
        const allPayments = await payRes.value.json();
        setCases(allPayments);
      } else {
        setCases([]);
      }
      if (escRes.status === 'fulfilled' && escRes.value.ok) {
        const escData = await escRes.value.json();
        setEscalations(escData);
      } else {
        setEscalations([]);
      }
    } catch (err) {
      console.error('Failed to fetch recovery cases:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleResolveAction = async (actionType: 'DISPATCH_LINK' | 'RETRY' | 'DISMISS') => {
    if (!selectedCase) return;
    setResolving(true);
    setActionResult(null);
    setResolveError(null);
    try {
      const res = await apiFetch('/recovery/resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          payment_id: selectedCase.payment_id,
          action_type: actionType,
          notes: actionNotes || 'Resolved manually from case dashboard',
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setActionResult(data);
        // Refresh cases list
        fetchData();
      } else {
        const errText = await res.text().catch(() => `HTTP ${res.status}`);
        setResolveError(`Server error ${res.status}: ${errText.slice(0, 120)}`);
      }
    } catch (err: any) {
      setResolveError(err?.message || 'Network error — check that the backend is running.');
    } finally {
      setResolving(false);
    }
  };

  const filteredCases = cases.filter((c) => {
    if (filterTab === 'escalated') {
      return c.amount > 10000 || c.previous_attempts >= 2 || c.status === 'DISMISSED';
    }
    if (filterTab === 'failed') {
      return c.status === 'FAILED';
    }
    if (filterTab === 'abandoned') {
      return c.failure_reason === 'CHECKOUT_ABANDONED' || c.event_type === 'CHECKOUT_ABANDONED';
    }
    return true;
  }).filter((c) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      c.payment_id.toLowerCase().includes(q) ||
      c.customer_id.toLowerCase().includes(q) ||
      c.failure_reason.toLowerCase().includes(q)
    );
  });

  const totalAtRisk = cases.filter(c => c.status === 'FAILED').reduce((acc, c) => acc + c.amount, 0);

  return (
    <div className="max-w-[1400px] mx-auto space-y-6 pt-2 pb-16">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 tracking-tight">Recovery & Escalation Center</h1>
          <p className="text-sm text-gray-500 mt-1 max-w-xl">
            Resolve bounded human escalations, review AI decisions, and dispatch manual recovery links.
          </p>
        </div>

        <button
          onClick={fetchData}
          className="flex items-center gap-2 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-bold px-3.5 py-2 rounded-xl transition-all shadow-sm shrink-0"
        >
          <RefreshCcw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm">
          <div className="flex items-center gap-2 mb-1">
            <ClipboardList className="h-4 w-4 text-indigo-600" />
            <span className="text-xs font-bold text-gray-500 uppercase">Active Cases</span>
          </div>
          <div className="text-2xl font-black text-gray-900">
            {cases.filter(c => c.status === 'FAILED').length}
          </div>
          <span className="text-[11px] text-gray-400">Awaiting resolution / link</span>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm">
          <div className="flex items-center gap-2 mb-1">
            <ShieldAlert className="h-4 w-4 text-amber-600" />
            <span className="text-xs font-bold text-gray-500 uppercase">Human Escalations</span>
          </div>
          <div className="text-2xl font-black text-amber-700">
            {escalations.length || cases.filter(c => c.amount > 10000).length}
          </div>
          <span className="text-[11px] text-amber-600">Blocked by Guardrail R2 / R4</span>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            <span className="text-xs font-bold text-gray-500 uppercase">Recovered</span>
          </div>
          <div className="text-2xl font-black text-emerald-700">
            {cases.filter(c => c.status === 'RECOVERED').length}
          </div>
          <span className="text-[11px] text-emerald-600">Confirmed captured</span>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm">
          <div className="flex items-center gap-2 mb-1">
            <Hourglass className="h-4 w-4 text-red-600" />
            <span className="text-xs font-bold text-gray-500 uppercase">Revenue at Risk</span>
          </div>
          <div className="text-2xl font-black text-gray-900">
            ₹{totalAtRisk.toLocaleString()}
          </div>
          <span className="text-[11px] text-red-500">Unrecovered volume</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col gap-3 bg-white p-3 rounded-2xl border border-gray-100 shadow-sm">
        {/* Filter Tabs - scroll on mobile */}
        <div className="flex gap-1.5 bg-gray-100 p-1 rounded-xl overflow-x-auto scrollbar-hide">
          <button
            onClick={() => setFilterTab('all')}
            className={`whitespace-nowrap px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              filterTab === 'all' ? 'bg-white text-indigo-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            All ({cases.length})
          </button>
          <button
            onClick={() => setFilterTab('escalated')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
              filterTab === 'escalated' ? 'bg-white text-amber-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Escalated (Human Review)
          </button>
          <button
            onClick={() => setFilterTab('failed')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
              filterTab === 'failed' ? 'bg-white text-red-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Active Failures
          </button>
          <button
            onClick={() => setFilterTab('abandoned')}
            className={`whitespace-nowrap px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              filterTab === 'abandoned' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Cart Drop-Offs
          </button>
        </div>

        <div className="relative w-full">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
          <input
            type="text"
            placeholder="Search payment ID, customer..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-gray-50/70 border border-gray-200 rounded-xl pl-9 pr-3.5 py-2 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition-all"
          />
        </div>
      </div>

      {/* Cases: Table (desktop) / Card list (mobile) */}
      
      {/* Mobile card view */}
      <div className="flex flex-col gap-3 md:hidden">
        {filteredCases.length === 0 ? (
          <div className="bg-white rounded-2xl border border-gray-100 p-8 text-center text-gray-500 text-sm">
            No recovery cases found. Failed payments and high-risk cases will automatically appear here.
          </div>
        ) : filteredCases.slice(0, 50).map((c) => {
          const isHighVal = c.amount > 10000;
          const isRecovered = c.status === 'RECOVERED';
          return (
            <div key={c.payment_id} className="bg-white rounded-2xl border border-gray-100 p-4 shadow-sm space-y-3">
              <div className="flex justify-between items-start gap-2">
                <div className="min-w-0">
                  <div className="font-mono font-bold text-gray-900 text-xs truncate">{c.payment_id}</div>
                  <div className="text-[11px] text-gray-400 mt-0.5 truncate">{c.customer_id}</div>
                </div>
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold shrink-0 ${
                  isRecovered ? 'bg-emerald-50 text-emerald-700' : isHighVal ? 'bg-amber-50 text-amber-700' : 'bg-red-50 text-red-700'
                }`}>
                  {isRecovered ? 'RECOVERED' : isHighVal ? 'ESCALATED' : c.status}
                </span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Amount</span>
                <span className="font-black text-gray-900">₹{c.amount.toLocaleString()}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Failure</span>
                <span className="font-medium text-gray-700 text-right max-w-[55%] truncate">{c.failure_reason.replace(/_/g, ' ')}</span>
              </div>
              {isHighVal && (
                <div className="text-[10px] text-amber-600 font-bold">⚠️ Amount &gt; ₹10k — human review required</div>
              )}
              <button
                onClick={() => { setSelectedCase(c); setActionResult(null); setActionNotes(''); }}
                className="w-full bg-indigo-50 hover:bg-indigo-600 hover:text-white text-indigo-600 font-bold text-xs py-2.5 rounded-xl transition-all shadow-sm"
              >
                Resolve Case
              </button>
            </div>
          );
        })}
      </div>

      {/* Desktop table view */}
      <div className="hidden md:block bg-white rounded-3xl border border-gray-100 shadow-sm overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50/40 text-[11px] font-bold text-gray-500 uppercase tracking-wider">
              <th className="py-3.5 px-6">Payment / Customer</th>
              <th className="py-3.5 px-4">Amount</th>
              <th className="py-3.5 px-4">Failure Reason</th>
              <th className="py-3.5 px-4">Method</th>
              <th className="py-3.5 px-4">Status</th>
              <th className="py-3.5 px-6 text-right">Human Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50 text-xs">
            {filteredCases.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-12 px-6 text-center text-gray-500 text-sm">
                  No recovery cases found. Failed payments and high-risk cases will automatically be listed here for automated recovery and agent review.
                </td>
              </tr>
            ) : (
              filteredCases.slice(0, 50).map((c) => {
                const isHighVal = c.amount > 10000;
                const isRecovered = c.status === 'RECOVERED';
                return (
                  <tr key={c.payment_id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="py-3.5 px-6">
                      <div className="font-mono font-bold text-gray-900">{c.payment_id}</div>
                      <div className="text-[11px] text-gray-400 mt-0.5">{c.customer_id}</div>
                    </td>
                    <td className="py-3.5 px-4 font-bold text-gray-900">
                      ₹{c.amount.toLocaleString()}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="font-medium text-gray-700">{c.failure_reason.replace(/_/g, ' ')}</span>
                      {isHighVal && (
                        <span className="block text-[10px] text-amber-600 font-bold mt-0.5">⚠️ Amount &gt; ₹10k</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 font-medium text-gray-500">
                      {c.payment_method}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold ${
                        isRecovered ? 'bg-emerald-50 text-emerald-700' : isHighVal ? 'bg-amber-50 text-amber-700' : 'bg-red-50 text-red-700'
                      }`}>
                        {isRecovered ? 'RECOVERED' : isHighVal ? 'ESCALATED' : c.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-6 text-right">
                      <button
                        onClick={() => {
                          setSelectedCase(c);
                          setActionResult(null);
                          setActionNotes('');
                        }}
                        className="bg-indigo-50 hover:bg-indigo-600 hover:text-white text-indigo-600 font-bold text-xs px-3 py-1.5 rounded-xl transition-all shadow-sm"
                      >
                        Resolve Case
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* RESOLUTION MODAL */}
      {selectedCase && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-5 animate-scaleUp">
            <div className="flex justify-between items-start">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-md">
                  Human Resolution Queue
                </span>
                <h3 className="text-lg font-bold text-gray-900 mt-1">
                  Resolve Payment {selectedCase.payment_id}
                </h3>
              </div>
              <button
                onClick={() => {
                  setSelectedCase(null);
                  setResolveError(null);
                  setActionResult(null);
                }}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-full hover:bg-gray-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-4 bg-gray-50 rounded-2xl space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-500">Customer ID:</span>
                <span className="font-bold text-gray-800">{selectedCase.customer_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Amount at Risk:</span>
                <span className="font-black text-gray-900">₹{selectedCase.amount.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Failure Mode:</span>
                <span className="font-bold text-red-600">{selectedCase.failure_reason}</span>
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">
                Merchant Notes / Resolution Reason
              </label>
              <textarea
                rows={2}
                value={actionNotes}
                onChange={(e) => setActionNotes(e.target.value)}
                placeholder="e.g., Customer verified account balance, approved manual WhatsApp link dispatch."
                className="w-full bg-gray-50 border border-gray-200 rounded-xl p-3 text-xs text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
              />
            </div>

            {actionResult && (
              <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 font-semibold flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-emerald-600" />
                  <span>Action executed and logged to audit trail!</span>
                </div>
                {actionResult.link_url && (
                  <a
                    href={actionResult.link_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-indigo-600 underline font-bold flex items-center gap-1"
                  >
                    Open Link <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
            )}

            {resolveError && (
              <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 font-semibold flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                <span>{resolveError}</span>
              </div>
            )}


            <div className="grid grid-cols-3 gap-2.5 pt-2">
              <button
                type="button"
                disabled={resolving}
                onClick={() => handleResolveAction('DISPATCH_LINK')}
                className="flex items-center justify-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs py-2.5 px-3 rounded-xl transition-all shadow-md shadow-indigo-100 disabled:opacity-50"
              >
                <Send className="h-3.5 w-3.5" /> Dispatch Link
              </button>

              <button
                type="button"
                disabled={resolving}
                onClick={() => handleResolveAction('RETRY')}
                className="flex items-center justify-center gap-1.5 bg-gray-800 hover:bg-black text-white font-bold text-xs py-2.5 px-3 rounded-xl transition-all disabled:opacity-50"
              >
                <RefreshCcw className="h-3.5 w-3.5" /> Gateway Retry
              </button>

              <button
                type="button"
                disabled={resolving}
                onClick={() => handleResolveAction('DISMISS')}
                className="flex items-center justify-center gap-1.5 bg-red-50 hover:bg-red-100 text-red-700 font-bold text-xs py-2.5 px-3 rounded-xl transition-all disabled:opacity-50"
              >
                <X className="h-3.5 w-3.5" /> Dismiss Case
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

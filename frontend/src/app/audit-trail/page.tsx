'use client';

import React, { useEffect, useState } from 'react';
import {
  Search,
  Filter,
  MoreHorizontal,
  Activity,
  Zap,
  ShieldOff,
  ChevronDown,
  Loader2,
} from 'lucide-react';
import { useAuth } from '@/lib/auth-context';

export default function AuditTrail() {
  const { user, apiFetch } = useAuth();
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadAudit = async () => {
      setLoading(true);
      try {
        const res = await apiFetch('/audit');
        if (res.ok) {
          const data = await res.json();
          setAuditLogs(Array.isArray(data) ? data : []);
        } else {
          setAuditLogs([]);
        }
      } catch (err) {
        console.error("Failed to fetch audit logs", err);
        setAuditLogs([]);
      } finally {
        setLoading(false);
      }
    };
    loadAudit();
  }, [user, apiFetch]);

  const totalEvents = auditLogs.length;

  return (
    <div className="max-w-[1400px] mx-auto space-y-6 pt-2">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-2">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 tracking-tight">System Audit Trail</h1>
          <p className="text-sm text-gray-500 mt-1">Immutable record of all ML scoring, AI decisions, and system actions for this workspace.</p>
        </div>
      </div>

      {/* Top KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <div className="h-8 w-8 bg-indigo-50 text-indigo-600 rounded-full flex items-center justify-center">
              <Activity className="h-4 w-4" />
            </div>
            <span className="text-[13px] font-semibold text-gray-500 uppercase tracking-wider">Total Events Recorded</span>
          </div>
          <div className="text-3xl font-extrabold text-gray-900">
            {loading ? <Loader2 className="h-7 w-7 animate-spin text-indigo-400" /> : totalEvents.toLocaleString()}
          </div>
          <div className="text-sm font-semibold text-indigo-600 mt-1">Workspace Lifetime</div>
        </div>
        
        <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <div className="h-8 w-8 bg-amber-50 text-amber-600 rounded-full flex items-center justify-center">
              <Zap className="h-4 w-4" />
            </div>
            <span className="text-[13px] font-semibold text-gray-500 uppercase tracking-wider">Automated Actions</span>
          </div>
          <div className="text-3xl font-extrabold text-gray-900">
            {loading ? <Loader2 className="h-7 w-7 animate-spin text-amber-400" /> : auditLogs.filter((a: any) => a.action_taken !== 'escalate_to_human').length.toLocaleString()}
          </div>
          <div className="text-sm font-semibold text-amber-600 mt-1">Handled completely by AI</div>
        </div>

        <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <div className="h-8 w-8 bg-emerald-50 text-emerald-600 rounded-full flex items-center justify-center">
              <ShieldOff className="h-4 w-4" />
            </div>
            <span className="text-[13px] font-semibold text-gray-500 uppercase tracking-wider">Guardrail Interventions</span>
          </div>
          <div className="text-3xl font-extrabold text-gray-900">
            {loading ? <Loader2 className="h-7 w-7 animate-spin text-emerald-400" /> : auditLogs.filter((a: any) => a.guardrail_result !== 'passed').length.toLocaleString()}
          </div>
          <div className="text-sm font-semibold text-emerald-600 mt-1">Actions bounded for safety</div>
        </div>
      </div>

      {/* Main Table Area */}
      <div className="bg-white rounded-[24px] border border-gray-100 shadow-sm overflow-hidden">
        {/* Filters Bar */}
        <div className="p-4 flex flex-wrap gap-4 items-center justify-between border-b border-gray-100 bg-gray-50/50">
          <div className="flex items-center gap-3 flex-1 min-w-[200px]">
            <div className="relative w-full max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input 
                type="text" 
                placeholder="Search event ID, payment ID..." 
                className="w-full pl-9 pr-4 py-2 bg-white border border-gray-200 rounded-xl text-sm outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all font-medium"
              />
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 px-3 py-2 border border-gray-200 rounded-lg text-sm font-semibold text-gray-700 hover:bg-gray-50">
              <Filter className="h-4 w-4" /> Filters
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-gray-100 bg-white">
                <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider">Event & Time</th>
                <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider">Payment ID</th>
                <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider">AI Diagnosis</th>
                <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider text-center">ML Score</th>
                <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider">AI Recommendation</th>
                <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider text-center">Guardrail</th>
                <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider text-center">Final Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-400 text-sm">
                    <Loader2 className="h-6 w-6 animate-spin mx-auto text-indigo-500 mb-2" />
                    Loading audit trail...
                  </td>
                </tr>
              ) : auditLogs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-500 text-sm">
                    No audit records in this workspace yet. When the AI agent evaluates failed payments, verified decision logs will appear here.
                  </td>
                </tr>
              ) : (
                auditLogs.slice(0, 50).map((log: any) => {
                  const displayDate = new Date(log.timestamp).toLocaleString('en-IN', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric'
                  });
                  const displayTime = new Date(log.timestamp).toLocaleString('en-IN', {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                  });

                  return (
                    <TableRow 
                      key={log.event_id}
                      eventId={log.event_id ? log.event_id.slice(0, 10) : 'evt'}
                      date={displayDate}
                      time={displayTime}
                      paymentId={log.payment_id ? log.payment_id.slice(0, 10) : 'pay'}
                      diagnosis={log.ai_diagnosis}
                      mlScore={log.ml_score}
                      recommendation={log.ai_recommendation}
                      guardrailStatus={log.guardrail_result === 'passed' || log.guardrail_result === 'APPROVED' ? 'Passed' : 'Blocked'}
                      finalAction={log.action_taken ? log.action_taken.replace(/_/g, ' ') : 'N/A'}
                    />
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="p-4 border-t border-gray-100 flex items-center justify-between bg-white">
          <div className="text-sm font-semibold text-gray-500">
            Showing 1 to {Math.min(50, totalEvents)} of {totalEvents.toLocaleString()} events
          </div>
          <div className="flex items-center gap-2">
            <button className="h-8 w-8 rounded-lg border border-gray-200 flex items-center justify-center text-gray-500 hover:bg-gray-50 disabled:opacity-50" disabled>
              &lt;
            </button>
            <button className="h-8 w-8 rounded-lg bg-[#10B981] text-white font-semibold flex items-center justify-center shadow-sm shadow-emerald-200">
              1
            </button>
            <button className="h-8 w-8 rounded-lg border border-gray-200 flex items-center justify-center text-gray-700 font-semibold hover:bg-gray-50">
              2
            </button>
            <span className="px-2 text-gray-400">...</span>
            <button className="h-8 w-8 rounded-lg border border-gray-200 flex items-center justify-center text-gray-500 hover:bg-gray-50">
              &gt;
            </button>
            
            <div className="ml-4 flex items-center gap-2 border border-gray-200 px-3 py-1.5 rounded-lg text-sm font-semibold text-gray-700 cursor-pointer hover:bg-gray-50">
              50 / page
              <ChevronDown className="h-4 w-4 text-gray-400" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function TableRow({ eventId, date, time, paymentId, diagnosis, mlScore, recommendation, guardrailStatus, finalAction }: any) {
  const guardrailColors: any = {
    'Passed': 'bg-emerald-50 text-emerald-700 border-emerald-100',
    'Blocked': 'bg-red-50 text-red-700 border-red-100',
    'Warning': 'bg-amber-50 text-amber-700 border-amber-100',
  };

  const actionColors: any = {
    'send email': 'bg-blue-50 text-blue-700 border-blue-100',
    'send sms': 'bg-indigo-50 text-indigo-700 border-indigo-100',
    'escalate to human': 'bg-orange-50 text-orange-700 border-orange-100',
    'retry gateway': 'bg-emerald-50 text-emerald-700 border-emerald-100',
    'wait and retry': 'bg-amber-50 text-amber-700 border-amber-100'
  };
  
  const scorePct = Math.round((mlScore || 0) * 100);
  const scoreColor = scorePct > 70 ? 'text-emerald-600' : scorePct > 40 ? 'text-amber-600' : 'text-red-600';

  return (
    <tr className="hover:bg-gray-50/50 transition-colors group">
      <td className="px-6 py-4">
        <div className="font-mono text-[12px] font-bold text-gray-900 mb-0.5 uppercase">{eventId}</div>
        <div className="text-[11px] font-semibold text-gray-400">{date} • {time}</div>
      </td>
      <td className="px-6 py-4">
        <div className="font-mono text-[12px] font-semibold text-indigo-600 bg-indigo-50 border border-indigo-100 px-2 py-0.5 rounded inline-flex">{paymentId}</div>
      </td>
      <td className="px-6 py-4">
        <span className="text-[13px] font-medium text-gray-700">{diagnosis}</span>
      </td>
      <td className="px-6 py-4 text-center">
        <span className={`font-bold text-[14px] ${scoreColor}`}>{scorePct}%</span>
      </td>
      <td className="px-6 py-4">
        <span className="text-[13px] font-medium text-gray-700">{recommendation}</span>
      </td>
      <td className="px-6 py-4 text-center">
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${guardrailColors[guardrailStatus] || 'bg-gray-50 text-gray-600'}`}>
          {guardrailStatus}
        </span>
      </td>
      <td className="px-6 py-4 text-center">
        <span className={`inline-flex items-center px-2 py-1 rounded text-[11px] font-bold uppercase tracking-wider border ${actionColors[finalAction.toLowerCase()] || 'bg-gray-50 text-gray-700 border-gray-200'}`}>
          {finalAction}
        </span>
      </td>
    </tr>
  );
}

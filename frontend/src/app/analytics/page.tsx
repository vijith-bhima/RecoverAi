'use client';

import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  Download,
  Calendar,
  ChevronDown,
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  Target,
  Zap,
  RefreshCw,
  Sparkles
} from 'lucide-react';
import { useAuth } from '@/lib/auth-context';

export default function Analytics() {
  const { user, apiFetch } = useAuth();
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = async (refresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const url = refresh ? '/metrics?refresh=true' : '/metrics';
      const res = await apiFetch(url);
      if (res.ok) {
        setMetrics(await res.json());
      } else if (res.status === 404) {
        setMetrics(null);
      } else {
        setError(`Server error ${res.status} — try clicking Refresh`);
      }
    } catch (err: any) {
      setError('Cannot reach backend. Make sure uvicorn is running on port 8000.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, [user, apiFetch]);

  const m = metrics || {
    revenue_recovered: 0,
    recovery_rate_pct: 0,
    successful_recoveries: 0,
    transactions_tested: 0,
    recoverable_count: 0,
    human_escalations: 0,
    strategy_counts: {},
    daily_trend: []
  };

  const recoveredDisplay = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0
  }).format(m.revenue_recovered);

  return (
    <div className="max-w-[1400px] mx-auto space-y-6 pt-2">

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 tracking-tight">Analytics Overview</h1>
          <p className="text-sm text-gray-500 mt-1">Deep dive into your recovery performance and system metrics.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <div className="flex items-center gap-2 bg-white border border-gray-200 px-3 py-2 rounded-xl text-xs sm:text-sm font-semibold text-gray-700 hover:border-gray-300 cursor-pointer transition-colors shadow-sm">
            <Calendar className="h-4 w-4 text-gray-400" />
            <span>Last 30 Days</span>
            <ChevronDown className="h-4 w-4 text-gray-400" />
          </div>
          <button
            onClick={() => fetchMetrics(true)}
            className="flex items-center gap-2 bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-colors shadow-sm"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={async () => {
              const token = typeof window !== 'undefined' ? localStorage.getItem('recoverai_auth_token') : null;
              const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
              const res = await fetch(`${apiBase}/reports/export/csv`, {
                headers: token ? { Authorization: `Bearer ${token}` } : {}
              });
              if (res.ok) {
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'recoverai_revenue_report.csv';
                a.click();
                URL.revokeObjectURL(url);
              }
            }}
            className="flex items-center gap-2 bg-[#10B981] hover:bg-[#059669] text-white px-3 sm:px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-colors shadow-sm shadow-emerald-200"
          >
            <Download className="h-4 w-4" />
            Export
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
          <strong>Failed to load analytics:</strong> {error}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <KpiCard
          title="Total Recovered"
          value={loading ? null : recoveredDisplay}
          trend="All Time"
          isPositive={true}
          icon={TrendingUp}
          color="emerald"
        />
        <KpiCard
          title="Transactions Tested"
          value={loading ? null : m.transactions_tested.toLocaleString()}
          trend="All Time"
          isPositive={true}
          icon={Activity}
          color="blue"
        />
        <KpiCard
          title="Success Rate"
          value={loading ? null : `${m.recovery_rate_pct}%`}
          trend="Live"
          isPositive={true}
          icon={Target}
          color="indigo"
        />
        <KpiCard
          title="Human Escalations"
          value={loading ? null : m.human_escalations.toLocaleString()}
          trend="Guardrail Protected"
          isPositive={false}
          icon={Activity}
          color="red"
        />
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Main Chart Area */}
        <div className="col-span-2 bg-white rounded-[24px] border border-gray-100 shadow-sm p-6">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h3 className="font-bold text-gray-900 text-lg">Recovery Volume Trend</h3>
              <p className="text-xs text-gray-500 mt-1">Daily recovered amount vs failed amount</p>
            </div>
            <div className="flex items-center gap-4 text-sm font-medium">
              <div className="flex items-center gap-2">
                <div className="h-2.5 w-2.5 rounded-full bg-emerald-500"></div>
                <span className="text-gray-600">Recovered</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-2.5 w-2.5 rounded-full bg-red-400 opacity-50"></div>
                <span className="text-gray-600">Failed</span>
              </div>
            </div>
          </div>

          {/* Chart */}
          <div className="h-[280px] w-full relative mt-4">
            {loading ? (
              <div className="absolute inset-0 flex flex-col gap-3 justify-end pb-6">
                <div className="h-full w-full bg-gray-100 rounded-xl animate-pulse" />
              </div>
            ) : (() => {
              const trend = m.daily_trend || [];
              const maxVal = Math.max(...trend.map((d: any) => Math.max(d.recovered, d.failed)), 200000);
              const formatAxis = (val: number) => `₹${Math.round(val / 1000)}K`;
              const makePath = (key: 'recovered' | 'failed') => {
                if (trend.length === 0) return '';
                return trend.map((d: any, i: number) => {
                  const x = (i / Math.max(1, trend.length - 1)) * 100;
                  const y = 90 - ((d[key] / maxVal) * 80);
                  return `${i === 0 ? 'M' : 'L'}${x},${y}`;
                }).join(' ');
              };
              const recoveredPath = makePath('recovered');
              const failedPath = makePath('failed');
              const areaPath = recoveredPath ? `${recoveredPath} L100,100 L0,100 Z` : '';

              return (
                <>
                  <div className="absolute left-0 top-0 bottom-6 w-12 flex flex-col justify-between text-xs text-gray-400 font-medium">
                    <span>{formatAxis(maxVal)}</span>
                    <span>{formatAxis(maxVal * 0.75)}</span>
                    <span>{formatAxis(maxVal * 0.5)}</span>
                    <span>{formatAxis(maxVal * 0.25)}</span>
                    <span>₹0</span>
                  </div>
                  <div className="absolute left-14 right-0 top-0 bottom-6">
                    <div className="absolute left-0 right-0 top-[10%] h-[1px] bg-gray-100"></div>
                    <div className="absolute left-0 right-0 top-[30%] h-[1px] bg-gray-100"></div>
                    <div className="absolute left-0 right-0 top-[50%] h-[1px] bg-gray-100"></div>
                    <div className="absolute left-0 right-0 top-[70%] h-[1px] bg-gray-100"></div>
                    <div className="absolute left-0 right-0 bottom-[10%] h-[1px] bg-gray-100"></div>
                    <svg className="absolute inset-0 w-full h-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 100 100">
                      <defs>
                        <linearGradient id="recoveredGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#10B981" stopOpacity="0.4" />
                          <stop offset="100%" stopColor="#10B981" stopOpacity="0.0" />
                        </linearGradient>
                      </defs>
                      {failedPath && <path d={failedPath} fill="none" stroke="#F87171" strokeWidth="2" opacity="0.5" strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />}
                      {areaPath && <path d={areaPath} fill="url(#recoveredGradient)" />}
                      {recoveredPath && <path d={recoveredPath} fill="none" stroke="#10B981" strokeWidth="3" vectorEffect="non-scaling-stroke" />}
                    </svg>
                  </div>
                  <div className="absolute left-14 right-0 bottom-0 flex justify-between text-xs text-gray-400 font-medium">
                    {trend.length > 0 ? (
                      <>
                        <span>{trend[0]?.date}</span>
                        <span>{trend[Math.floor(trend.length * 0.25)]?.date}</span>
                        <span>{trend[Math.floor(trend.length * 0.5)]?.date}</span>
                        <span>{trend[Math.floor(trend.length * 0.75)]?.date}</span>
                        <span>{trend[trend.length - 1]?.date}</span>
                      </>
                    ) : (
                      <span className="text-gray-300">No data</span>
                    )}
                  </div>
                </>
              );
            })()}
          </div>
        </div>

        {/* Side Panel */}
        <div className="space-y-6">
          {/* Top Recovery Strategies */}
          <div className="bg-white rounded-[24px] border border-gray-100 shadow-sm p-6">
            <h3 className="font-bold text-gray-900 text-sm mb-5">Top Recovery Strategies</h3>
            <div className="space-y-5">
              {loading ? (
                [1, 2, 3, 4].map(i => (
                  <div key={i} className="space-y-2">
                    <div className="h-4 bg-gray-100 rounded animate-pulse w-3/4"></div>
                    <div className="h-2 bg-gray-100 rounded-full animate-pulse"></div>
                  </div>
                ))
              ) : (
                <>
                  <StrategyRow name="Smart Retry (AI)" count={m.strategy_counts?.RETRY || 0} pct={m.successful_recoveries ? `${Math.round(((m.strategy_counts?.RETRY || 0) / m.successful_recoveries) * 100)}%` : '0%'} color="bg-indigo-500" />
                  <StrategyRow name="WhatsApp Link" count={m.strategy_counts?.SEND_PAYMENT_LINK || 0} pct={m.successful_recoveries ? `${Math.round(((m.strategy_counts?.SEND_PAYMENT_LINK || 0) / m.successful_recoveries) * 100)}%` : '0%'} color="bg-emerald-500" />
                  <StrategyRow name="Wait & Evaluate" count={m.strategy_counts?.WAIT || 0} pct={m.transactions_tested ? `${Math.round(((m.strategy_counts?.WAIT || 0) / m.transactions_tested) * 100)}%` : '0%'} color="bg-blue-500" />
                  <StrategyRow name="Agent Call" count={m.strategy_counts?.ESCALATE_TO_HUMAN || 0} pct={m.transactions_tested ? `${Math.round(((m.strategy_counts?.ESCALATE_TO_HUMAN || 0) / m.transactions_tested) * 100)}%` : '0%'} color="bg-orange-500" />
                </>
              )}
            </div>
          </div>

          {/* AI Insights */}
          <div className="bg-indigo-600 rounded-[24px] shadow-sm p-6 text-white relative overflow-hidden">
            <div className="absolute -right-6 -top-6 h-24 w-24 bg-indigo-500 rounded-full blur-2xl opacity-50"></div>
            <div className="flex items-center gap-2 mb-4">
              <Zap className="h-5 w-5 text-indigo-200" />
              <h3 className="font-bold text-lg tracking-tight">AI Insights</h3>
            </div>
            <p className="text-indigo-100 text-sm leading-relaxed mb-4 font-medium">
              Sending reminders between <strong className="text-white">6:00 PM - 8:00 PM</strong> increases recovery probability by <strong className="text-emerald-300">18.4%</strong> for &quot;Insufficient Funds&quot; errors.
            </p>
            <a
              href="/settings"
              className="block bg-white text-indigo-700 text-xs font-bold px-4 py-2 rounded-xl w-full hover:bg-indigo-50 transition-colors shadow-sm text-center"
            >
              Configure Guardrails & Channels →
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

// Subcomponents

function KpiCard({ title, value, trend, isPositive, icon: Icon, color }: any) {
  const colorMap: any = {
    emerald: 'bg-emerald-50 text-emerald-600',
    blue: 'bg-blue-50 text-blue-600',
    indigo: 'bg-indigo-50 text-indigo-600',
    red: 'bg-red-50 text-red-600'
  };

  return (
    <div className="bg-white p-6 rounded-[24px] border border-gray-100 shadow-sm relative group overflow-hidden hover:border-gray-200 transition-all">
      <div className="flex justify-between items-start mb-4">
        <div className={`h-10 w-10 rounded-xl flex items-center justify-center ${colorMap[color]} shrink-0`}>
          <Icon className="h-5 w-5" />
        </div>
        <div className={`flex items-center gap-1 text-xs font-bold px-2 py-1 rounded-full ${isPositive ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-600'}`}>
          {isPositive ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
          {trend}
        </div>
      </div>
      <div>
        {value === null ? (
          <div className="h-9 w-32 bg-gray-100 rounded-lg animate-pulse mb-2"></div>
        ) : (
          <div className="text-3xl font-extrabold text-gray-900 tracking-tight mb-1">{value}</div>
        )}
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{title}</div>
      </div>
    </div>
  );
}

function StrategyRow({ name, count, pct, color }: any) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-xs font-bold">
        <span className="text-gray-700">{name}</span>
        <span className="text-gray-900">{count} <span className="text-gray-400 font-medium ml-1">({pct})</span></span>
      </div>
      <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: pct }}></div>
      </div>
    </div>
  );
}

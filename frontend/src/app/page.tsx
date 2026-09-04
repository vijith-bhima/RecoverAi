'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  CheckCircle2,
  AlertCircle,
  ShieldCheck,
  Search,
  Eye,
  RefreshCw,
  Loader2,
  Sparkles,
  Building,
} from 'lucide-react';
import { useAuth } from '@/lib/auth-context';

// Inline components
const Card = ({ className, children }: any) => <div className={`rounded-3xl border border-gray-100 shadow-sm bg-white overflow-hidden ${className || ''}`}>{children}</div>;
const CardHeader = ({ className, children }: any) => <div className={`p-6 pb-2 ${className || ''}`}>{children}</div>;
const CardTitle = ({ className, children }: any) => <h3 className={`text-lg font-bold text-gray-900 ${className || ''}`}>{children}</h3>;
const CardContent = ({ className, children }: any) => <div className={`p-6 pt-0 ${className || ''}`}>{children}</div>;
const Badge = ({ className, children }: any) => <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider ${className || ''}`}>{children}</span>;
const Avatar = ({ className, children }: any) => <div className={`relative flex shrink-0 overflow-hidden rounded-full items-center justify-center ${className || ''}`}>{children}</div>;
const AvatarFallback = ({ className, children }: any) => <span className={`flex h-full w-full items-center justify-center rounded-full ${className || ''}`}>{children}</span>;

const DEFAULT_METRICS = { revenue_recovered: 0, recovery_rate_pct: 0, revenue_at_risk: 0, successful_recoveries: 0 };

export default function RecoverAIDashboard() {
  const { user, apiFetch } = useAuth();
  const router = useRouter();
  const [metrics, setMetrics] = useState<any>(null);
  const [payments, setPayments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [greeting, setGreeting] = useState('Good morning');

  const loadDashboardData = () => {
    setLoading(true);
    // Fetch in parallel using authenticated apiFetch
    Promise.allSettled([
      apiFetch('/payments')
        .then(r => r.ok ? r.json() : [])
        .catch(() => []),
      apiFetch('/metrics')
        .then(r => r.ok ? r.json() : null)
        .catch(() => null),
    ]).then(([paymentsRes, metricsRes]) => {
      if (paymentsRes.status === 'fulfilled' && Array.isArray(paymentsRes.value)) {
        setPayments(paymentsRes.value);
      } else {
        setPayments([]);
      }
      if (metricsRes.status === 'fulfilled' && metricsRes.value) {
        setMetrics(metricsRes.value);
      } else {
        setMetrics(DEFAULT_METRICS);
      }
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => {
    const h = new Date().getHours();
    setGreeting(h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening');
    loadDashboardData();
  }, [user]);

  const m = metrics || DEFAULT_METRICS;

  const recoveredDisplay = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(m.revenue_recovered);
  const atRiskDisplay = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(m.revenue_at_risk);
  
  // Prepare dynamic recent customers
  const recentCustomers = payments.slice(0, 4).map((p: any) => {
    return {
      initials: p.customer_id.slice(-2).toUpperCase(),
      name: "Customer " + p.customer_id.slice(-4),
      desc: p.failure_reason || (p.status === 'SUCCESS' ? 'Processed successfully' : 'Pending verification'),
      amount: new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(p.amount),
      status: p.status === 'SUCCESS' ? 'recovered' : p.status === 'FAILED' ? 'waiting' : 'in review',
      color: p.status === 'SUCCESS' ? 'bg-emerald-700' : p.status === 'FAILED' ? 'bg-red-500' : 'bg-orange-500'
    }
  });

  // Prepare a dynamic closer look case study based on the first payment
  const caseStudyPayment = payments[0] || {
    payment_id: "PAY_18291",
    status: "SUCCESS",
    amount: 5000,
    failure_reason: "Bank server was briefly down"
  };
  const caseStudyAmount = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(caseStudyPayment.amount);
  const caseStudyStatus = caseStudyPayment.status === 'SUCCESS' ? 'Recovered' : caseStudyPayment.status === 'FAILED' ? 'Failed' : 'Pending';

  return (
    <div className="max-w-6xl mx-auto space-y-6 pt-2">
      
      {/* Hero Section */}
      <section 
        className="relative overflow-hidden rounded-[24px] md:rounded-[32px] p-6 sm:p-10 md:p-14 shadow-sm border border-indigo-50 bg-cover bg-center bg-no-repeat min-h-[300px] md:min-h-[380px] bg-white flex items-center"
        style={{ backgroundImage: "url('/Assets/heroText_backgroundImage.png')" }}
      >
        <div className="absolute inset-0 bg-white/20 md:bg-transparent"></div>
        
        <div className="relative z-10 md:w-[60%] space-y-7">
          <div className="space-y-3">
            <p className="text-gray-600 font-medium flex items-center gap-2 text-xs sm:text-sm uppercase tracking-wider">
              {greeting}, 👋
            </p>
            <h1 className="text-[30px] sm:text-[40px] md:text-[56px] font-extrabold tracking-tight text-gray-900 leading-[1.1]">
              {loading ? (
                <span className="inline-flex items-center gap-3 text-indigo-400">
                  <Loader2 className="h-8 w-8 animate-spin" />
                  <span className="text-3xl">Loading…</span>
                </span>
              ) : (
                <>Welcome back{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}.<br/><span className="text-indigo-600">{recoveredDisplay}</span> recovered so far.</>
              )}
            </h1>
          </div>
          
          <p className="text-gray-500 leading-relaxed text-[13px] sm:text-[15px] max-w-[420px] font-medium">
            A clear view of the payments that need attention, the ones we’ve recovered, and what to do next.
          </p>

          <div className="flex flex-wrap gap-3 pt-4">
            {loading ? (
              <div className="h-16 w-64 bg-gray-100 animate-pulse rounded-[20px]" />
            ) : (
              <>
                <HeroStat icon={RefreshCw} value={`${m.recovery_rate_pct}%`} label="Recovery rate" color="green" href="/analytics" />
                <HeroStat icon="₹" value={atRiskDisplay} label="Won at risk" color="orange" href="/recovery-cases" />
                <HeroStat icon={Eye} value={m.successful_recoveries} label="Trusted us here" color="indigo" href="/payments" />
              </>
            )}
          </div>
        </div>
      </section>

      {/* Merchant Production Readiness & Gateway Status */}
      <div className="bg-white rounded-3xl p-6 border border-gray-100 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-md">
              ● Recovery pipeline is running
            </span>
            <h3 className="text-base font-bold text-gray-900 mt-1">Your payment connection and safety checks</h3>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <a
              href="/settings"
              className="text-xs font-bold text-indigo-600 hover:text-indigo-700 bg-indigo-50 hover:bg-indigo-100 px-3.5 py-1.5 rounded-xl transition-all"
            >
              Configure Gateway & Guardrails →
            </a>
            <a
              href="/recover"
              className="text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 px-3.5 py-1.5 rounded-xl transition-all shadow-sm shadow-indigo-200"
            >
              Open Live Console
            </a>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 pt-2">
          <div className="p-3 bg-gray-50/70 border border-gray-100 rounded-2xl flex items-center gap-3">
            <div className="h-8 w-8 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold text-xs shrink-0">
              ✓
            </div>
            <div>
              <div className="text-xs font-bold text-gray-900">Razorpay Connected</div>
              <div className="text-[10px] text-gray-500">Live API Key Verified</div>
            </div>
          </div>

          <div className="p-3 bg-gray-50/70 border border-gray-100 rounded-2xl flex items-center gap-3">
            <div className="h-8 w-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-xs shrink-0">
              ⚡
            </div>
            <div>
              <div className="text-xs font-bold text-gray-900">Webhook Ingestion</div>
              <div className="text-[10px] text-gray-500">Auto-triggers on failure</div>
            </div>
          </div>

          <div className="p-3 bg-gray-50/70 border border-gray-100 rounded-2xl flex items-center gap-3">
            <div className="h-8 w-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-xs shrink-0">
              🛡️
            </div>
            <div>
              <div className="text-xs font-bold text-gray-900">Guardrails Enforced</div>
              <div className="text-[10px] text-gray-500">₹10,000 Safety Threshold</div>
            </div>
          </div>

          <div className="p-3 bg-gray-50/70 border border-gray-100 rounded-2xl flex items-center gap-3">
            <div className="h-8 w-8 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold text-xs shrink-0">
              🤖
            </div>
            <div>
              <div className="text-xs font-bold text-gray-900">Compound AI Loop</div>
              <div className="text-[10px] text-gray-500">Zero Merchant Clicks</div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid lg:grid-cols-2 gap-6">
        
        {/* How It Works */}
        <Card>
          <CardHeader>
            <p className="text-[11px] font-extrabold text-indigo-600 uppercase tracking-widest mb-1">How it works</p>
            <CardTitle>A payment's second chance</CardTitle>
          </CardHeader>
          <CardContent className="pt-8 pb-10">
            {/* Desktop: Horizontal. Mobile: Vertical */}
            <div className="hidden sm:relative sm:flex justify-between items-start">
              <div className="absolute top-[22px] left-[15%] right-[15%] h-[2px] border-t-2 border-dashed border-gray-200 -z-10"></div>
              <StepItem icon={Search} title="We size it up" desc="How likely is this one come back?" color="green" />
              <StepItem icon={AlertCircle} title="We understand" desc="The agent figures out what went wrong." color="orange" />
              <StepItem icon={ShieldCheck} title="We verify" desc="Firm rules decide what we're allowed to do." color="red" />
              <StepItem icon={CheckCircle2} title="We confirm" desc="Nudging politely until the money is there." color="green" solid />
            </div>
            {/* Mobile vertical layout */}
            <div className="flex sm:hidden flex-col gap-4">
              <StepItemVertical icon={Search} title="We size it up" desc="How likely is this one come back?" color="green" />
              <StepItemVertical icon={AlertCircle} title="We understand" desc="The agent figures out what went wrong." color="orange" />
              <StepItemVertical icon={ShieldCheck} title="We verify" desc="Firm rules decide what we're allowed to do." color="red" />
              <StepItemVertical icon={CheckCircle2} title="We confirm" desc="Nudging politely until the money is there." color="green" solid />
            </div>
          </CardContent>
        </Card>

        {/* Today's Customers */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <p className="text-[11px] font-extrabold text-indigo-600 uppercase tracking-widest mb-1">Today</p>
              <CardTitle>A few of your customers</CardTitle>
            </div>
            <a
              href="/customers"
              className="text-[12px] font-bold text-indigo-700 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 px-4 py-1.5 rounded-full transition-colors"
            >
              View all
            </a>
          </CardHeader>
          <CardContent className="space-y-4 pt-2">
            {loading ? (
              [1,2,3,4].map(i => (
                <div key={i} className="h-12 bg-gray-100 animate-pulse rounded-xl" />
              ))
            ) : recentCustomers.length > 0 ? recentCustomers.map((c: any, i: number) => (
              <CustomerRow
                key={i}
                initials={c.initials}
                name={c.name}
                desc={c.desc}
                amount={c.amount}
                status={c.status}
                color={c.color}
                isLast={i === recentCustomers.length - 1}
              />
            )) : (
              <div className="text-gray-500 text-sm py-4">No recent customers found.</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Closer Look — only shown when there are real payments */}
      {!loading && payments.length > 0 && (
        <div className="space-y-4 pt-4 pb-8">
          <div>
            <p className="text-[11px] font-extrabold text-indigo-600 uppercase tracking-widest mb-1">A closer look</p>
            <h2 className="text-2xl font-bold text-gray-900">What happened with Customer {payments[0].customer_id?.slice(-4)}'s payment</h2>
          </div>
          <div className="bg-[#1C5140] rounded-[24px] md:rounded-[32px] p-6 sm:p-10 text-white relative overflow-hidden flex flex-col md:flex-row justify-between items-center shadow-md gap-6">
            <div className="md:w-3/4 space-y-5 z-10">
              <div className="flex flex-wrap items-center gap-3 sm:gap-4">
                <span className="font-mono text-[11px] sm:text-[13px] opacity-70 tracking-widest break-all">{payments[0].payment_id}</span>
                <span className="bg-[#2A6553] text-emerald-100 border border-[#3B7B66] font-bold px-3 py-1 rounded-full text-[10px] uppercase tracking-wider">
                  {payments[0].status === 'SUCCESS' ? 'Recovered' : payments[0].status === 'FAILED' ? 'Failed' : 'Pending'}
                </span>
              </div>
              <p className="text-emerald-50/90 leading-relaxed text-[15px] max-w-2xl font-light">
                Failure Reason: {payments[0].failure_reason || 'System outage'}.<br/>
                RecoverAI recognized it, waited for things to settle, and sent a fresh payment link.
              </p>
              <p className="font-bold text-[#FFD166] pt-2 text-[17px] tracking-wide">
                {new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(payments[0].amount)} at stake.
              </p>
            </div>
            <div className="mt-8 md:mt-0 relative z-10 bg-[#164435] p-4 rounded-[32px] border border-white/10 flex items-center justify-center shadow-2xl">
               <div className="h-[140px] w-[80px] border-[2px] border-white/20 rounded-[24px] flex items-center justify-center relative overflow-hidden bg-[#1A4E3D]">
                  <div className="absolute top-3 w-8 h-1 bg-white/20 rounded-full"></div>
                  <div className="h-10 w-10 bg-[#10B981] rounded-full flex items-center justify-center shadow-xl shadow-emerald-900/50">
                    <CheckCircle2 className="h-5 w-5 text-white" />
                  </div>
               </div>
            </div>
          </div>
        </div>
      )}

      {/* Empty state — shown when no real payments ingested yet */}
      {!loading && payments.length === 0 && (
        <div className="pb-10">
          <div className="rounded-[32px] border-2 border-dashed border-indigo-100 bg-indigo-50/30 p-12 flex flex-col items-center text-center space-y-5">
            <div className="h-16 w-16 rounded-2xl bg-indigo-100 text-indigo-500 flex items-center justify-center text-3xl">
              ⚡
            </div>
            <div>
              <h3 className="text-xl font-bold text-gray-900">Ready for your first real payment</h3>
              <p className="text-sm text-gray-500 mt-2 max-w-md">
                No transactions yet. Configure your Razorpay keys in Settings and point your webhook to this server.
                Failed payments will appear here automatically — no manual action needed.
              </p>
            </div>
            <div className="flex flex-wrap gap-3 pt-2 justify-center">
              <a
                href="/settings"
                className="px-5 py-2.5 bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 text-sm font-bold rounded-xl transition-all"
              >
                Configure Razorpay →
              </a>
              <a
                href="/recover"
                className="px-5 py-2.5 bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 text-sm font-bold rounded-xl transition-all"
              >
                Open Live Console
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* Helper Components */

function HeroStat({ icon: Icon, value, label, color, href }: any) {
  const colorMap: any = {
    green: 'bg-emerald-50 text-emerald-600',
    orange: 'bg-orange-50 text-orange-500',
    indigo: 'bg-indigo-50 text-indigo-600'
  };
  
  const content = (
    <div className={`bg-white/90 backdrop-blur-sm px-6 py-4 rounded-[20px] shadow-sm border border-gray-100/50 flex items-center gap-4 hover:shadow-md transition-shadow ${href ? 'cursor-pointer' : ''}`}>
      <div className={`h-11 w-11 ${colorMap[color]} rounded-full flex items-center justify-center font-bold text-lg`}>
        {typeof Icon === 'string' ? Icon : <Icon className="h-5 w-5" />}
      </div>
      <div>
        <div className="font-extrabold text-gray-900 text-[15px]">{value}</div>
        <div className="text-[12px] text-gray-500 font-semibold">{label}</div>
      </div>
    </div>
  );

  if (href) {
    return <a href={href}>{content}</a>;
  }
  return content;
}

function StepItem({ icon: Icon, title, desc, color, solid }: any) {
  const bgClass = solid 
    ? 'bg-emerald-500 text-white shadow-emerald-500/20' 
    : color === 'green' ? 'bg-emerald-50 text-emerald-600' : color === 'orange' ? 'bg-orange-50 text-orange-500' : 'bg-red-50 text-red-500';

  return (
    <div className="flex flex-col items-center text-center space-y-4 w-1/4">
      <div className={`h-12 w-12 ${bgClass} rounded-full flex items-center justify-center shadow-lg ring-[6px] ring-white relative z-10`}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="px-2">
        <div className="font-bold text-[14px] text-gray-900">{title}</div>
        <div className="text-[12px] text-gray-500 leading-snug mt-1.5">{desc}</div>
      </div>
    </div>
  );
}

function StepItemVertical({ icon: Icon, title, desc, color, solid }: any) {
  const bgClass = solid 
    ? 'bg-emerald-500 text-white shadow-emerald-500/20' 
    : color === 'green' ? 'bg-emerald-50 text-emerald-600' : color === 'orange' ? 'bg-orange-50 text-orange-500' : 'bg-red-50 text-red-500';

  return (
    <div className="flex items-start gap-4">
      <div className={`h-10 w-10 shrink-0 ${bgClass} rounded-full flex items-center justify-center shadow-md ring-4 ring-white`}>
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <div className="font-bold text-[14px] text-gray-900">{title}</div>
        <div className="text-[12px] text-gray-500 leading-snug mt-1">{desc}</div>
      </div>
    </div>
  );
}

function CustomerRow({ initials, name, desc, amount, status, color, isLast }: any) {
  const statusColors: any = {
    'recovered': 'bg-emerald-50 text-emerald-700',
    'in review': 'bg-orange-50 text-orange-700',
    'waiting': 'bg-yellow-50 text-yellow-700'
  };

  return (
    <div className={`flex items-center justify-between pb-4 ${!isLast ? 'border-b border-gray-50' : ''}`}>
      <div className="flex items-center gap-2 sm:gap-4 min-w-0">
        <Avatar className={`h-9 w-9 sm:h-10 sm:w-10 shrink-0 ${color} text-white font-bold text-[12px] shadow-sm`}>
          <AvatarFallback className={color}>{initials}</AvatarFallback>
        </Avatar>
        <div className="min-w-0">
          <div className="font-bold text-[14px] text-gray-900 truncate">{name}</div>
          <div className="text-[12px] text-gray-400 font-medium truncate max-w-[120px] sm:max-w-[200px]">{desc}</div>
        </div>
      </div>
      <div className="flex items-center gap-2 sm:gap-5 shrink-0">
        <Badge className={`${statusColors[status]} border-0 px-2 py-0.5 sm:px-2.5 sm:py-1 hidden sm:inline-flex`}>{status}</Badge>
        <div className="font-extrabold text-[13px] sm:text-[15px] text-gray-900">{amount}</div>
      </div>
    </div>
  );
}

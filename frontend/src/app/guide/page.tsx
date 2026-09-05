'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  Activity,
  ArrowRight,
  BarChart2,
  BellRing,
  BookOpen,
  Brain,
  Briefcase,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  Code2,
  Copy,
  CreditCard,
  ExternalLink,
  Eye,
  FileCheck2,
  FileText,
  GitBranch,
  HelpCircle,
  Home,
  Info,
  KeyRound,
  Landmark,
  Layers,
  List,
  Lock,
  Play,
  RefreshCw,
  Search,
  Server,
  Shield,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  TimerReset,
  Users,
  WalletCards,
  Zap,
} from 'lucide-react';

export default function GuidePage() {
  const [activeTab, setActiveTab] = useState<'quickstart' | 'platform' | 'playbooks' | 'guardrails' | 'ghost' | 'passport' | 'faq'>('quickstart');
  const [faqSearch, setFaqSearch] = useState('');
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [selectedPlaybook, setSelectedPlaybook] = useState<string>('BANK_SERVER_DOWN');

  const webhookSampleUrl = typeof window !== 'undefined' 
    ? `${window.location.origin.replace('3000', '8000')}/webhooks/razorpay` 
    : 'https://api.recoverai.io/webhooks/razorpay';

  const copyWebhookUrl = () => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(webhookSampleUrl);
      setCopiedUrl(true);
      setTimeout(() => setCopiedUrl(false), 2500);
    }
  };

  const setupSteps = [
    {
      id: 'step-1',
      number: '01',
      title: 'Connect Your Razorpay API Credentials',
      icon: Landmark,
      badge: '2 mins',
      description: 'Navigate to Settings and enter your Razorpay Key ID and Key Secret. Click "Test Connection" to cryptographically verify live access before proceeding.',
      action: 'Open Credentials Settings',
      href: '/settings',
      tips: [
        'Use test keys (rzp_test_...) during sandbox evaluation or live keys (rzp_live_...) for production.',
        'Credentials are never logged or stored in plain-text audit records.',
      ],
    },
    {
      id: 'step-2',
      number: '02',
      title: 'Configure Production Webhook in Razorpay',
      icon: GitBranch,
      badge: '1 min',
      description: 'In your Razorpay Dashboard (Settings → Webhooks), create a new webhook endpoint and enable failure and capture events.',
      action: 'View Webhook Configuration',
      href: '/settings',
      eventsToEnable: ['payment.failed', 'payment.captured', 'payment.link.paid', 'order.paid'],
      tips: [
        'Ensure HMAC Secret matches RAZORPAY_WEBHOOK_SECRET in your settings for signature validation.',
        'RecoverAI verifies every payload using constant-time cryptographic hash comparison.',
      ],
    },
    {
      id: 'step-3',
      number: '03',
      title: 'Set Deterministic Guardrail Ceilings',
      icon: SlidersHorizontal,
      badge: '1 min',
      description: 'Define your autonomous financial boundaries: max recovery amount (e.g. ₹10,000), retry limit (max 2), cooldown interval (6h), and allowed notification channels (SMS, Email, WhatsApp).',
      action: 'Configure Safety Guardrails',
      href: '/settings',
      tips: [
        'Any payment exceeding your amount ceiling is automatically escalated to human review (Rule R2).',
        'Customer contact frequency limits prevent spam fatigue (Rule R6).',
      ],
    },
    {
      id: 'step-4',
      number: '04',
      title: 'Simulate or Ingest Your First Payment',
      icon: Activity,
      badge: '1 min',
      description: 'Open the Recovery Assistant (Live Agent Activity) and launch a demo scenario (Bank Downtime, Expired Card, High-Value Escalation) to watch the agent detect, score, guardrail, and execute in real time.',
      action: 'Launch Recovery Assistant',
      href: '/recover',
      tips: [
        'Observe the closed loop: Perception → Diagnosis → Strategy → Guardrail → Execution → Verification.',
        'Inspect raw telemetry, ML probability float scores, and deterministic safety badges.',
      ],
    },
  ];

  const platformPages = [
    {
      title: 'Executive Overview',
      route: '/',
      icon: Home,
      tag: 'Executive Dashboard',
      description: 'High-level financial command center summarizing Revenue at Risk, Total Recovered Revenue, Active Recovery Plans, and Global Success Rate.',
      whenToUse: 'Daily executive check-in to monitor net recovery velocity, active pipeline volume, and financial ROI.',
      keyActions: ['Review top at-risk payment volume', 'Inspect recovery rate progression', 'Jump directly to live opportunities'],
    },
    {
      title: 'Recovery Assistant (Live Console)',
      route: '/recover',
      icon: Zap,
      tag: 'Autonomous AI Engine',
      description: 'Real-time interactive command feed showing the autonomous agent loop streaming live: failure detection, ML scoring, LLM reasoning, guardrail checks, and link dispatches.',
      whenToUse: 'Active operations monitoring or interactive demonstration of demo failure scenarios.',
      keyActions: ['Run pre-configured demo scenarios', 'Inspect step-by-step agent decisions', 'Toggle background autonomous worker'],
    },
    {
      title: 'Recovery Cases (Opportunity Queue)',
      route: '/recovery-cases',
      icon: Briefcase,
      tag: 'Priority Matrix',
      description: 'Intelligent triage queue sorted by Expected Recovery Value (Amount × Probability). Categorizes failures into High, Medium, and Low priority tiers.',
      whenToUse: 'When prioritizing manual interventions or checking high-value opportunities waiting for execution.',
      keyActions: ['Filter by priority tier (High/Med/Low)', 'Inspect expected recovery value in ₹', 'Manually trigger instant recovery run'],
    },
    {
      title: 'Ghost Revenue Hunter',
      route: '/ghost-revenue',
      icon: Eye,
      tag: 'Phantom Capture Auditor',
      description: 'Specialized ledger tracking payments that were captured on Razorpay but dropped out of local checkout session before internal order matching occurred.',
      whenToUse: 'Reconciling unmatched customer payments to ensure orders are fulfilled without double-charging or manual disputes.',
      keyActions: ['Inspect captured-without-order incidents', 'One-click verify and restore order', 'Escalate or trigger investigation'],
    },
    {
      title: 'Recovery Passport & Promise',
      route: '/recovery-passport',
      icon: Brain,
      tag: 'Explainability & Retention',
      description: 'Explainable transparency engine breaking down customer context, ML predictions, native gateway ownership status, and customer Promise-to-Pay agreements.',
      whenToUse: 'Evaluating why a customer was or was not contacted, and logging structured promise-to-pay grace periods for halted subscriptions.',
      keyActions: ['Verify Razorpay native ownership', 'Log customer Promise-to-Pay date', 'Audit attribution rules'],
    },
    {
      title: 'Payments Management',
      route: '/payments',
      icon: CreditCard,
      tag: 'Full Transaction Ledger',
      description: 'Searchable directory of all processed, failed, pending, and recovered transactions with failure taxonomy, attempt counts, and customer associations.',
      whenToUse: 'Looking up a specific customer payment ID, reviewing failure codes, or auditing payment history.',
      keyActions: ['Filter by status or failure code', 'Search by customer or payment ID', 'Trigger single-payment recovery'],
    },
    {
      title: 'Analytics & Financial ROI',
      route: '/analytics',
      icon: BarChart2,
      tag: 'ROI & Model Metrics',
      description: 'Quantitative breakdown of Gross Recovered Revenue vs Communication Costs (SMS, Email), net ROI multiplier, and ML model precision/recall metrics.',
      whenToUse: 'Measuring the direct business return on investment and evaluating classifier accuracy.',
      keyActions: ['Audit Net Recovery ROI multiplier', 'Review channel cost attribution', 'Inspect daily recovery trends'],
    },
    {
      title: 'Audit Trail & Compliance',
      route: '/audit-trail',
      icon: List,
      tag: 'Tamper-Evident Ledger',
      description: 'Immutable, tenant-scoped audit record for every decision made by the system. Tracks exact guardrail triggers (R1-R7), timestamps, and CSV export.',
      whenToUse: 'Compliance reviews, financial audits, dispute resolution, and regulatory accountability.',
      keyActions: ['Search immutable event records', 'Inspect rule veto rationales', 'Export complete audit log to CSV'],
    },
  ];

  const failurePlaybooks = [
    {
      id: 'BANK_SERVER_DOWN',
      name: 'Bank Server Downtime',
      category: 'Transient Failure',
      severity: 'Medium',
      color: 'amber',
      naiveApproach: 'Retries instantly or blasts repetitive spam emails, causing bank rate-limits and customer panic.',
      recoveraiApproach: 'Applies intelligent 10s cooldown → Rechecks gateway status → Dispatches single smart payment link via SMS/Email only if still unsettled.',
      safetyRule: 'Rule R5 (Cooldown Window) & Rule R4 (Max 2 Attempts)',
      expectedRecoveryRate: '75% - 90%',
    },
    {
      id: 'NETWORK_TIMEOUT',
      name: 'Network Latency / Packet Drop',
      category: 'Transient Glitch',
      severity: 'Medium',
      color: 'amber',
      naiveApproach: 'Drops the transaction or forces customer to start entire checkout from scratch.',
      recoveraiApproach: 'Schedules automated gateway verification. If confirmed unpaid, creates a 1-click checkout restoration link.',
      safetyRule: 'Rule R1 (Already Successful) & Rule R5 (Cooldown)',
      expectedRecoveryRate: '80% - 95%',
    },
    {
      id: 'INSUFFICIENT_FUNDS',
      name: 'Insufficient Account Balance',
      category: 'Customer State',
      severity: 'High',
      color: 'rose',
      naiveApproach: 'Immediately re-hits bank card, triggering issuer penalty fees and potential card blocking.',
      recoveraiApproach: 'Enforces polite cooldown window (6 hours) → Sends gentle reminder link enabling alternative payment instruments (UPI / NetBanking).',
      safetyRule: 'Rule R5 (6h Cooldown) & Rule R6 (Max 2 Contacts)',
      expectedRecoveryRate: '45% - 65%',
    },
    {
      id: 'CARD_EXPIRED',
      name: 'Expired Payment Card',
      category: 'Permanent Instrument',
      severity: 'High',
      color: 'rose',
      naiveApproach: 'Loops retries on invalid card, resulting in payment gateway penalties.',
      recoveraiApproach: 'Rule R3 strictly blocks card retries → Overrides strategy to Smart Alternate Payment Link (UPI / NetBanking / New Card).',
      safetyRule: 'Rule R3 (Card Expired No Retry Guarantee)',
      expectedRecoveryRate: '50% - 70%',
    },
    {
      id: 'SUBSCRIPTION_HALTED',
      name: 'Halted Recurring Subscription',
      category: 'Recurring Churn',
      severity: 'High',
      color: 'purple',
      naiveApproach: 'Instantly cancels customer subscription, destroying customer lifetime value.',
      recoveraiApproach: 'Activates Recover Promise (Promise-to-Pay) workflow, giving customer grace period commitment before service suspension.',
      safetyRule: 'Rule R6 (Contact Frequency) & Rule R2 (Ceiling)',
      expectedRecoveryRate: '60% - 80%',
    },
    {
      id: 'INVOICE_OVERDUE',
      name: 'Overdue B2B/B2C Invoice',
      category: 'Invoice Recovery',
      severity: 'Medium',
      color: 'indigo',
      naiveApproach: 'Harasses finance contacts or hands over immediately to manual debt collection.',
      recoveraiApproach: 'Generates structured invoice recovery roadmap with dynamic payment links and scheduled grace milestones.',
      safetyRule: 'Rule R2 (Amount Escalation) & Rule R6 (Contact Limits)',
      expectedRecoveryRate: '65% - 85%',
    },
    {
      id: 'CHECKOUT_ABANDONED',
      name: 'Checkout Cart Abandonment',
      category: 'Friction Drop-off',
      severity: 'Low',
      color: 'cyan',
      naiveApproach: 'Generic discount spam without session context or checkout pre-population.',
      recoveraiApproach: 'Constructs customized 1-click cart recovery link sent via preferred customer channel with 24-hour expiry.',
      safetyRule: 'Rule R6 (Max Contact Limits)',
      expectedRecoveryRate: '30% - 55%',
    },
    {
      id: 'INTERNATIONAL_CARD_UNSUPPORTED',
      name: 'Unsupported International Card',
      category: 'Gateway Managed',
      severity: 'Info',
      color: 'emerald',
      naiveApproach: 'Sends duplicate payment link while Razorpay checkout is presenting currency alternatives.',
      recoveraiApproach: 'Detects native Razorpay alternate checkout in progress and stays strictly in monitoring-only mode to prevent duplicate outreach.',
      safetyRule: 'Native-First Razorpay Fallback Protection',
      expectedRecoveryRate: 'Gateway Dependent',
    },
  ];

  const guardrailsList = [
    {
      id: 'R1',
      name: 'Already Successful Guard',
      condition: 'Payment status is already SUCCESS or CAPTURED',
      outcome: 'BLOCKED → STOP',
      rationale: 'Prevents double-charging or redundant outreach when webhooks replay or when customer pays via an alternative path.',
    },
    {
      id: 'R2',
      name: 'Autonomous Amount Ceiling',
      condition: 'Transaction amount > ₹10,000 (configurable)',
      outcome: 'BLOCKED → ESCALATE_TO_HUMAN',
      rationale: 'Ensures high-value enterprise transactions receive human oversight, eliminating large financial risk exposure.',
    },
    {
      id: 'R3',
      name: 'Card Expired No-Retry',
      condition: 'Failure reason is CARD_EXPIRED and action is RETRY',
      outcome: 'BLOCKED → SEND_PAYMENT_LINK',
      rationale: 'Retrying an expired card is guaranteed to fail and attracts issuer penalty fees; immediately switches to alternative payment methods.',
    },
    {
      id: 'R4',
      name: 'Max Retry Ceiling',
      condition: 'Previous retry attempts ≥ 2',
      outcome: 'BLOCKED → ESCALATE_TO_HUMAN',
      rationale: 'Halts infinite retry loops and bounds autonomous resource consumption.',
    },
    {
      id: 'R5',
      name: 'Cooldown Window',
      condition: 'Last attempt occurred < 6 hours ago for balance failures',
      outcome: 'BLOCKED → WAIT',
      rationale: 'Gives the customer or banking system time to settle before retrying, preventing rapid-fire gateway hammering.',
    },
    {
      id: 'R6',
      name: 'Contact Frequency Ceiling',
      condition: 'Customer has been contacted ≥ 2 times across recovery attempts',
      outcome: 'BLOCKED → STOP',
      rationale: 'Strictly protects customers from communication fatigue and merchant brand erosion.',
    },
    {
      id: 'R7',
      name: 'Fraud & Risk Tripwire',
      condition: 'Failure payload contains FRAUD, STOLEN, or SUSPICIOUS indicators',
      outcome: 'BLOCKED → ESCALATE_TO_HUMAN',
      rationale: 'Strict zero-autonomy fence prohibiting automated recovery on compromised or high-risk instruments.',
    },
  ];

  const faqs = [
    {
      q: 'When does a customer actually receive a payment link?',
      a: 'A payment link is dispatched only after: (1) an initial cooldown and gateway status recheck confirm the payment remains unpaid, (2) Razorpay has no active native retry or alternate checkout running, (3) all 7 deterministic guardrails approve the action, and (4) no active RecoverAI link has already been reserved for this payment.',
    },
    {
      q: 'What does "Razorpay Monitoring" mean in the Live Agent feed?',
      a: 'When a failure occurs due to an unsupported international card or an active subscription auto-retry, Razorpay native workflows are already handling recovery. RecoverAI intentionally stays silent (monitoring-only) to avoid customer confusion, duplicate links, and false attribution.',
    },
    {
      q: 'How does Ghost Revenue Hunter work and what should I do with incidents?',
      a: 'Ghost Revenue occurs when a payment is captured on Razorpay, but local checkout session dropped before creating an internal order. RecoverAI logs these in an isolated incident ledger. You should click "Verify & Restore Order" to attach the captured payment ID to your internal ERP/fulfillment, or escalate for refund. RecoverAI NEVER creates blind orders automatically.',
    },
    {
      q: 'How does Recover Promise (Promise-to-Pay) prevent subscription churn?',
      a: 'For halted subscriptions or overdue invoices, Recover Promise enables you or the customer to agree on a committed payment date. The system schedules a grace period, preventing premature service cancellation while maintaining clear financial commitments.',
    },
    {
      q: 'Can the Large Language Model (LLM) charge my customers directly?',
      a: 'NO. RecoverAI enforces a hard Financial Execution Fence. The LLM only proposes strategies and explains reasoning. All financial actions are strictly validated by deterministic Python guardrails (R1-R7) before being executed by strongly-typed API adapters.',
    },
    {
      q: 'How is data isolated between different merchant accounts?',
      a: 'RecoverAI uses cryptographic zero-trust multi-tenancy. Every request requires an authenticated Bearer JWT or high-entropy API key. All database queries strictly enforce `WHERE merchant_id = ?` at the database level. Attempting cross-tenant access returns an immediate 404.',
    },
    {
      q: 'What happens if Groq or the LLM service experiences an outage?',
      a: 'RecoverAI utilizes a resilient Multi-Provider LLM interface. If Groq encounters rate limits (429) or downtime, it gracefully falls back to local Ollama, and finally to the deterministic MockProvider. The recovery pipeline never crashes.',
    },
  ];

  const filteredFaqs = faqs.filter(
    (f) =>
      f.q.toLowerCase().includes(faqSearch.toLowerCase()) ||
      f.a.toLowerCase().includes(faqSearch.toLowerCase())
  );

  return (
    <div className="max-w-6xl mx-auto space-y-8 pt-2 pb-20">
      
      {/* Hero Banner */}
      <section className="relative overflow-hidden rounded-3xl border border-indigo-100 bg-gradient-to-br from-indigo-700 via-indigo-600 to-violet-700 px-6 py-9 sm:px-10 sm:py-12 text-white shadow-xl shadow-indigo-100">
        <div className="absolute -right-12 -top-16 h-64 w-64 rounded-full bg-white/10 blur-2xl pointer-events-none" />
        <div className="absolute -bottom-20 right-28 h-56 w-56 rounded-full bg-violet-300/15 blur-xl pointer-events-none" />
        
        <div className="relative max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/15 backdrop-blur-md px-3.5 py-1 text-xs font-bold tracking-wide border border-white/20">
            <BookOpen className="h-3.5 w-3.5 text-indigo-200" />
            <span>INTERACTIVE PLATFORM & PLAYBOOK GUIDE</span>
          </div>
          
          <h1 className="mt-4 text-3xl font-extrabold tracking-tight sm:text-4xl text-white">
            Master Autonomous Revenue Recovery
          </h1>
          
          <p className="mt-3 max-w-2xl text-sm leading-6 text-indigo-100 sm:text-base">
            Everything you need to configure, monitor, and master RecoverAI. Understand our 7 failure playbooks, deterministic financial guardrails, Ghost Revenue Hunter, and Recover Promise workflows.
          </p>

          <div className="mt-7 flex flex-wrap items-center gap-3">
            <Link
              href="/settings"
              className="inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-bold text-indigo-700 transition hover:bg-indigo-50 shadow-sm"
            >
              Complete 5-Min Setup <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/recover"
              className="inline-flex items-center gap-2 rounded-xl border border-white/30 bg-white/10 backdrop-blur-sm px-4 py-2.5 text-sm font-bold text-white transition hover:bg-white/20"
            >
              Open Live Assistant <Zap className="h-4 w-4 text-amber-300" />
            </Link>
          </div>
        </div>
      </section>

      {/* Navigation Tabs */}
      <div className="sticky top-0 z-20 -mx-2 px-2 py-2 bg-[#F7F8FB]/90 backdrop-blur-md border-b border-gray-200/60">
        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar p-1 bg-white rounded-2xl border border-gray-200/80 shadow-xs">
          {[
            { id: 'quickstart', label: 'Quick Start', icon: Sparkles },
            { id: 'platform', label: 'Platform Tour', icon: Layers },
            { id: 'playbooks', label: '7 Recovery Playbooks', icon: Activity },
            { id: 'guardrails', label: 'Safety Guardrails', icon: ShieldCheck },
            { id: 'ghost', label: 'Ghost Revenue Hunter', icon: Eye },
            { id: 'passport', label: 'Recover Promise', icon: Brain },
            { id: 'faq', label: 'FAQ & Help', icon: HelpCircle },
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id as any)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-bold whitespace-nowrap transition-all ${
                activeTab === id
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* TAB 1: QUICK START */}
      {activeTab === 'quickstart' && (
        <section className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-indigo-600">First-Time Merchant Onboarding</p>
              <h2 className="mt-1 text-2xl font-extrabold text-gray-900">Get up and running in under 5 minutes</h2>
            </div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700 border border-emerald-200/60 self-start sm:self-auto">
              <CheckCircle2 className="h-3.5 w-3.5" /> 4 Simple Steps
            </span>
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            {setupSteps.map((step) => {
              const Icon = step.icon;
              return (
                <article
                  key={step.id}
                  className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm transition hover:shadow-md hover:border-indigo-100 flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between gap-3 mb-4">
                      <div className="flex items-center gap-3">
                        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-50 text-sm font-extrabold text-indigo-700">
                          {step.number}
                        </span>
                        <h3 className="font-bold text-gray-900 text-base">{step.title}</h3>
                      </div>
                      <span className="text-[11px] font-semibold bg-gray-100 text-gray-600 px-2 py-0.5 rounded-md">
                        {step.badge}
                      </span>
                    </div>

                    <p className="text-sm leading-6 text-gray-600 mb-4">{step.description}</p>

                    {step.eventsToEnable && (
                      <div className="mb-4 bg-gray-50 rounded-xl p-3 border border-gray-100">
                        <p className="text-xs font-bold text-gray-700 mb-2">Required Razorpay Webhook Events:</p>
                        <div className="flex flex-wrap gap-1.5">
                          {step.eventsToEnable.map((evt) => (
                            <span
                              key={evt}
                              className="font-mono text-[11px] bg-white border border-gray-200 text-indigo-700 font-semibold px-2 py-0.5 rounded-md"
                            >
                              {evt}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="space-y-1.5 mb-5 bg-indigo-50/50 rounded-xl p-3 border border-indigo-50">
                      {step.tips.map((tip, i) => (
                        <p key={i} className="text-xs text-indigo-950 flex items-start gap-1.5 leading-5">
                          <span className="text-indigo-600 font-bold">•</span> {tip}
                        </p>
                      ))}
                    </div>
                  </div>

                  <Link
                    href={step.href}
                    className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold text-xs sm:text-sm py-2.5 px-4 transition-all"
                  >
                    {step.action} <ArrowRight className="h-4 w-4" />
                  </Link>
                </article>
              );
            })}
          </div>

          {/* Webhook Endpoint Helper Box */}
          <div className="rounded-3xl border border-indigo-100 bg-white p-6 shadow-sm sm:p-7">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <KeyRound className="h-4 w-4 text-indigo-600" />
                  <h4 className="font-bold text-gray-900">Your Merchant Webhook Receiver Endpoint</h4>
                </div>
                <p className="text-xs text-gray-500">
                  Paste this URL into your Razorpay Dashboard Webhooks setting with your secret key.
                </p>
              </div>

              <div className="flex items-center gap-2 w-full sm:w-auto">
                <code className="px-3 py-1.5 bg-gray-50 border border-gray-200 text-xs font-mono text-gray-800 rounded-lg max-w-full truncate">
                  {webhookSampleUrl}
                </code>
                <button
                  onClick={copyWebhookUrl}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-3 py-1.5 transition-all shrink-0"
                >
                  <Copy className="h-3.5 w-3.5" />
                  {copiedUrl ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* TAB 2: PLATFORM TOUR */}
      {activeTab === 'platform' && (
        <section className="space-y-6">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-indigo-600">Platform Directory</p>
            <h2 className="mt-1 text-2xl font-extrabold text-gray-900">Every Page & Tool in RecoverAI</h2>
            <p className="mt-1 text-sm text-gray-500">Understand the exact purpose and key operations of each interface in your workspace.</p>
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            {platformPages.map((page) => {
              const Icon = page.icon;
              return (
                <div
                  key={page.route}
                  className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm hover:shadow-md hover:border-indigo-100 transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl bg-indigo-50 text-indigo-600">
                          <Icon className="h-5 w-5" />
                        </div>
                        <div>
                          <h3 className="font-bold text-gray-900 text-base">{page.title}</h3>
                          <span className="text-[11px] font-mono text-gray-400">{page.route}</span>
                        </div>
                      </div>
                      <span className="text-[10px] uppercase font-bold tracking-wider bg-indigo-50 text-indigo-700 px-2.5 py-1 rounded-full">
                        {page.tag}
                      </span>
                    </div>

                    <p className="text-sm text-gray-600 leading-relaxed mb-4">{page.description}</p>

                    <div className="mb-4 bg-gray-50/80 rounded-xl p-3 border border-gray-100 space-y-1">
                      <p className="text-xs font-bold text-gray-700">When to use:</p>
                      <p className="text-xs text-gray-500 leading-5">{page.whenToUse}</p>
                    </div>

                    <div className="space-y-1 mb-5">
                      <p className="text-xs font-bold text-gray-700 mb-1.5">Key Actions Available:</p>
                      {page.keyActions.map((act, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs text-gray-600">
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                          <span>{act}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <Link
                    href={page.route}
                    className="inline-flex items-center justify-between rounded-xl bg-gray-50 hover:bg-indigo-50 text-gray-700 hover:text-indigo-700 font-bold text-xs py-2 px-3.5 transition-all border border-gray-100 hover:border-indigo-100"
                  >
                    <span>Open {page.title}</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* TAB 3: 7 RECOVERY PLAYBOOKS */}
      {activeTab === 'playbooks' && (
        <section className="space-y-6">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-indigo-600">Failure Diagnostics & Strategies</p>
            <h2 className="mt-1 text-2xl font-extrabold text-gray-900">7 Failure-Specific Recovery Playbooks</h2>
            <p className="mt-1 text-sm text-gray-500">
              RecoverAI never treats payment failures as monolithic. Compare our intelligent agentic playbooks against naive recovery scripts.
            </p>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            {/* Playbook Selector List */}
            <div className="space-y-2 lg:col-span-1">
              <p className="text-xs font-bold text-gray-400 uppercase tracking-wider px-1">Select Failure Type</p>
              {failurePlaybooks.map((pb) => (
                <button
                  key={pb.id}
                  onClick={() => setSelectedPlaybook(pb.id)}
                  className={`w-full text-left p-3.5 rounded-xl border transition-all flex items-center justify-between gap-3 ${
                    selectedPlaybook === pb.id
                      ? 'bg-indigo-600 border-indigo-600 text-white shadow-md'
                      : 'bg-white border-gray-100 text-gray-800 hover:border-indigo-100 hover:bg-indigo-50/30'
                  }`}
                >
                  <div>
                    <p className={`text-xs font-bold ${selectedPlaybook === pb.id ? 'text-white' : 'text-gray-900'}`}>{pb.name}</p>
                    <p className={`text-[11px] ${selectedPlaybook === pb.id ? 'text-indigo-100' : 'text-gray-400'}`}>{pb.category}</p>
                  </div>
                  <ChevronRight className={`h-4 w-4 ${selectedPlaybook === pb.id ? 'text-white' : 'text-gray-400'}`} />
                </button>
              ))}
            </div>

            {/* Detailed Playbook Viewer */}
            <div className="lg:col-span-2">
              {(() => {
                const pb = failurePlaybooks.find((p) => p.id === selectedPlaybook) || failurePlaybooks[0];
                return (
                  <div className="rounded-3xl border border-gray-100 bg-white p-6 sm:p-8 shadow-sm space-y-6">
                    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 pb-5">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
                            {pb.id}
                          </span>
                          <span className="text-xs font-semibold text-gray-500">• {pb.category}</span>
                        </div>
                        <h3 className="text-xl font-extrabold text-gray-900 mt-1">{pb.name}</h3>
                      </div>
                      <div className="text-right">
                        <p className="text-[11px] uppercase tracking-wider text-gray-400 font-bold">Historical Recovery Rate</p>
                        <p className="text-lg font-extrabold text-emerald-600">{pb.expectedRecoveryRate}</p>
                      </div>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="rounded-2xl border border-rose-100 bg-rose-50/50 p-4 space-y-2">
                        <div className="flex items-center gap-2 text-rose-800 font-bold text-xs uppercase tracking-wide">
                          <ShieldAlert className="h-4 w-4 text-rose-600" />
                          <span>Naive / Basic Automation</span>
                        </div>
                        <p className="text-xs text-rose-950/80 leading-relaxed">{pb.naiveApproach}</p>
                      </div>

                      <div className="rounded-2xl border border-emerald-100 bg-emerald-50/50 p-4 space-y-2">
                        <div className="flex items-center gap-2 text-emerald-800 font-bold text-xs uppercase tracking-wide">
                          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                          <span>RecoverAI Autonomous Agent</span>
                        </div>
                        <p className="text-xs text-emerald-950/80 leading-relaxed">{pb.recoveraiApproach}</p>
                      </div>
                    </div>

                    <div className="rounded-2xl bg-gray-50 border border-gray-100 p-4 space-y-1.5">
                      <p className="text-xs font-bold text-gray-700 flex items-center gap-1.5">
                        <ShieldCheck className="h-4 w-4 text-indigo-600" /> Enforced Safety Boundary:
                      </p>
                      <p className="text-xs text-gray-600">{pb.safetyRule}</p>
                    </div>

                    <div className="flex justify-end">
                      <Link
                        href="/recover"
                        className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs sm:text-sm font-bold px-4 py-2.5 transition-all shadow-sm"
                      >
                        <Play className="h-3.5 w-3.5" /> Test Scenario in Live Console
                      </Link>
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>
        </section>
      )}

      {/* TAB 4: SAFETY GUARDRAILS */}
      {activeTab === 'guardrails' && (
        <section className="space-y-6">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-indigo-600">Deterministic Financial Boundaries</p>
            <h2 className="mt-1 text-2xl font-extrabold text-gray-900">7 Deterministic Safety Guardrails (R1–R7)</h2>
            <p className="mt-1 text-sm text-gray-500">
              In financial operations, an AI recommendation is NEVER an authorization. Hardcoded Python rules hold ultimate veto power over all actions.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {guardrailsList.map((g) => (
              <div key={g.id} className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600 text-white font-mono text-xs font-bold">
                      {g.id}
                    </span>
                    <h3 className="font-bold text-gray-900 text-sm">{g.name}</h3>
                  </div>
                  <span className="font-mono text-[11px] font-bold px-2 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-100">
                    {g.outcome}
                  </span>
                </div>

                <div className="bg-gray-50 rounded-xl p-2.5 border border-gray-100">
                  <p className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">Condition Checked:</p>
                  <p className="font-mono text-xs text-gray-800 mt-0.5">{g.condition}</p>
                </div>

                <p className="text-xs text-gray-600 leading-relaxed">{g.rationale}</p>
              </div>
            ))}
          </div>

          <div className="rounded-3xl border border-indigo-100 bg-indigo-50/50 p-6 sm:p-7 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <h4 className="font-bold text-indigo-950">Customize Your Guardrail Ceilings</h4>
              <p className="text-xs text-indigo-900/80">
                You can adjust max amount thresholds, retry limits, and cooldown hours in your Merchant Settings anytime.
              </p>
            </div>
            <Link
              href="/settings"
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs sm:text-sm font-bold px-4 py-2.5 transition-all shrink-0"
            >
              Adjust Settings <SlidersHorizontal className="h-4 w-4" />
            </Link>
          </div>
        </section>
      )}

      {/* TAB 5: GHOST REVENUE HUNTER */}
      {activeTab === 'ghost' && (
        <section className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-indigo-600">Unmatched Capture Auditor</p>
              <h2 className="mt-1 text-2xl font-extrabold text-gray-900">How Ghost Revenue Hunter Protects You</h2>
              <p className="mt-1 text-sm text-gray-500">
                Solving the phantom capture dilemma: when money is paid on Razorpay but the checkout session dropped.
              </p>
            </div>
            <Link
              href="/ghost-revenue"
              className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 text-white font-bold text-xs px-3.5 py-2 hover:bg-indigo-700 transition-all self-start sm:self-auto"
            >
              Open Ghost Revenue Drawer <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <div className="grid gap-5 md:grid-cols-3">
            <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm space-y-2">
              <div className="flex items-center gap-2 text-indigo-600 font-bold text-sm">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-50 text-xs">1</span>
                <span>Automatic Detection</span>
              </div>
              <p className="text-xs text-gray-600 leading-relaxed">
                When a <code className="text-indigo-700 font-mono text-[11px]">payment.captured</code> webhook arrives from Razorpay with no matching active order in your database, an incident is instantly opened in <code className="text-indigo-700 font-mono text-[11px]">ghost_revenue_incidents</code>.
              </p>
            </div>

            <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm space-y-2">
              <div className="flex items-center gap-2 text-indigo-600 font-bold text-sm">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-50 text-xs">2</span>
                <span>Zero Double Billing</span>
              </div>
              <p className="text-xs text-gray-600 leading-relaxed">
                RecoverAI strictly prohibits creating unverified dummy orders or charging the customer again. All recovery links and retries for this customer are immediately frozen.
              </p>
            </div>

            <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm space-y-2">
              <div className="flex items-center gap-2 text-indigo-600 font-bold text-sm">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-50 text-xs">3</span>
                <span>One-Click Operator Action</span>
              </div>
              <p className="text-xs text-gray-600 leading-relaxed">
                From the Ghost Revenue Hunter interface, an operator can click <b>"Verify & Restore Order"</b> to link the funds to internal fulfillment or mark for refund investigation.
              </p>
            </div>
          </div>

          <div className="rounded-3xl border border-emerald-100 bg-emerald-50/60 p-6 sm:p-7 space-y-3">
            <div className="flex items-center gap-2 text-emerald-900 font-bold text-sm">
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
              <span>Safe Accounting Reconciliation Rule</span>
            </div>
            <p className="text-xs text-emerald-950/80 leading-relaxed">
              Every resolved incident writes an immutable event into <code className="font-mono text-emerald-800">ghost_revenue_events</code> with the operator’s action, internal order ID, and timestamp—giving your accounting team complete audit compliance.
            </p>
          </div>
        </section>
      )}

      {/* TAB 6: RECOVER PROMISE & PASSPORT */}
      {activeTab === 'passport' && (
        <section className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-indigo-600">Customer Retention Workflows</p>
              <h2 className="mt-1 text-2xl font-extrabold text-gray-900">Recovery Passport & Recover Promise</h2>
              <p className="mt-1 text-sm text-gray-500">
                Explainability for every recovery decision and consent-based grace period commitments.
              </p>
            </div>
            <Link
              href="/recovery-passport"
              className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 text-white font-bold text-xs px-3.5 py-2 hover:bg-indigo-700 transition-all self-start sm:self-auto"
            >
              Open Recovery Passport <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            <div className="rounded-3xl border border-gray-100 bg-white p-6 shadow-sm space-y-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-indigo-50 text-indigo-600">
                  <Brain className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-bold text-gray-900 text-base">What is the Recovery Passport?</h3>
                  <p className="text-xs text-gray-400">Explainable eligibility engine</p>
                </div>
              </div>
              <p className="text-xs text-gray-600 leading-relaxed">
                Before any customer is contacted, RecoverAI generates a lightweight <b>Recovery Passport</b>. It transparently explains customer lifetime value (LTV), ML expected recovery probability, gateway ownership (native vs incremental), and the specific guardrails applied.
              </p>
              <div className="rounded-xl bg-gray-50 p-3 text-xs text-gray-600 space-y-1 font-mono border border-gray-100">
                <p>• native_recovery_active: false</p>
                <p>• eligible_for_recoverai: true</p>
                <p>• attribution: RecoverAI-incremental</p>
              </div>
            </div>

            <div className="rounded-3xl border border-gray-100 bg-white p-6 shadow-sm space-y-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-purple-50 text-purple-600">
                  <TimerReset className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-bold text-gray-900 text-base">What is Recover Promise (Promise-to-Pay)?</h3>
                  <p className="text-xs text-gray-400">Consent-based churn prevention</p>
                </div>
              </div>
              <p className="text-xs text-gray-600 leading-relaxed">
                For halted recurring subscriptions (<code className="text-purple-700 font-mono text-[11px]">SUBSCRIPTION_HALTED</code>) or overdue invoices (<code className="text-purple-700 font-mono text-[11px]">INVOICE_OVERDUE</code>), customers can commit to a promised future payment date. This keeps their service active and eliminates churn.
              </p>
              <div className="rounded-xl bg-purple-50/50 p-3 text-xs text-purple-950 space-y-1 border border-purple-100">
                <p className="font-bold text-purple-900">Key Safeguards:</p>
                <p>• Strict guardrail blocks Promise-to-Pay for already captured payments.</p>
                <p>• Unavailable while Razorpay native retries are active.</p>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* TAB 7: FAQ & SEARCH */}
      {activeTab === 'faq' && (
        <section className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-indigo-600">Knowledge Base & FAQ</p>
              <h2 className="mt-1 text-2xl font-extrabold text-gray-900">Frequently Asked Questions</h2>
            </div>
            
            {/* Search Input */}
            <div className="relative w-full sm:w-72">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
              <input
                type="text"
                value={faqSearch}
                onChange={(e) => setFaqSearch(e.target.value)}
                placeholder="Search questions..."
                className="w-full rounded-xl border border-gray-200 bg-white py-2 pl-9 pr-4 text-xs sm:text-sm font-medium outline-none focus:border-indigo-600 focus:ring-1 focus:ring-indigo-600 transition-all"
              />
            </div>
          </div>

          <div className="rounded-3xl border border-gray-100 bg-white p-6 sm:p-8 shadow-sm divide-y divide-gray-100">
            {filteredFaqs.length > 0 ? (
              filteredFaqs.map((faq, index) => (
                <details key={index} className="group py-4 first:pt-0 last:pb-0" open={index === 0}>
                  <summary className="cursor-pointer list-none font-bold text-gray-900 text-sm sm:text-base flex items-center justify-between gap-3">
                    <span>{faq.q}</span>
                    <ChevronDown className="h-4 w-4 text-indigo-600 transition-transform group-open:rotate-180 shrink-0" />
                  </summary>
                  <p className="mt-2.5 max-w-4xl text-xs sm:text-sm leading-relaxed text-gray-600">
                    {faq.a}
                  </p>
                </details>
              ))
            ) : (
              <div className="py-8 text-center text-gray-400 text-sm">
                No matching questions found for "{faqSearch}". Try searching for keywords like "Razorpay", "Guardrail", or "Ghost".
              </div>
            )}
          </div>
        </section>
      )}

      {/* Persistent Help Callout Footer */}
      <section className="rounded-3xl border border-gray-100 bg-white p-6 sm:p-8 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-5">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
            <Sparkles className="h-6 w-6" />
          </div>
          <div>
            <h4 className="font-bold text-gray-900 text-base">Ready to test the autonomous agent?</h4>
            <p className="text-xs sm:text-sm text-gray-500">
              Run real-time simulated payment events or test your live webhook integration in the Agent Console.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <Link
            href="/recover"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs sm:text-sm font-bold px-5 py-2.5 transition-all shadow-sm"
          >
            <Zap className="h-4 w-4 text-amber-300" /> Open Recovery Assistant
          </Link>
        </div>
      </section>

    </div>
  );
}
'use client';

import { useEffect, useState } from 'react';
import { ShieldCheck, RefreshCw, BadgeIndianRupee, HeartHandshake } from 'lucide-react';
import { useAuth } from '@/lib/auth-context';

type Bucket = { cases: number; value: number };
type Impact = { at_risk: Bucket; razorpay_native_monitored: Bucket; recoverai_incremental_verified: Bucket; open_promises_to_pay: Bucket };

const money = (value = 0) => `₹${Number(value).toLocaleString('en-IN')}`;

export default function RecoveryPassportPage() {
  const { apiFetch } = useAuth();
  const [impact, setImpact] = useState<Impact | null>(null);
  const [paymentId, setPaymentId] = useState('');
  const [passport, setPassport] = useState<any>(null);
  const [message, setMessage] = useState('');

  const loadImpact = async () => {
    const res = await apiFetch('/recovery/impact');
    if (res.ok) setImpact(await res.json());
  };
  useEffect(() => { loadImpact().catch(() => undefined); }, []);

  const inspect = async (event: React.FormEvent) => {
    event.preventDefault(); setMessage(''); setPassport(null);
    const res = await apiFetch(`/recovery/passport/${encodeURIComponent(paymentId)}`);
    if (!res.ok) { setMessage('That payment was not found in this workspace.'); return; }
    setPassport(await res.json());
  };

  return <div className="max-w-6xl mx-auto space-y-6 pt-2 pb-16">
    <div>
      <p className="text-xs font-bold uppercase tracking-widest text-indigo-600">Recovery Passport</p>
      <h1 className="text-3xl font-serif font-bold text-gray-900 mt-1">Prove every recovery is incremental.</h1>
      <p className="text-sm text-gray-500 mt-2">RecoverAI stays silent while Razorpay owns recovery, then acts only on eligible revenue risk.</p>
    </div>

    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {[
        ['Revenue at risk', impact?.at_risk, 'bg-slate-900 text-white'],
        ['Razorpay-native monitored', impact?.razorpay_native_monitored, 'bg-blue-50 text-blue-950'],
        ['RecoverAI incremental verified', impact?.recoverai_incremental_verified, 'bg-emerald-50 text-emerald-950'],
        ['Open promises to pay', impact?.open_promises_to_pay, 'bg-amber-50 text-amber-950'],
      ].map(([label, bucket, style]) => <div key={String(label)} className={`rounded-3xl p-5 border border-black/5 ${style}`}>
        <p className="text-xs font-bold opacity-65">{String(label)}</p>
        <p className="text-2xl font-black mt-2">{money((bucket as Bucket | undefined)?.value)}</p>
        <p className="text-xs mt-1 opacity-70">{(bucket as Bucket | undefined)?.cases || 0} cases</p>
      </div>)}
    </div>

    <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
      <div className="flex items-start gap-3"><ShieldCheck className="h-6 w-6 text-indigo-600 shrink-0" /><div><h2 className="font-bold text-gray-900">Native-first policy</h2><p className="text-sm text-gray-500 mt-1">Razorpay retry and alternate-checkout paths are excluded from RecoverAI revenue attribution. No duplicate payment link is created.</p></div></div>
    </div>

    <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <form onSubmit={inspect} className="lg:col-span-2 bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-4">
        <h2 className="font-bold text-gray-900">Inspect a recovery case</h2>
        <input value={paymentId} onChange={e => setPaymentId(e.target.value)} placeholder="Payment ID" required className="w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-200" />
        <button className="w-full rounded-xl bg-indigo-600 text-white text-sm font-bold py-2.5 flex justify-center gap-2"><RefreshCw className="h-4 w-4" />Open passport</button>
        {message && <p className="text-sm text-red-600">{message}</p>}
      </form>
      <div className="lg:col-span-3 bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
        {!passport ? <div className="h-full min-h-40 grid place-items-center text-center text-sm text-gray-400"><div><HeartHandshake className="h-7 w-7 mx-auto mb-2" />Enter a payment ID to see its eligibility, predicted value, safety controls, and attribution.</div></div> : <div className="space-y-4"><div className="flex justify-between gap-4"><div><p className="text-xs font-bold text-gray-400">{passport.recovery_type.replaceAll('_',' ')}</p><h2 className="text-xl font-black text-gray-900">{money(passport.amount)} recovery case</h2></div><span className={`h-fit rounded-full px-3 py-1 text-xs font-bold ${passport.eligible_for_recoverai ? 'bg-emerald-100 text-emerald-700' : 'bg-blue-100 text-blue-700'}`}>{passport.eligible_for_recoverai ? 'Eligible for RecoverAI' : 'Razorpay owns recovery'}</span></div><p className="text-sm text-gray-600">{passport.eligibility_reason}</p><div className="grid grid-cols-2 gap-3 text-sm"><div className="rounded-2xl bg-gray-50 p-3"><p className="text-xs text-gray-400">Expected recovery</p><b>{money(passport.prediction.expected_recovery_value)}</b></div><div className="rounded-2xl bg-gray-50 p-3"><p className="text-xs text-gray-400">Recovery probability</p><b>{Math.round(passport.prediction.recovery_probability * 100)}%</b></div></div><p className="text-xs text-gray-500 border-t pt-3">Attribution: {passport.attribution_rule}</p></div>}
      </div>
    </div>
  </div>;
}

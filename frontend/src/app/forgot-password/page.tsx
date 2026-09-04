'use client';

import { FormEvent, useState } from 'react';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [resetUrl, setResetUrl] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage(''); setResetUrl('');
    try {
      const response = await fetch(`${API_BASE}/auth/forgot-password`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }),
      });
      const data = await response.json();
      setMessage(data.message || 'If an account exists, a reset link has been sent.');
      if (data.reset_url) setResetUrl(data.reset_url);
    } catch { setMessage('We could not reach the server. Please try again.'); }
    finally { setBusy(false); }
  }

  return <main className="min-h-screen w-full bg-cover bg-center bg-fixed flex items-center justify-center p-5" style={{ backgroundImage: "linear-gradient(115deg, rgba(8,18,42,.28), rgba(8,18,42,.12)), url('/auth-background.png')" }}>
    <section className="w-full max-w-md rounded-[28px] border border-white/35 bg-slate-950/45 shadow-2xl shadow-slate-950/20 backdrop-blur-xl p-7 sm:p-10">
      <Link href="/login" className="text-sm font-semibold text-indigo-200">← Back to sign in</Link>
      <h1 className="mt-8 text-3xl font-extrabold tracking-tight text-white">Reset your password</h1>
      <p className="mt-2 text-sm leading-6 text-white/75">Enter your work email and we’ll send you a secure link to choose a new password.</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <input required type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="Work email" className="auth-input" />
        <button disabled={busy} className="w-full rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-950/30 disabled:opacity-50">{busy ? 'Sending…' : 'Send reset link'}</button>
      </form>
      {message && <p className="mt-5 rounded-xl border border-indigo-200/30 bg-indigo-400/20 px-4 py-3 text-sm text-white" role="status">{message}</p>}
      {resetUrl && <a href={resetUrl} className="mt-3 block break-all text-xs text-indigo-200 underline">Open development reset link</a>}
    </section>
  </main>;
}

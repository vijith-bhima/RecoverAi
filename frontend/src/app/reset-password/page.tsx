'use client';

import { FormEvent, useEffect, useState } from 'react';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function ResetPasswordPage() {
  const [token, setToken] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [message, setMessage] = useState('');
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const value = new URLSearchParams(window.location.search).get('token') || '';
    setToken(value);
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (password !== confirm) { setMessage('Passwords do not match.'); return; }
    setBusy(true); setMessage('');
    try {
      const response = await fetch(`${API_BASE}/auth/reset-password`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token, new_password: password }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'This link is invalid or expired.');
      setDone(true); setMessage(data.message);
    } catch (error: any) { setMessage(error.message); }
    finally { setBusy(false); }
  }

  return <main className="min-h-screen w-full bg-cover bg-center bg-fixed flex items-center justify-center p-5" style={{ backgroundImage: "linear-gradient(115deg, rgba(8,18,42,.28), rgba(8,18,42,.12)), url('/auth-background.png')" }}>
    <section className="w-full max-w-md rounded-[28px] border border-white/35 bg-slate-950/45 shadow-2xl shadow-slate-950/20 backdrop-blur-xl p-7 sm:p-10">
      <Link href="/login" className="text-sm font-semibold text-indigo-200">← Back to sign in</Link>
      <h1 className="mt-8 text-3xl font-extrabold tracking-tight text-white">Choose a new password</h1>
      <p className="mt-2 text-sm leading-6 text-white/75">Use at least eight characters. This link works once and expires after 30 minutes.</p>
      {!done ? <form onSubmit={submit} className="mt-6 space-y-4">
        <input required minLength={8} type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="New password" className="auth-input" />
        <input required minLength={8} type="password" value={confirm} onChange={e => setConfirm(e.target.value)} placeholder="Confirm new password" className="auth-input" />
        <button disabled={busy || !token} className="w-full rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-950/30 disabled:opacity-50">{busy ? 'Updating…' : 'Update password'}</button>
      </form> : <Link href="/login" className="mt-6 block w-full rounded-xl bg-indigo-600 px-4 py-3 text-center text-sm font-semibold text-white">Return to sign in</Link>}
      {message && <p className="mt-5 rounded-xl border border-indigo-200/30 bg-indigo-400/20 px-4 py-3 text-sm text-white" role="status">{message}</p>}
    </section>
  </main>;
}

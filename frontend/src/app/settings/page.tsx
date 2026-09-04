'use client';

import React, { useState, useEffect } from 'react';
import {
  Shield, Key, Link2, CheckCircle2, AlertTriangle, RefreshCw,
  Save, Sliders, Smartphone, MessageSquare, Mail, Zap, ExternalLink,
  Copy, Check, User, Building, Lock, Sparkles, Database, Eye, EyeOff,
  ShieldCheck, ArrowUpRight, Terminal, Globe, HelpCircle, CheckCircle
} from 'lucide-react';
import { useAuth } from '../../lib/auth-context';

const API_ORIGIN = (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

export default function SettingsPage() {
  const { user, updateProfile, apiFetch, refreshProfiles } = useAuth();
  const [activeTab, setActiveTab] = useState<'profile' | 'gateway' | 'webhooks' | 'guardrails' | 'channels' | 'brand'>('gateway');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  
  // Profile form state
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [companyName, setCompanyName] = useState(user?.company_name || '');
  const [newPassword, setNewPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  // Secret visibility states
  const [showKeySecret, setShowKeySecret] = useState(false);
  const [showWebhookSecret, setShowWebhookSecret] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);

  // Test connection state
  const [testingConnection, setTestingConnection] = useState(false);
  const [testResult, setTestResult] = useState<{ status: 'success' | 'error'; message: string } | null>(null);

  // Copy state
  const [copiedWebhook, setCopiedWebhook] = useState(false);
  const [copiedApiKey, setCopiedApiKey] = useState(false);
  const [copiedKeyId, setCopiedKeyId] = useState(false);
  const [regeneratingApiKey, setRegeneratingApiKey] = useState(false);

  // Form fields
  const [settings, setSettings] = useState({
    brand_name: '',
    support_email: '',
    razorpay_key_id: '',
    razorpay_key_secret: '',
    razorpay_webhook_secret: '',
    webhook_url: '',
    max_autonomous_amount: 10000,
    max_retry_attempts: 2,
    retry_cooldown_hours: 6,
    enable_sms: true,
    enable_whatsapp: false,
    enable_email: true,
    message_template: 'Hi {{customer_name}}, your payment of ₹{{amount}} failed. Complete securely here: {{payment_link}}',
  });

  useEffect(() => {
    if (user) {
      setFullName(user.full_name || '');
      setCompanyName(user.company_name || '');
    }
    fetchSettings();
  }, [user]);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/settings');
      if (res.ok) {
        const data = await res.json();
        setSettings(prev => ({
          ...prev,
          ...data,
          // Keep the integration URL tenant-specific even when an older API
          // response or a cached page omits it.
          webhook_url: data.webhook_url || `${API_ORIGIN}/webhooks/razorpay?merchant_id=${encodeURIComponent(user?.merchant_id || '')}`,
        }));
      }
    } catch (err) {
      console.error('Error loading settings:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setSaving(true);
    setSaveSuccess(false);
    try {
      const res = await apiFetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      });
      if (res.ok) {
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 4000);
      }
    } catch (err) {
      console.error('Save settings error:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleProfileUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileSaving(true);
    setProfileError(null);
    setProfileSuccess(false);

    const payload: any = {
      full_name: fullName,
      company_name: companyName,
    };
    if (newPassword.trim()) {
      payload.new_password = newPassword.trim();
    }

    const res = await updateProfile(payload);
    setProfileSaving(false);
    if (res.success) {
      setProfileSuccess(true);
      setNewPassword('');
      setTimeout(() => setProfileSuccess(false), 4000);
    } else {
      setProfileError(res.error || 'Failed to update profile');
    }
  };

  const handleRegenerateApiKey = async () => {
    if (!confirm('Are you sure you want to regenerate your API key? Any active external scripts or webhook sources using this key will immediately stop working until updated.')) {
      return;
    }
    setRegeneratingApiKey(true);
    try {
      const res = await apiFetch('/auth/regenerate-api-key', { method: 'POST' });
      if (res.ok) {
        await refreshProfiles();
        await fetchSettings();
      }
    } catch (e) {
      console.error('Regenerate key error:', e);
    } finally {
      setRegeneratingApiKey(false);
    }
  };

  const handleTestRazorpay = async () => {
    if (!settings.razorpay_key_id.trim() || !settings.razorpay_key_secret.trim()) {
      setTestResult({
        status: 'error',
        message: 'Please enter both your Razorpay Key ID and Key Secret in the fields below before testing.',
      });
      return;
    }

    setTestingConnection(true);
    setTestResult(null);
    try {
      const res = await apiFetch('/api/settings/test-razorpay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          key_id: settings.razorpay_key_id,
          key_secret: settings.razorpay_key_secret,
        }),
      });
      const data = await res.json();
      if (res.ok && data.status === 'connected') {
        setTestResult({ status: 'success', message: data.message });
      } else {
        setTestResult({ status: 'error', message: data.detail || data.message || 'Connection failed' });
      }
    } catch (err: any) {
      setTestResult({ status: 'error', message: 'Unable to reach backend to verify keys.' });
    } finally {
      setTestingConnection(false);
    }
  };

  const copyWebhookUrl = () => {
    navigator.clipboard.writeText(settings.webhook_url);
    setCopiedWebhook(true);
    setTimeout(() => setCopiedWebhook(false), 2500);
  };

  const copyApiKey = () => {
    if (user?.api_key) {
      navigator.clipboard.writeText(user.api_key);
      setCopiedApiKey(true);
      setTimeout(() => setCopiedApiKey(false), 2500);
    }
  };

  const copyKeyId = () => {
    if (settings.razorpay_key_id) {
      navigator.clipboard.writeText(settings.razorpay_key_id);
      setCopiedKeyId(true);
      setTimeout(() => setCopiedKeyId(false), 2500);
    }
  };

  return (
    <div className="max-w-[1240px] mx-auto space-y-6 pt-2 pb-20">
      {/* Top Header Card */}
      <div className="bg-white rounded-3xl border border-gray-100/90 shadow-sm p-6 sm:p-8 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6">
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-indigo-50 text-indigo-700 border border-indigo-100">
              <ShieldCheck className="h-3.5 w-3.5 text-indigo-600" />
              Tenant ID: {user?.merchant_id || user?.user_id || 'mer_default'}
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-100">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              PBKDF2 &amp; JWT Encrypted
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
            Settings &amp; Integrations
          </h1>
          <p className="text-sm text-gray-500 max-w-2xl">
            Configure live Razorpay payment gateway credentials, manage isolated tenant API secrets, and customize deterministic revenue recovery guardrails.
          </p>
        </div>

        <button
          onClick={() => handleSave()}
          disabled={saving}
          className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-700 hover:to-indigo-800 disabled:opacity-50 text-white px-6 py-3 rounded-2xl text-sm font-bold shadow-lg shadow-indigo-100 transition-all cursor-pointer hover:shadow-indigo-200"
        >
          {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          {saving ? 'Saving...' : 'Save Configuration'}
        </button>
      </div>

      {saveSuccess && (
        <div className="p-4 bg-emerald-50 border border-emerald-200/90 rounded-2xl flex items-center gap-3 text-emerald-900 text-sm font-semibold animate-in fade-in shadow-sm">
          <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" />
          <span>Configuration, secrets, and safety guardrails successfully committed and applied to your workspace.</span>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex gap-1.5 sm:gap-2 p-1.5 bg-gray-100/90 rounded-2xl overflow-x-auto scrollbar-hide border border-gray-200/50">
        <button
          onClick={() => setActiveTab('gateway')}
          className={`whitespace-nowrap flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all ${
            activeTab === 'gateway'
              ? 'bg-white text-indigo-700 shadow-sm border border-gray-200/60'
              : 'text-gray-600 hover:text-gray-900 hover:bg-white/50'
          }`}
        >
          <Key className="h-3.5 w-3.5 shrink-0 text-indigo-600" /> Razorpay Credentials
        </button>

        <button
          onClick={() => setActiveTab('webhooks')}
          className={`whitespace-nowrap flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all ${
            activeTab === 'webhooks'
              ? 'bg-white text-indigo-700 shadow-sm border border-gray-200/60'
              : 'text-gray-600 hover:text-gray-900 hover:bg-white/50'
          }`}
        >
          <Link2 className="h-3.5 w-3.5 shrink-0 text-indigo-600" /> Webhooks &amp; API Keys
        </button>

        <button
          onClick={() => setActiveTab('guardrails')}
          className={`whitespace-nowrap flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all ${
            activeTab === 'guardrails'
              ? 'bg-white text-indigo-700 shadow-sm border border-gray-200/60'
              : 'text-gray-600 hover:text-gray-900 hover:bg-white/50'
          }`}
        >
          <Shield className="h-3.5 w-3.5 shrink-0 text-indigo-600" /> Safety Guardrails
        </button>

        <button
          onClick={() => setActiveTab('channels')}
          className={`whitespace-nowrap flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all ${
            activeTab === 'channels'
              ? 'bg-white text-indigo-700 shadow-sm border border-gray-200/60'
              : 'text-gray-600 hover:text-gray-900 hover:bg-white/50'
          }`}
        >
          <Smartphone className="h-3.5 w-3.5 shrink-0 text-indigo-600" /> Notification Channels
        </button>

        <button
          onClick={() => setActiveTab('brand')}
          className={`whitespace-nowrap flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all ${
            activeTab === 'brand'
              ? 'bg-white text-indigo-700 shadow-sm border border-gray-200/60'
              : 'text-gray-600 hover:text-gray-900 hover:bg-white/50'
          }`}
        >
          <Sliders className="h-3.5 w-3.5 shrink-0 text-indigo-600" /> Brand &amp; Messages
        </button>

        <button
          onClick={() => setActiveTab('profile')}
          className={`whitespace-nowrap flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all ${
            activeTab === 'profile'
              ? 'bg-white text-indigo-700 shadow-sm border border-gray-200/60'
              : 'text-gray-600 hover:text-gray-900 hover:bg-white/50'
          }`}
        >
          <User className="h-3.5 w-3.5 shrink-0 text-indigo-600" /> Profile &amp; Workspace
        </button>
      </div>

      {/* ──────────────────────────────────────────────────────────── */}
      {/* TAB 1: RAZORPAY CREDENTIALS (VAULT) */}
      {/* ──────────────────────────────────────────────────────────── */}
      {activeTab === 'gateway' && (
        <div className="space-y-6">
          <div className="bg-white rounded-3xl border border-gray-100 shadow-sm p-6 sm:p-8 space-y-6">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-4 border-b border-gray-100">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-extrabold text-gray-900 text-lg">Razorpay API Credentials Vault</h3>
                  <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                    Encrypted Secret Storage
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  RecoverAI uses these credentials to generate authenticated payment links and query real transaction statuses.
                </p>
              </div>

              <a
                href="https://dashboard.razorpay.com/app/keys"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-xs font-bold text-indigo-600 hover:text-indigo-700 bg-indigo-50/80 hover:bg-indigo-100/80 px-3.5 py-2 rounded-xl transition-all"
              >
                <span>Get Keys from Razorpay Dashboard</span>
                <ArrowUpRight className="h-3.5 w-3.5" />
              </a>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Key ID */}
              <div className="space-y-2">
                <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider">
                  Razorpay Key ID
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={settings.razorpay_key_id}
                    onChange={(e) => setSettings({ ...settings, razorpay_key_id: e.target.value })}
                    placeholder="rzp_live_xxxxxxxxxxxxxx or rzp_test_xxxxxx"
                    className="w-full bg-gray-50/70 border border-gray-200 rounded-2xl px-4 py-3 text-sm font-mono text-gray-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition-all pr-12"
                  />
                  {settings.razorpay_key_id && (
                    <button
                      type="button"
                      onClick={copyKeyId}
                      className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-200/60 transition-all"
                      title="Copy Key ID"
                    >
                      {copiedKeyId ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}
                    </button>
                  )}
                </div>
                <p className="text-[11px] text-gray-400">Public key identifier generated in your Razorpay dashboard.</p>
              </div>

              {/* Key Secret */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Razorpay Key Secret
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowKeySecret(!showKeySecret)}
                    className="flex items-center gap-1 text-[11px] font-bold text-gray-500 hover:text-gray-800 transition-colors"
                  >
                    {showKeySecret ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                    <span>{showKeySecret ? 'Hide Secret' : 'Reveal Secret'}</span>
                  </button>
                </div>
                <div className="relative">
                  <input
                    type={showKeySecret ? 'text' : 'password'}
                    autoComplete="new-password"
                    value={settings.razorpay_key_secret}
                    onChange={(e) => setSettings({ ...settings, razorpay_key_secret: e.target.value })}
                    placeholder="Enter Razorpay Key Secret"
                    className="w-full bg-gray-50/70 border border-gray-200 rounded-2xl px-4 py-3 text-sm font-mono text-gray-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition-all pr-12"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKeySecret(!showKeySecret)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-200/60 transition-all"
                  >
                    {showKeySecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                <p className="text-[11px] text-gray-400">Kept encrypted on server. Never exposed to browser or client bundles.</p>
              </div>
            </div>

            {/* Test Connection Box */}
            <div className="bg-gray-50/80 rounded-2xl p-5 border border-gray-200/70 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="space-y-0.5">
                <h4 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                  <Zap className="h-4 w-4 text-amber-500" />
                  Live Connection Verification
                </h4>
                <p className="text-xs text-gray-500">
                  Sends an authenticated ping to Razorpay API v1 to verify key validity and balance access.
                </p>
              </div>

              <button
                type="button"
                onClick={handleTestRazorpay}
                disabled={testingConnection}
                className="inline-flex items-center gap-2 bg-white hover:bg-gray-100 text-gray-800 border border-gray-300/80 px-4 py-2.5 rounded-xl text-xs font-bold transition-all shadow-sm shrink-0 cursor-pointer"
              >
                {testingConnection ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Zap className="h-3.5 w-3.5 text-amber-500" />}
                {testingConnection ? 'Testing Gateway...' : 'Test Razorpay Connection'}
              </button>
            </div>

            {testResult && (
              <div
                className={`p-4 rounded-2xl border text-xs font-semibold flex items-center gap-3 animate-in fade-in ${
                  testResult.status === 'success'
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                    : 'bg-red-50 border-red-200 text-red-900'
                }`}
              >
                {testResult.status === 'success' ? (
                  <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" />
                ) : (
                  <AlertTriangle className="h-5 w-5 text-red-600 shrink-0" />
                )}
                <span>{testResult.message}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ──────────────────────────────────────────────────────────── */}
      {/* TAB 2: WEBHOOKS & API KEYS */}
      {/* ──────────────────────────────────────────────────────────── */}
      {activeTab === 'webhooks' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left Card: Razorpay Webhook Configuration */}
            <div className="bg-white rounded-3xl border border-gray-100 shadow-sm p-6 sm:p-8 space-y-6 flex flex-col justify-between">
              <div className="space-y-5">
                <div className="pb-4 border-b border-gray-100">
                  <div className="flex items-center gap-2">
                    <h3 className="font-extrabold text-gray-900 text-base">Razorpay Webhook Endpoint</h3>
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                      HMAC-SHA256
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    Paste this endpoint into your Razorpay Webhook settings to feed real-time failure events to the autonomous agent.
                  </p>
                </div>

                {/* Webhook URL Box */}
                <div className="space-y-2">
                  <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Webhook Destination URL
                  </label>
                  <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-2xl p-2.5">
                    <div className="font-mono text-xs text-gray-800 font-semibold px-2 truncate flex-1">
                      {settings.webhook_url}
                    </div>
                    <button
                      type="button"
                      onClick={copyWebhookUrl}
                      className="inline-flex items-center gap-1 text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1.5 rounded-xl transition-all shrink-0 shadow-sm"
                    >
                      {copiedWebhook ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                      <span>{copiedWebhook ? 'Copied' : 'Copy'}</span>
                    </button>
                  </div>
                </div>

                {/* Razorpay Webhook Secret */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider">
                      Webhook Secret (HMAC Verification)
                    </label>
                    <button
                      type="button"
                      onClick={() => setShowWebhookSecret(!showWebhookSecret)}
                      className="flex items-center gap-1 text-[11px] font-bold text-gray-500 hover:text-gray-800 transition-colors"
                    >
                      {showWebhookSecret ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                      <span>{showWebhookSecret ? 'Hide' : 'Reveal'}</span>
                    </button>
                  </div>
                  <div className="relative">
                    <input
                      type={showWebhookSecret ? 'text' : 'password'}
                      autoComplete="new-password"
                      value={settings.razorpay_webhook_secret}
                      onChange={(e) => setSettings({ ...settings, razorpay_webhook_secret: e.target.value })}
                      placeholder="Enter Webhook Secret configured in Razorpay"
                      className="w-full bg-gray-50/70 border border-gray-200 rounded-2xl px-4 py-3 text-sm font-mono text-gray-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition-all pr-12"
                    />
                    <button
                      type="button"
                      onClick={() => setShowWebhookSecret(!showWebhookSecret)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-200/60 transition-all"
                    >
                      {showWebhookSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                {/* Events Checklist */}
                <div className="space-y-2 pt-2">
                  <span className="block text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Required Active Events to Subscribe:
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
                    <div className="flex items-center gap-2 p-2 rounded-xl bg-gray-50 border border-gray-200/80 font-mono text-[11px] text-gray-800">
                      <CheckCircle className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                      <span>payment.failed</span>
                    </div>
                    <div className="flex items-center gap-2 p-2 rounded-xl bg-gray-50 border border-gray-200/80 font-mono text-[11px] text-gray-800">
                      <CheckCircle className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                      <span>payment.captured</span>
                    </div>
                    <div className="flex items-center gap-2 p-2 rounded-xl bg-gray-50 border border-gray-200/80 font-mono text-[11px] text-gray-800">
                      <CheckCircle className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                      <span>payment_link.paid</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
                <span className="flex items-center gap-1.5">
                  <ShieldCheck className="h-4 w-4 text-indigo-600" />
                  Signatures validated on arrival
                </span>
                <span className="text-[11px] text-gray-400">Header: x-razorpay-signature</span>
              </div>
            </div>

            {/* Right Card: Merchant API Key Management */}
            <div className="bg-white rounded-3xl border border-gray-100 shadow-sm p-6 sm:p-8 space-y-6 flex flex-col justify-between">
              <div className="space-y-5">
                <div className="pb-4 border-b border-gray-100">
                  <div className="flex items-center gap-2">
                    <h3 className="font-extrabold text-gray-900 text-base">Merchant Live API Key</h3>
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-purple-50 text-purple-700 border border-purple-200">
                      Tenant-Scoped
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    Pass this key in <code className="bg-gray-100 px-1 py-0.5 rounded font-mono text-[11px]">X-API-Key</code> request headers to ingest events from external servers.
                  </p>
                </div>

                <div className="p-4 bg-gray-50/80 rounded-2xl border border-gray-200 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-gray-600 uppercase tracking-wider">Secret API Key</span>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setShowApiKey(!showApiKey)}
                        className="flex items-center gap-1 text-[11px] font-bold text-gray-600 hover:text-gray-900 bg-white border border-gray-200 px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
                      >
                        {showApiKey ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                        <span>{showApiKey ? 'Hide' : 'Reveal'}</span>
                      </button>

                      <button
                        type="button"
                        onClick={copyApiKey}
                        className="flex items-center gap-1 text-[11px] font-bold text-indigo-600 hover:text-indigo-700 bg-indigo-50 border border-indigo-100 px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
                      >
                        {copiedApiKey ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                        <span>{copiedApiKey ? 'Copied' : 'Copy'}</span>
                      </button>
                    </div>
                  </div>

                  <div className="font-mono text-xs text-gray-900 font-bold break-all bg-white p-3 rounded-xl border border-gray-200/80">
                    {showApiKey
                      ? user?.api_key || 'rec_live_demo_merchant_key'
                      : (user?.api_key ? `rec_live_${'•'.repeat(24)}` : 'rec_live_••••••••••••••••••••••••')}
                  </div>
                </div>

                <div className="bg-amber-50/70 border border-amber-200/80 rounded-2xl p-4 text-xs text-amber-900 space-y-1">
                  <div className="flex items-center gap-1.5 font-bold">
                    <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
                    <span>Security Warning</span>
                  </div>
                  <p className="text-[11px] text-amber-800">
                    Never expose this API key in client-side code or public GitHub repositories. All requests using this key run with full merchant workspace permissions.
                  </p>
                </div>
              </div>

              <div className="pt-4 border-t border-gray-100 flex flex-col sm:flex-row items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={handleRegenerateApiKey}
                  disabled={regeneratingApiKey}
                  className="w-full sm:w-auto py-2.5 px-4 bg-gray-50 hover:bg-gray-100 border border-gray-300/80 text-gray-700 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  {regeneratingApiKey ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                  <span>Regenerate API Key</span>
                </button>

                <span className="text-[11px] text-gray-400">Prefix: rec_live_</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ──────────────────────────────────────────────────────────── */}
      {/* TAB 3: DETERMINISTIC SAFETY GUARDRAILS */}
      {/* ──────────────────────────────────────────────────────────── */}
      {activeTab === 'guardrails' && (
        <div className="space-y-6">
          <div className="bg-white rounded-3xl border border-gray-100 shadow-sm p-6 sm:p-8 space-y-6">
            <div className="pb-4 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <h3 className="font-extrabold text-gray-900 text-lg">Deterministic Safety Guardrails (Rules R1 – R7)</h3>
                <span className="px-2.5 py-0.5 rounded-md text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  Hard Rule Boundaries
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Configure hard threshold ceilings that override AI recommendations to prevent infinite loops, customer spam, or excessive autonomous charges.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Max Autonomous Amount */}
              <div className="bg-gray-50/60 p-5 rounded-2xl border border-gray-200/80 space-y-3">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-bold text-gray-800 uppercase tracking-wider">
                    Max Autonomous Amount (₹)
                  </label>
                  <span className="text-[11px] font-mono font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
                    Rule R2
                  </span>
                </div>
                <div className="relative">
                  <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500 font-bold text-sm">₹</span>
                  <input
                    type="number"
                    value={settings.max_autonomous_amount}
                    onChange={(e) => setSettings({ ...settings, max_autonomous_amount: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-white border border-gray-200 rounded-xl pl-8 pr-3.5 py-2.5 text-sm font-bold text-gray-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
                  />
                </div>
                <p className="text-[11px] text-gray-500 leading-relaxed">
                  Payments exceeding <span className="font-bold text-gray-700">₹{settings.max_autonomous_amount?.toLocaleString('en-IN')}</span> are automatically blocked from automated retries and redirected to the Human Escalation Review Queue.
                </p>
              </div>

              {/* Max Retry Attempts */}
              <div className="bg-gray-50/60 p-5 rounded-2xl border border-gray-200/80 space-y-3">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-bold text-gray-800 uppercase tracking-wider">
                    Max Retry Attempts
                  </label>
                  <span className="text-[11px] font-mono font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
                    Rule R4
                  </span>
                </div>
                <input
                  type="number"
                  min={1}
                  max={5}
                  value={settings.max_retry_attempts}
                  onChange={(e) => setSettings({ ...settings, max_retry_attempts: parseInt(e.target.value) || 1 })}
                  className="w-full bg-white border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm font-bold text-gray-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
                />
                <p className="text-[11px] text-gray-500 leading-relaxed">
                  Stops automated recovery when a single payment has been attempted <span className="font-bold text-gray-700">{settings.max_retry_attempts} times</span> to prevent issuer penalization.
                </p>
              </div>

              {/* Retry Cooldown Window */}
              <div className="bg-gray-50/60 p-5 rounded-2xl border border-gray-200/80 space-y-3">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-bold text-gray-800 uppercase tracking-wider">
                    Cooldown Window (Hours)
                  </label>
                  <span className="text-[11px] font-mono font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
                    Rule R5
                  </span>
                </div>
                <input
                  type="number"
                  min={1}
                  max={48}
                  value={settings.retry_cooldown_hours}
                  onChange={(e) => setSettings({ ...settings, retry_cooldown_hours: parseFloat(e.target.value) || 1 })}
                  className="w-full bg-white border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm font-bold text-gray-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
                />
                <p className="text-[11px] text-gray-500 leading-relaxed">
                  Enforces a minimum interval of <span className="font-bold text-gray-700">{settings.retry_cooldown_hours} hours</span> between autonomous retries on transient bank failures.
                </p>
              </div>
            </div>

            {/* Guardrail Rules Overview */}
            <div className="pt-4 border-t border-gray-100">
              <h4 className="text-xs font-bold text-gray-800 uppercase tracking-wider mb-3">Active Deterministic Safety Rules</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
                <div className="p-3 bg-gray-50 rounded-xl border border-gray-200/70">
                  <span className="font-bold text-gray-900 block">R1: Duplicate Check</span>
                  <span className="text-gray-500 text-[11px]">Blocks actions on already settled transactions.</span>
                </div>
                <div className="p-3 bg-gray-50 rounded-xl border border-gray-200/70">
                  <span className="font-bold text-gray-900 block">R3: Card Expired Shield</span>
                  <span className="text-gray-500 text-[11px]">Forces payment link with UPI/NetBanking.</span>
                </div>
                <div className="p-3 bg-gray-50 rounded-xl border border-gray-200/70">
                  <span className="font-bold text-gray-900 block">R6: Contact Ceiling</span>
                  <span className="text-gray-500 text-[11px]">Ceases outreach after 2 customer messages.</span>
                </div>
                <div className="p-3 bg-gray-50 rounded-xl border border-gray-200/70">
                  <span className="font-bold text-gray-900 block">R7: Fraud Tripwire</span>
                  <span className="text-gray-500 text-[11px]">Escalates suspicious telemetry to human queue.</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ──────────────────────────────────────────────────────────── */}
      {/* TAB 4: CHANNELS */}
      {/* ──────────────────────────────────────────────────────────── */}
      {activeTab === 'channels' && (
        <div className="space-y-6">
          <div className="bg-white rounded-3xl border border-gray-100 shadow-sm p-6 sm:p-8 space-y-6">
            <div className="pb-4 border-b border-gray-100">
              <h3 className="font-extrabold text-gray-900 text-lg">Customer Outreach Channels</h3>
              <p className="text-xs text-gray-500 mt-1">
                Select which communication avenues RecoverAI can utilize to dispatch payment links and recovery prompts.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              {/* SMS */}
              <div className={`p-5 rounded-2xl border transition-all ${settings.enable_sms ? 'bg-indigo-50/40 border-indigo-200' : 'bg-gray-50/60 border-gray-200'}`}>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-indigo-600 text-white">
                      <Smartphone className="h-5 w-5" />
                    </div>
                    <div>
                      <span className="font-bold text-sm text-gray-900 block">SMS Gateway</span>
                      <span className="text-xs text-indigo-700 font-semibold">Razorpay Native SMS</span>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={settings.enable_sms}
                    onChange={(e) => setSettings({ ...settings, enable_sms: e.target.checked })}
                    className="h-5 w-5 text-indigo-600 rounded-lg cursor-pointer"
                  />
                </div>
                <p className="text-xs text-gray-500 mt-3">
                  Delivers direct payment links via instant SMS with instant carrier delivery.
                </p>
              </div>

              {/* Email */}
              <div className={`p-5 rounded-2xl border transition-all ${settings.enable_email ? 'bg-blue-50/40 border-blue-200' : 'bg-gray-50/60 border-gray-200'}`}>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-blue-600 text-white">
                      <Mail className="h-5 w-5" />
                    </div>
                    <div>
                      <span className="font-bold text-sm text-gray-900 block">Email Invoicing</span>
                      <span className="text-xs text-blue-700 font-semibold">HTML Recovery Template</span>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={settings.enable_email}
                    onChange={(e) => setSettings({ ...settings, enable_email: e.target.checked })}
                    className="h-5 w-5 text-blue-600 rounded-lg cursor-pointer"
                  />
                </div>
                <p className="text-xs text-gray-500 mt-3">
                  Dispatches itemized payment links with invoice breakdown to customer's registered email.
                </p>
              </div>

              {/* WhatsApp */}
              <div className={`p-5 rounded-2xl border transition-all ${settings.enable_whatsapp ? 'bg-emerald-50/40 border-emerald-200' : 'bg-gray-50/60 border-gray-200'}`}>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-emerald-600 text-white">
                      <MessageSquare className="h-5 w-5" />
                    </div>
                    <div>
                      <span className="font-bold text-sm text-gray-900 block">WhatsApp Business</span>
                      <span className="text-xs text-emerald-700 font-semibold">Interactive Buttons</span>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={settings.enable_whatsapp}
                    onChange={(e) => setSettings({ ...settings, enable_whatsapp: e.target.checked })}
                    className="h-5 w-5 text-emerald-600 rounded-lg cursor-pointer"
                  />
                </div>
                <p className="text-xs text-gray-500 mt-3">
                  Direct conversational WhatsApp recovery links (Requires Meta Business Cloud credentials).
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ──────────────────────────────────────────────────────────── */}
      {/* TAB 5: BRAND & MESSAGES */}
      {/* ──────────────────────────────────────────────────────────── */}
      {activeTab === 'brand' && (
        <div className="space-y-6">
          <div className="bg-white rounded-3xl border border-gray-100 shadow-sm p-6 sm:p-8 space-y-6">
            <div className="pb-4 border-b border-gray-100">
              <h3 className="font-extrabold text-gray-900 text-lg">Store Brand &amp; Customer Messaging</h3>
              <p className="text-xs text-gray-500 mt-1">
                Customize your merchant identity and recovery prompt template delivered to shoppers.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider">
                  Store / Brand Name
                </label>
                <input
                  type="text"
                  value={settings.brand_name}
                  onChange={(e) => setSettings({ ...settings, brand_name: e.target.value })}
                  placeholder="e.g. Acme Fashion Direct"
                  className="w-full bg-gray-50/70 border border-gray-200 rounded-2xl px-4 py-3 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 font-medium"
                />
              </div>

              <div className="space-y-2">
                <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider">
                  Support Email Address
                </label>
                <input
                  type="email"
                  value={settings.support_email}
                  onChange={(e) => setSettings({ ...settings, support_email: e.target.value })}
                  placeholder="support@merchant.com"
                  className="w-full bg-gray-50/70 border border-gray-200 rounded-2xl px-4 py-3 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 font-medium"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider">
                SMS / WhatsApp Recovery Message Template
              </label>
              <textarea
                rows={3}
                value={settings.message_template}
                onChange={(e) => setSettings({ ...settings, message_template: e.target.value })}
                className="w-full bg-gray-50/70 border border-gray-200 rounded-2xl p-4 text-sm font-mono text-gray-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
              />
              <div className="flex flex-wrap gap-2 items-center text-xs text-gray-500 pt-1">
                <span className="font-semibold text-gray-700">Available Variables:</span>
                <code className="bg-gray-100 text-indigo-700 px-2 py-0.5 rounded font-mono text-[11px] font-bold">{`{{customer_name}}`}</code>
                <code className="bg-gray-100 text-indigo-700 px-2 py-0.5 rounded font-mono text-[11px] font-bold">{`{{amount}}`}</code>
                <code className="bg-gray-100 text-indigo-700 px-2 py-0.5 rounded font-mono text-[11px] font-bold">{`{{payment_link}}`}</code>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ──────────────────────────────────────────────────────────── */}
      {/* TAB 6: PROFILE & WORKSPACE IDENTITY */}
      {/* ──────────────────────────────────────────────────────────── */}
      {activeTab === 'profile' && (
        <div className="space-y-6">
          <div className="bg-gradient-to-r from-indigo-900 via-indigo-800 to-indigo-700 text-white rounded-3xl p-6 sm:p-8 shadow-md flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Database className="h-5 w-5 text-indigo-300" />
                <h3 className="text-base font-bold tracking-tight">Isolated Tenant Profile Active</h3>
              </div>
              <p className="text-xs text-indigo-200 max-w-xl">
                All recovery cases, payment records, customer LTV context, and audit logs belong strictly to tenant <code className="bg-indigo-950 px-2 py-0.5 rounded text-white font-mono">{user?.user_id}</code>.
              </p>
            </div>
            <div className="flex items-center gap-2 bg-indigo-800/90 px-4 py-2 rounded-2xl border border-indigo-400/30 text-xs font-bold shrink-0">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span>Multi-Tenant Vault Active</span>
            </div>
          </div>

          <div className="bg-white rounded-3xl border border-gray-100 shadow-sm p-6 sm:p-8 space-y-6">
            <div className="pb-4 border-b border-gray-100">
              <h3 className="font-extrabold text-gray-900 text-lg">Merchant Account &amp; Organization Details</h3>
              <p className="text-xs text-gray-500 mt-0.5">
                Update your account credentials, workspace identity, and password.
              </p>
            </div>

            {profileError && (
              <div className="p-3.5 bg-red-50 border border-red-200 rounded-2xl text-xs text-red-800 font-semibold">
                {profileError}
              </div>
            )}

            {profileSuccess && (
              <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-2xl text-xs text-emerald-800 font-semibold flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                <span>Profile updated successfully!</span>
              </div>
            )}

            <form onSubmit={handleProfileUpdate} className="space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div className="space-y-2">
                  <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Full Name
                  </label>
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. Rahul Sharma"
                    className="w-full bg-gray-50/70 border border-gray-200 rounded-2xl px-4 py-3 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 font-medium"
                  />
                </div>

                <div className="space-y-2">
                  <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Organization / Brand Name
                  </label>
                  <input
                    type="text"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder="e.g. Acme Retail D2C"
                    className="w-full bg-gray-50/70 border border-gray-200 rounded-2xl px-4 py-3 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 font-medium"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div className="space-y-2">
                  <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Work Email (Read-Only)
                  </label>
                  <input
                    type="email"
                    disabled
                    value={user?.email || 'merchant@recoverai.io'}
                    className="w-full bg-gray-100 border border-gray-200 rounded-2xl px-4 py-3 text-sm text-gray-500 cursor-not-allowed font-medium"
                  />
                </div>

                <div className="space-y-2">
                  <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Role &amp; Permissions
                  </label>
                  <input
                    type="text"
                    disabled
                    value={(user?.role || 'OWNER').toUpperCase()}
                    className="w-full bg-gray-100 border border-gray-200 rounded-2xl px-4 py-3 text-sm text-gray-500 cursor-not-allowed font-bold"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Change Password (Optional)
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="flex items-center gap-1 text-[11px] font-bold text-gray-500 hover:text-gray-800 transition-colors"
                  >
                    {showPassword ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                    <span>{showPassword ? 'Hide' : 'Reveal'}</span>
                  </button>
                </div>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Leave blank to keep current password"
                    className="w-full bg-gray-50/70 border border-gray-200 rounded-2xl px-4 py-3 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 pr-12"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-200/60 transition-all"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={profileSaving}
                  className="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-2xl text-xs font-bold transition-all shadow-md shadow-indigo-100 cursor-pointer"
                >
                  {profileSaving ? 'Saving Profile...' : 'Update Profile Details'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

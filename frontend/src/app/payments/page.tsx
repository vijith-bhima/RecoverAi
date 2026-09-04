'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  Search,
  Filter,
  MoreHorizontal,
  CreditCard,
  CheckCircle2,
  XCircle,
  Clock,
  Banknote,
  ChevronDown,
  MoreVertical,
  Copy,
  Check,
  Zap
} from 'lucide-react';

import { useEffect } from 'react';
import { useAuth } from '@/lib/auth-context';
import PaymentDetailModal from '@/components/PaymentDetailModal';

export default function Payments() {
  const { user, apiFetch } = useAuth();
  const [payments, setPayments] = React.useState<any[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [searchQuery, setSearchQuery] = React.useState('');
  const [statusFilter, setStatusFilter] = React.useState('All Status');
  const [methodFilter, setMethodFilter] = React.useState('All Methods');
  const [currentPage, setCurrentPage] = React.useState(1);
  const [selectedPayment, setSelectedPayment] = React.useState<any>(null);
  const PAGE_SIZE = 10;
  
  useEffect(() => {
    const loadPayments = () => {
      setLoading(true);
      apiFetch('/payments')
        .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
        .then(data => { setPayments(Array.isArray(data) ? data : []); setLoading(false); })
        .catch(() => { setPayments([]); setLoading(false); });
    };
    loadPayments();
  }, [user, apiFetch]);

  // Calculate KPIs from all payments
  const totalPayments = payments.length;
  const successful = payments.filter((p: any) => p.status === 'SUCCESS' || p.status === 'RECOVERED').length;
  const failed = payments.filter((p: any) => p.status === 'FAILED').length;
  const pending = payments.filter((p: any) => p.status === 'PENDING').length;
  const totalVolume = payments.reduce((acc: number, p: any) => acc + p.amount, 0);

  const successRate = totalPayments > 0 ? ((successful / totalPayments) * 100).toFixed(1) : "0.0";
  const failureRate = totalPayments > 0 ? ((failed / totalPayments) * 100).toFixed(1) : "0.0";
  const pendingRate = totalPayments > 0 ? ((pending / totalPayments) * 100).toFixed(1) : "0.0";

  const volumeDisplay = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(totalVolume);

  // Dynamic payment method distribution
  const methodCounts: Record<string, number> = {};
  payments.forEach((p: any) => {
    const m = p.payment_method || 'OTHER';
    methodCounts[m] = (methodCounts[m] || 0) + 1;
  });
  const methodEntries = Object.entries(methodCounts).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const methodTotal = methodEntries.reduce((acc, [, cnt]) => acc + cnt, 0) || 1;
  const methodColors: Record<string, string> = {
    UPI: 'bg-emerald-500', CREDIT_CARD: 'bg-blue-500', DEBIT_CARD: 'bg-indigo-500',
    NET_BANKING: 'bg-orange-500', WALLET: 'bg-purple-500', CHECKOUT_CART: 'bg-gray-400',
  };

  // Filter payments by search, status, and method
  const filtered = payments.filter((p: any) => {
    const q = searchQuery.toLowerCase();
    const matchSearch = !q
      || p.payment_id?.toLowerCase().includes(q)
      || p.customer_id?.toLowerCase().includes(q)
      || p.failure_reason?.toLowerCase().includes(q)
      || p.payment_method?.toLowerCase().includes(q);
    const matchStatus = statusFilter === 'All Status' || p.status === statusFilter.toUpperCase();
    const matchMethod = methodFilter === 'All Methods' || p.payment_method === methodFilter.toUpperCase().replace(' ', '_');
    return matchSearch && matchStatus && matchMethod;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const paginated = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  const handleSearch = (q: string) => { setSearchQuery(q); setCurrentPage(1); };
  const handleStatusFilter = (v: string) => { setStatusFilter(v); setCurrentPage(1); };
  const handleMethodFilter = (v: string) => { setMethodFilter(v); setCurrentPage(1); };

  return (
    <div className="max-w-[1400px] mx-auto space-y-6 pt-2">
      
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-2">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 tracking-tight">Payments</h1>
          <p className="text-sm text-gray-500 mt-1">Overview of all transactions and their current status.</p>
        </div>
      </div>

      {/* Top KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-6 mb-6 sm:mb-8">
         <div className="bg-white p-4 sm:p-6 rounded-2xl border border-gray-100 shadow-sm">
           <div className="flex items-center gap-2 mb-2">
             <div className="h-8 w-8 bg-indigo-50 text-indigo-600 rounded-full flex items-center justify-center">
               <Banknote className="h-4 w-4" />
             </div>
             <span className="text-[11px] sm:text-[13px] font-semibold text-gray-500 uppercase tracking-wider">Total Volume</span>
           </div>
           <div className="text-xl sm:text-3xl font-extrabold text-gray-900 truncate">{volumeDisplay}</div>
         </div>
         
         <div className="bg-white p-4 sm:p-6 rounded-2xl border border-gray-100 shadow-sm">
           <div className="flex items-center gap-2 mb-2">
             <div className="h-8 w-8 bg-emerald-50 text-emerald-600 rounded-full flex items-center justify-center">
               <CheckCircle2 className="h-4 w-4" />
             </div>
             <span className="text-[11px] sm:text-[13px] font-semibold text-gray-500 uppercase tracking-wider">Success</span>
           </div>
           <div className="text-xl sm:text-3xl font-extrabold text-gray-900">{successRate}%</div>
           <div className="text-xs sm:text-sm font-semibold text-emerald-600 mt-1">{successful.toLocaleString()} transactions</div>
         </div>

         <div className="bg-white p-4 sm:p-6 rounded-2xl border border-gray-100 shadow-sm">
           <div className="flex items-center gap-2 mb-2">
             <div className="h-8 w-8 bg-red-50 text-red-600 rounded-full flex items-center justify-center">
               <XCircle className="h-4 w-4" />
             </div>
             <span className="text-[11px] sm:text-[13px] font-semibold text-gray-500 uppercase tracking-wider">Failed</span>
           </div>
           <div className="text-xl sm:text-3xl font-extrabold text-gray-900">{failureRate}%</div>
           <div className="text-xs sm:text-sm font-semibold text-red-600 mt-1">{failed.toLocaleString()} transactions</div>
         </div>

         <div className="bg-white p-4 sm:p-6 rounded-2xl border border-gray-100 shadow-sm">
           <div className="flex items-center gap-2 mb-2">
             <div className="h-8 w-8 bg-amber-50 text-amber-600 rounded-full flex items-center justify-center">
               <Clock className="h-4 w-4" />
             </div>
             <span className="text-[11px] sm:text-[13px] font-semibold text-gray-500 uppercase tracking-wider">Pending</span>
           </div>
           <div className="text-xl sm:text-3xl font-extrabold text-gray-900">{pendingRate}%</div>
           <div className="text-xs sm:text-sm font-semibold text-amber-600 mt-1">{pending.toLocaleString()} transactions</div>
         </div>
      </div>

      {/* Main layout — stacks on mobile */}
      <div className="flex flex-col xl:flex-row gap-6 items-start">
        
        {/* Main Table Area (Left Column) */}
        <div className="flex-1 bg-white rounded-[24px] border border-gray-100 shadow-sm overflow-hidden">
          
          {/* Filters Bar (Dark) */}
          <div className="p-4 bg-[#1B252E] flex flex-wrap gap-4 items-center justify-between m-2 rounded-2xl">
            <div className="flex items-center gap-3 flex-1 min-w-[200px]">
              <div className="relative w-full">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input 
                  type="text" 
                  placeholder="Search by Payment ID, Customer, Order ID..." 
                  value={searchQuery}
                  onChange={e => handleSearch(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 bg-[#25313D] border-none rounded-xl text-sm text-white outline-none focus:ring-2 focus:ring-emerald-500/50 transition-all placeholder:text-gray-400 font-medium"
                />
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <select
                value={statusFilter}
                onChange={e => handleStatusFilter(e.target.value)}
                className="bg-[#25313D] border border-[#344252] text-white text-sm font-semibold rounded-xl px-3 py-2 outline-none cursor-pointer"
              >
                {['All Status','FAILED','RECOVERED','PENDING','SUCCESS'].map(s => (
                  <option key={s} value={s}>{s.replace('_',' ')}</option>
                ))}
              </select>
              <select
                value={methodFilter}
                onChange={e => handleMethodFilter(e.target.value)}
                className="bg-[#25313D] border border-[#344252] text-white text-sm font-semibold rounded-xl px-3 py-2 outline-none cursor-pointer"
              >
                {['All Methods','UPI','CREDIT_CARD','DEBIT_CARD','NET_BANKING','WALLET'].map(m => (
                  <option key={m} value={m}>{m.replace('_',' ')}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-gray-100 bg-white">
                  <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider">Payment ID</th>
                  <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider">Customer</th>
                  <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider">Amount</th>
                  <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider text-center">Method</th>
                  <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider">Status</th>
                  <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider">Failure Reason</th>
                  <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider">Date & Time</th>
                  <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider text-center">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {loading ? (
                  <tr><td colSpan={8} className="px-6 py-12 text-center text-gray-400 text-sm">Loading payments…</td></tr>
                ) : paginated.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-6 py-12 text-center text-gray-500 text-sm">
                      {searchQuery || statusFilter !== 'All Status' || methodFilter !== 'All Methods'
                        ? 'No payments match your filters.'
                        : 'No payment transactions found. Live webhook events from Razorpay will appear here in real-time.'}
                    </td>
                  </tr>
                ) : (
                  paginated.map((payment: any) => {
                    const displayDate = new Date(payment.timestamp).toLocaleString('en-IN', {
                      month: 'short', day: 'numeric', year: 'numeric'
                    });
                    const displayTime = new Date(payment.timestamp).toLocaleString('en-IN', {
                      hour: '2-digit', minute: '2-digit', second: '2-digit'
                    });
                    const displayAmount = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(payment.amount);
                    const customerDisplay = payment.customer_id || 'Unknown';
                    return (
                      <TableRow 
                        key={payment.payment_id}
                        paymentId={payment.payment_id}
                        orderId={`ORD-${payment.customer_id?.slice(-4) ?? '???'}`}
                        customerName={`Customer ${customerDisplay.slice(-4)}`}
                        customerSubtitle={customerDisplay}
                        amount={displayAmount}
                        methodType={payment.payment_method}
                        methodLast4="***"
                        status={payment.status.charAt(0).toUpperCase() + payment.status.slice(1).toLowerCase()}
                        reason={payment.failure_reason}
                        date={displayDate}
                        time={displayTime}
                        onViewDetail={() => setSelectedPayment(payment)}
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
              Showing {filtered.length === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1} to {Math.min(currentPage * PAGE_SIZE, filtered.length)} of {filtered.length.toLocaleString()} payments
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="h-8 w-8 rounded-lg border border-gray-200 flex items-center justify-center text-gray-500 hover:bg-gray-50 disabled:opacity-40"
              >
                &lt;
              </button>
              {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => i + 1).map(pg => (
                <button
                  key={pg}
                  onClick={() => setCurrentPage(pg)}
                  className={`h-8 w-8 rounded-lg flex items-center justify-center font-semibold text-sm ${
                    pg === currentPage
                      ? 'bg-[#10B981] text-white shadow-sm shadow-emerald-200'
                      : 'border border-gray-200 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  {pg}
                </button>
              ))}
              <button
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="h-8 w-8 rounded-lg border border-gray-200 flex items-center justify-center text-gray-500 hover:bg-gray-50 disabled:opacity-40"
              >
                &gt;
              </button>
            </div>
          </div>
        </div>

        {/* Analytics Sidebar (Right Column) */}
        <div className="w-[340px] space-y-6 flex-shrink-0">
          
          {/* Status Distribution */}
          <div className="bg-white rounded-[24px] border border-gray-100 shadow-sm p-5">
             <div className="flex justify-between items-center mb-6">
                <h3 className="font-bold text-gray-900 text-sm">Payment Status Distribution</h3>
                <MoreVertical className="h-4 w-4 text-gray-400" />
             </div>
             <div className="flex items-center gap-6">
                <div className="relative w-32 h-32 flex-shrink-0">
                  {/* CSS Donut Chart */}
                  <svg viewBox="0 0 36 36" className="w-full h-full transform -rotate-90">
                    <path className="text-gray-100" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeWidth="4"/>
                    <path className="text-emerald-500" strokeDasharray={`${successRate}, 100`} d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeWidth="4"/>
                    <path className="text-red-500" strokeDasharray={`${failureRate}, 100`} strokeDashoffset={`-${successRate}`} d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeWidth="4"/>
                    <path className="text-orange-400" strokeDasharray={`${pendingRate}, 100`} strokeDashoffset={`-${Number(successRate) + Number(failureRate)}`} d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeWidth="4"/>
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-xl font-bold text-gray-900">{totalPayments.toLocaleString()}</span>
                    <span className="text-[10px] text-gray-500 font-medium">Total</span>
                  </div>
                </div>

                <div className="space-y-4 flex-1">
                  <LegendItem color="bg-emerald-500" label="Success" count={successful.toLocaleString()} pct={`(${successRate}%)`} />
                  <LegendItem color="bg-red-500" label="Failed" count={failed.toLocaleString()} pct={`(${failureRate}%)`} />
                  <LegendItem color="bg-orange-400" label="Pending" count={pending.toLocaleString()} pct={`(${pendingRate}%)`} />
                </div>
             </div>
          </div>

          {/* Volume Over Time */}
          <div className="bg-white rounded-[24px] border border-gray-100 shadow-sm p-5">
             <div className="flex justify-between items-center mb-6">
                <h3 className="font-bold text-gray-900 text-sm">Payment Volume Over Time</h3>
                <div className="flex items-center gap-1 border border-gray-200 px-2 py-1 rounded text-[11px] font-semibold text-gray-600">
                  Daily <ChevronDown className="h-3 w-3" />
                </div>
             </div>
             
             {/* Mock Line Chart Area using SVG */}
             <div className="h-32 w-full relative">
               <div className="absolute left-0 top-0 bottom-0 w-8 flex flex-col justify-between text-[10px] text-gray-400 font-medium pb-5">
                 <span>₹40L</span>
                 <span>₹30L</span>
                 <span>₹20L</span>
                 <span>₹10L</span>
               </div>
               
               {/* Grid lines */}
               <div className="absolute left-8 right-0 top-1 h-[1px] bg-gray-100"></div>
               <div className="absolute left-8 right-0 top-[33%] h-[1px] bg-gray-100"></div>
               <div className="absolute left-8 right-0 top-[66%] h-[1px] bg-gray-100"></div>
               <div className="absolute left-8 right-0 bottom-5 h-[1px] bg-gray-100"></div>

               {/* Chart SVG */}
               <svg className="absolute left-8 right-0 top-1 bottom-5 w-[calc(100%-32px)] h-[calc(100%-20px)]" preserveAspectRatio="none" viewBox="0 0 100 100">
                 <defs>
                    <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#10B981" stopOpacity="0.3" />
                      <stop offset="100%" stopColor="#10B981" stopOpacity="0" />
                    </linearGradient>
                 </defs>
                 <path d="M0,80 L15,70 L25,90 L40,50 L55,80 L70,20 L85,60 L100,50 L100,100 L0,100 Z" fill="url(#chartGradient)" />
                 <path d="M0,80 L15,70 L25,90 L40,50 L55,80 L70,20 L85,60 L100,50" fill="none" stroke="#10B981" strokeWidth="2" vectorEffect="non-scaling-stroke" />
               </svg>

               <div className="absolute left-8 right-0 bottom-0 flex justify-between text-[10px] text-gray-400 font-medium pt-1">
                 <span>1 May</span>
                 <span>8 May</span>
                 <span>15 May</span>
                 <span>22 May</span>
                 <span>29 May</span>
               </div>
             </div>
          </div>

          {/* Top Payment Methods - dynamic */}
          <div className="bg-white rounded-[24px] border border-gray-100 shadow-sm p-5">
             <div className="flex justify-between items-center mb-6">
                <h3 className="font-bold text-gray-900 text-sm">Top Payment Methods</h3>
             </div>
             <div className="space-y-4">
               {methodEntries.length === 0 ? (
                 <p className="text-xs text-gray-400">No payment data yet.</p>
               ) : methodEntries.map(([method, cnt]) => {
                 const pct = ((cnt / methodTotal) * 100).toFixed(1);
                 const barWidth = `${Math.max(4, (cnt / methodTotal) * 100)}%`;
                 return (
                   <div key={method} className="space-y-1.5">
                     <div className="flex justify-between text-[11px] font-bold">
                       <span className="text-gray-700">{method.replace('_', ' ')}</span>
                       <span className="text-gray-900">{pct}%</span>
                     </div>
                     <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden">
                       <div
                         className={`h-full ${methodColors[method] || 'bg-gray-400'} rounded-full transition-all`}
                         style={{ width: barWidth }}
                       />
                     </div>
                   </div>
                 );
               })}
             </div>
          </div>

        </div>
      </div>
      
      <PaymentDetailModal
        payment={selectedPayment}
        isOpen={!!selectedPayment}
        onClose={() => setSelectedPayment(null)}
      />
    </div>
  );
}

// Subcomponents



function TableRow({ paymentId, orderId, customerName, customerSubtitle, amount, methodType, methodLast4, status, reason, date, time, onViewDetail }: any) {
  const [copied, setCopied] = React.useState(false);
  
  const copyId = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(paymentId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const statusConfig: any = {
    'Success': { icon: CheckCircle2, color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-100' },
    'Recovered': { icon: CheckCircle2, color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-100' },
    'Failed': { icon: XCircle, color: 'text-red-600', bg: 'bg-red-50 border-red-100' },
    'Pending': { icon: Clock, color: 'text-orange-600', bg: 'bg-orange-50 border-orange-100' },
  };

  const methodColors: any = {
    'VISA': 'text-blue-700 bg-blue-50',
    'MC': 'text-orange-600 bg-orange-50',
    'UPI': 'text-emerald-700 bg-emerald-50',
    'RuPay': 'text-indigo-700 bg-indigo-50'
  };

  const Conf = statusConfig[status] || statusConfig['Pending'];
  const StatusIcon = Conf.icon;

  return (
    <tr className="hover:bg-gray-50/50 transition-colors group cursor-pointer" onClick={onViewDetail}>
      <td className="px-6 py-4">
        <div className="flex items-center gap-1.5">
          <div className="font-bold text-[12px] font-mono text-gray-900">{paymentId}</div>
          <button onClick={copyId} className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 text-gray-400 hover:text-gray-700">
            {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
          </button>
        </div>
        <div className="text-[11px] font-semibold text-gray-400">{orderId}</div>
      </td>
      <td className="px-6 py-4">
        <div className="font-bold text-[13px] text-gray-900 mb-0.5">{customerName}</div>
        <div className="text-[11px] font-semibold text-gray-400">{customerSubtitle}</div>
      </td>
      <td className="px-6 py-4">
        <span className="font-bold text-[14px] text-gray-900">{amount}</span>
      </td>
      <td className="px-6 py-4 text-center">
        <div className="flex items-center justify-center gap-1.5">
          <span className={`text-[10px] font-extrabold px-1.5 py-0.5 rounded ${methodColors[methodType] || 'text-gray-700 bg-gray-50'}`}>{methodType}</span>
          <span className="text-[12px] font-semibold text-gray-600">•••• {methodLast4}</span>
        </div>
      </td>
      <td className="px-6 py-4">
        <div className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold border ${Conf.bg} ${Conf.color}`}>
          <StatusIcon className="h-3.5 w-3.5" />
          {status}
        </div>
      </td>
      <td className="px-6 py-4">
        <span className={`text-[13px] font-medium ${reason === '—' || !reason ? 'text-gray-300' : 'text-gray-600'}`}>{reason?.replace(/_/g, ' ') || '—'}</span>
      </td>
      <td className="px-6 py-4">
        <div className="text-[12px] font-semibold text-gray-700 mb-0.5">{date}</div>
        <div className="text-[11px] text-gray-400 font-medium">{time}</div>
      </td>
      <td className="px-6 py-4 text-center" onClick={e => e.stopPropagation()}>
        {status === 'Failed' ? (
          <Link
            href={`/recover?id=${paymentId}`}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-[11px] font-bold rounded-lg transition-colors shadow-sm"
          >
            <Zap className="h-3 w-3" />
            Recover
          </Link>
        ) : (
          <button onClick={onViewDetail} className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors">
            <MoreHorizontal className="h-4 w-4" />
          </button>
        )}
      </td>
    </tr>
  );
}

function LegendItem({ color, label, count, pct }: any) {
  return (
    <div className="flex items-start justify-between text-xs">
      <div className="flex items-center gap-2">
        <div className={`h-2.5 w-2.5 rounded-sm ${color}`}></div>
        <span className="font-semibold text-gray-700">{label}</span>
      </div>
      <div className="text-right">
        <div className="font-bold text-gray-900">{count}</div>
        <div className="text-[10px] text-gray-400">{pct}</div>
      </div>
    </div>
  );
}

function MethodProgress({ name, pct, color, width }: any) {
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-[11px] font-bold">
        <span className="text-gray-700">{name}</span>
        <span className="text-gray-900">{pct}</span>
      </div>
      <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} ${width} rounded-full`}></div>
      </div>
    </div>
  );
}

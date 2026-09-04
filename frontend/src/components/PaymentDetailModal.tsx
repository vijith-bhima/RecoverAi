'use client';

import React from 'react';
import { X, CheckCircle2, XCircle, Clock, Zap, ArrowRight, ShieldCheck } from 'lucide-react';
import Link from 'next/link';

interface PaymentDetailModalProps {
  payment: any;
  isOpen: boolean;
  onClose: () => void;
}

export default function PaymentDetailModal({ payment, isOpen, onClose }: PaymentDetailModalProps) {
  if (!isOpen || !payment) return null;

  const displayDate = new Date(payment.timestamp).toLocaleString('en-IN', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
  const displayAmount = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(payment.amount);

  const isFailed = payment.status === 'FAILED';
  const isRecovered = payment.status === 'SUCCESS' || payment.status === 'RECOVERED';
  
  const statusColors: any = {
    'SUCCESS': 'bg-emerald-50 text-emerald-700 border-emerald-200',
    'RECOVERED': 'bg-emerald-50 text-emerald-700 border-emerald-200',
    'FAILED': 'bg-red-50 text-red-700 border-red-200',
    'PENDING': 'bg-orange-50 text-orange-700 border-orange-200',
  };

  const statusColor = statusColors[payment.status] || statusColors['PENDING'];

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center sm:p-4 bg-gray-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div 
        className="bg-white rounded-t-3xl sm:rounded-3xl shadow-2xl border border-gray-100 w-full sm:max-w-2xl overflow-hidden transition-all transform animate-in slide-in-from-bottom sm:zoom-in-95 duration-200 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="relative px-8 pt-7 pb-5 border-b border-gray-100 bg-gradient-to-b from-gray-50/50 to-white">
          <button
            onClick={onClose}
            className="absolute top-6 right-6 p-2 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-full transition-colors"
          >
            <X className="h-5 w-5" />
          </button>

          <div className="flex items-start sm:items-center gap-3 sm:gap-4 mb-2">
            <div className={`h-10 w-10 sm:h-12 sm:w-12 shrink-0 rounded-2xl flex items-center justify-center border shadow-sm ${statusColor}`}>
              {isRecovered ? <CheckCircle2 className="h-5 w-5 sm:h-6 sm:w-6" /> : isFailed ? <XCircle className="h-5 w-5 sm:h-6 sm:w-6" /> : <Clock className="h-5 w-5 sm:h-6 sm:w-6" />}
            </div>
            <div className="min-w-0">
              <h2 className="text-lg sm:text-xl font-bold text-gray-900 tracking-tight truncate">Payment {payment.payment_id}</h2>
              <div className="flex flex-wrap items-center gap-2 mt-1">
                <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${statusColor}`}>
                  {payment.status}
                </span>
                <span className="text-xs sm:text-sm font-medium text-gray-500">{displayDate}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="p-5 sm:p-8 space-y-4 sm:space-y-6 bg-gray-50/30">
          
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
            <div className="space-y-4 bg-white p-5 rounded-2xl border border-gray-100 shadow-sm">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Transaction Details</h3>
              <div>
                <div className="text-[11px] font-semibold text-gray-500">Amount</div>
                <div className="text-lg font-bold text-gray-900">{displayAmount}</div>
              </div>
              <div>
                <div className="text-[11px] font-semibold text-gray-500">Payment Method</div>
                <div className="text-sm font-bold text-gray-900">{payment.payment_method?.replace('_', ' ') || 'Unknown'}</div>
              </div>
              {payment.failure_reason && (
                <div>
                  <div className="text-[11px] font-semibold text-gray-500">Failure Reason</div>
                  <div className="text-sm font-bold text-red-600 bg-red-50 p-2 rounded-lg mt-1 inline-block">
                    {payment.failure_reason.replace(/_/g, ' ')}
                  </div>
                </div>
              )}
            </div>

            <div className="space-y-4 bg-white p-5 rounded-2xl border border-gray-100 shadow-sm">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Customer Details</h3>
              <div>
                <div className="text-[11px] font-semibold text-gray-500">Customer ID</div>
                <div className="text-sm font-bold text-gray-900">{payment.customer_id}</div>
              </div>
              <div>
                <div className="text-[11px] font-semibold text-gray-500">Contact</div>
                <div className="text-sm font-medium text-gray-600">user{payment.customer_id?.slice(-4)}@example.com</div>
              </div>
            </div>
          </div>
          
          {/* Recovery Actions Area */}
          {isFailed && (
            <div className="bg-indigo-50 border border-indigo-100 rounded-2xl p-6 relative overflow-hidden">
              <div className="absolute -right-6 -top-6 h-32 w-32 bg-indigo-200 rounded-full blur-3xl opacity-50"></div>
              <div className="relative z-10 flex flex-col md:flex-row items-center justify-between gap-4">
                <div>
                  <h3 className="text-indigo-900 font-bold flex items-center gap-2">
                    <ShieldCheck className="h-5 w-5 text-indigo-600" />
                    Revenue Recovery Available
                  </h3>
                  <p className="text-indigo-700/80 text-sm mt-1">
                    This payment failed due to <span className="font-bold">{payment.failure_reason?.replace(/_/g, ' ') || 'a system error'}</span>. 
                    RecoverAI can attempt to recover this.
                  </p>
                </div>
                <Link
                  href={`/recover?id=${payment.payment_id}`}
                  className="shrink-0 flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-xl font-bold text-sm shadow-sm transition-all shadow-indigo-200"
                >
                  <Zap className="h-4 w-4" />
                  Start Recovery
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </div>
          )}

          {isRecovered && (
             <div className="bg-emerald-50 border border-emerald-100 rounded-2xl p-6">
                <h3 className="text-emerald-900 font-bold flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                  Successfully Processed
                </h3>
                <p className="text-emerald-700/80 text-sm mt-1">
                  This transaction has been completed and funds are secured.
                </p>
             </div>
          )}

        </div>
      </div>
    </div>
  );
}

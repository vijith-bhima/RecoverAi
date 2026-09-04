'use client';

import React, { useEffect, useState } from 'react';
import {
  Search,
  Filter,
  MoreHorizontal,
  Users,
  UserCheck,
  ChevronDown,
  Loader2,
} from 'lucide-react';
import { useAuth } from '@/lib/auth-context';

export default function Customers() {
  const { user, apiFetch } = useAuth();
  const [customers, setCustomers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadCustomers = async () => {
      setLoading(true);
      try {
        const res = await apiFetch('/customers');
        if (res.ok) {
          const data = await res.json();
          setCustomers(Array.isArray(data) ? data : []);
        } else {
          setCustomers([]);
        }
      } catch (err) {
        console.error("Failed to fetch customers", err);
        setCustomers([]);
      } finally {
        setLoading(false);
      }
    };
    loadCustomers();
  }, [user, apiFetch]);

  const totalCustomers = customers.length;
  const activeCustomers = customers.filter((c: any) => c.successful_payments > 0).length;

  return (
    <div className="max-w-[1400px] mx-auto space-y-6 pt-2">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-2">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 tracking-tight">Customers</h1>
          <p className="text-sm text-gray-500 mt-1">Manage and view your customer base.</p>
        </div>
      </div>

      {/* Top KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-8">
        <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <div className="h-8 w-8 bg-indigo-50 text-indigo-600 rounded-full flex items-center justify-center">
              <Users className="h-4 w-4" />
            </div>
            <span className="text-[13px] font-semibold text-gray-500 uppercase tracking-wider">Total Customers</span>
          </div>
          <div className="text-3xl font-extrabold text-gray-900">
            {loading ? <Loader2 className="h-7 w-7 animate-spin text-indigo-400" /> : totalCustomers.toLocaleString()}
          </div>
          <div className="text-sm font-semibold text-indigo-600 mt-1">All Time</div>
        </div>
        
        <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <div className="h-8 w-8 bg-emerald-50 text-emerald-600 rounded-full flex items-center justify-center">
              <UserCheck className="h-4 w-4" />
            </div>
            <span className="text-[13px] font-semibold text-gray-500 uppercase tracking-wider">Active Customers</span>
          </div>
          <div className="text-3xl font-extrabold text-gray-900">
            {loading ? <Loader2 className="h-7 w-7 animate-spin text-emerald-400" /> : activeCustomers.toLocaleString()}
          </div>
          <div className="text-sm font-semibold text-emerald-600 mt-1">
            {totalCustomers > 0 ? ((activeCustomers / totalCustomers) * 100).toFixed(1) : 0}% of total
          </div>
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
                placeholder="Search customers..." 
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
                <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider">Customer</th>
                <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider">Customer ID</th>
                <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider text-right">Total Payments</th>
                <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider text-right">Successful</th>
                <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider text-right">Failed</th>
                <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider text-center">Status</th>
                <th className="px-6 py-4 font-semibold text-gray-900 text-xs uppercase tracking-wider text-center">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-400 text-sm">
                    <Loader2 className="h-6 w-6 animate-spin mx-auto text-indigo-500 mb-2" />
                    Loading customer records...
                  </td>
                </tr>
              ) : customers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-500 text-sm">
                    No customer records in this workspace yet. Transactions and customer profiles will appear here automatically when payments are processed.
                  </td>
                </tr>
              ) : (
                customers.slice(0, 50).map((customer: any) => {
                  const nameDisplay = customer.email ? customer.email.split('@')[0] : customer.phone || ("Customer " + customer.customer_id.slice(-4));
                  const emailDisplay = customer.email || customer.phone || "—";
                  const avatarDisplay = (customer.email ? customer.email[0] : customer.customer_id.slice(-2)).toUpperCase();
                  return (
                    <TableRow 
                      key={customer.customer_id}
                      name={nameDisplay}
                      email={emailDisplay}
                      initials={avatarDisplay}
                      customerId={customer.customer_id}
                      totalPayments={customer.total_payments}
                      successful={customer.successful_payments}
                      failed={customer.failed_payments}
                      status={customer.successful_payments > 0 ? "Active" : "Inactive"}
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
            Showing 1 to {Math.min(50, totalCustomers)} of {totalCustomers.toLocaleString()} customers
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

function TableRow({ name, email, initials, customerId, totalPayments, successful, failed, status }: any) {
  return (
    <tr className="hover:bg-gray-50/50 transition-colors group">
      <td className="px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 bg-indigo-50 text-indigo-700 rounded-full flex items-center justify-center font-bold text-xs">
            {initials}
          </div>
          <div>
            <div className="font-bold text-[13px] text-gray-900">{name}</div>
            <div className="text-[11px] font-semibold text-gray-400">{email}</div>
          </div>
        </div>
      </td>
      <td className="px-6 py-4">
        <div className="font-mono text-[13px] font-semibold text-gray-500">{customerId}</div>
      </td>
      <td className="px-6 py-4 text-right">
        <div className="font-bold text-[14px] text-gray-900">{totalPayments}</div>
      </td>
      <td className="px-6 py-4 text-right">
        <div className="font-bold text-[14px] text-emerald-600">{successful}</div>
      </td>
      <td className="px-6 py-4 text-right">
        <div className="font-bold text-[14px] text-red-600">{failed}</div>
      </td>
      <td className="px-6 py-4 text-center">
        <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider border ${status === 'Active' ? 'bg-emerald-50 text-emerald-700 border-emerald-100' : 'bg-gray-50 text-gray-600 border-gray-200'}`}>
          {status}
        </span>
      </td>
      <td className="px-6 py-4 text-center">
        <button className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors">
          <MoreHorizontal className="h-4 w-4" />
        </button>
      </td>
    </tr>
  );
}

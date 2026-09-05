'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  Bell,
  CheckCircle2,
  AlertCircle,
  ShieldCheck,
  Search,
  Eye,
  RefreshCw,
  Home,
  Briefcase,
  List,
  Users,
  CreditCard,
  BarChart2,
  Brain,
  Settings,
  ChevronDown,
  Menu,
  Zap,
  Building,
  UserCheck,
  LogOut,
  Sparkles,
  Moon,
  Sun,
  BookOpen,
} from 'lucide-react';
import { useAuth } from '../lib/auth-context';
import AuthModal from './AuthModal';

const Avatar = ({ className, children }: any) => <div className={`relative flex shrink-0 overflow-hidden rounded-full items-center justify-center ${className || ''}`}>{children}</div>;
const AvatarFallback = ({ className, children }: any) => <span className={`flex h-full w-full items-center justify-center rounded-full ${className || ''}`}>{children}</span>;

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalTab, setAuthModalTab] = useState<'login' | 'register'>('login');
  const [darkMode, setDarkMode] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout, isLoading } = useAuth();

  useEffect(() => {
    const saved = localStorage.getItem('recoverai_theme') === 'dark';
    setDarkMode(saved);
    document.documentElement.classList.toggle('dark', saved);
  }, []);

  const toggleTheme = () => {
    setDarkMode(current => {
      const next = !current;
      localStorage.setItem('recoverai_theme', next ? 'dark' : 'light');
      document.documentElement.classList.toggle('dark', next);
      return next;
    });
  };

  useEffect(() => {
    const isPublicAuthPage = pathname === '/login' || pathname === '/forgot-password' || pathname === '/reset-password';
    if (!isLoading && !user && !isPublicAuthPage) {
      router.replace('/login');
    }
  }, [isLoading, pathname, router, user]);

  // Close mobile sidebar on route change
  useEffect(() => {
    setIsMobileSidebarOpen(false);
  }, [pathname]);

  // Handle body scroll lock
  useEffect(() => {
    if (isMobileSidebarOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isMobileSidebarOpen]);

  // Handle escape key to close mobile sidebar
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsMobileSidebarOpen(false);
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, []);

  // Auth recovery pages must remain public so logged-out users can reach them.
  if (pathname === '/login' || pathname === '/forgot-password' || pathname === '/reset-password') return <>{children}</>;
  if (isLoading || !user) return null;

  const initials = user?.full_name
    ? user.full_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .substring(0, 2)
    : 'RK';

  // Helper for NavItems
  const NavItem = ({ icon: Icon, label, href, badge, accent }: any) => {
    const active = pathname === href;
    
    return (
      <Link 
        href={href}
        onClick={() => setIsMobileSidebarOpen(false)}
        className={`group flex items-center ${isSidebarOpen ? 'gap-3 px-4' : 'justify-center lg:justify-center px-4 lg:px-0'} py-[14px] rounded-2xl font-semibold transition-all duration-200 ${
          active && accent
            ? 'bg-indigo-600 text-white'
            : active 
            ? 'bg-[#EEF3EA] text-[#2C5338]' 
            : accent
            ? 'text-indigo-600 hover:bg-indigo-50 border border-indigo-100'
            : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900'
        }`}
        title={label}
      >
        <div className="relative">
          <Icon className={`h-5 w-5 shrink-0 ${active ? 'text-[#3E744F]' : 'text-gray-400 group-hover:text-gray-600 transition-colors'}`} />
          {!isSidebarOpen && badge && (
            <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5 items-center justify-center rounded-full bg-indigo-500 border-2 border-white"></span>
          )}
        </div>
        
        <span className={`transition-all duration-300 text-[14px] tracking-wide whitespace-nowrap overflow-hidden ${
          isSidebarOpen ? 'w-full opacity-100' : 'w-0 opacity-0'
        }`}>
          <div className="flex items-center justify-between w-full">
            {label}
            {badge && (
              <span className="flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-indigo-500 text-[10px] font-bold text-white px-1">
                {badge}
              </span>
            )}
          </div>
        </span>
      </Link>
    );
  };

  // Build the page title based on the route
  const getPageTitle = () => {
    if (pathname === '/') return 'Overview';
    if (pathname === '/recovery-cases') return 'Recovery Cases';
    if (pathname === '/audit-trail') return 'Audit Trail';
    if (pathname === '/ghost-revenue') return 'Ghost Revenue Hunter';
    if (pathname === '/guide') return 'Getting Started';
    return pathname.substring(1);
  };

  return (
    <div className="flex h-screen bg-[#F7F8FB] font-sans text-gray-900 overflow-hidden selection:bg-indigo-100 relative w-full">
      
      {/* Mobile Overlay */}
      <div 
        className={`fixed inset-0 bg-gray-900/40 backdrop-blur-sm z-30 transition-opacity duration-300 lg:hidden ${isMobileSidebarOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
        onClick={() => setIsMobileSidebarOpen(false)}
      />

      {/* Sidebar */}
      <aside 
        className={`
          fixed lg:static inset-y-0 left-0 z-40 flex flex-col justify-between bg-white border-r border-gray-100 flex-shrink-0 transition-transform duration-300 ease-in-out shadow-xl lg:shadow-sm
          ${isSidebarOpen ? 'w-[280px] lg:w-[260px]' : 'w-[280px] lg:w-[88px]'}
          ${isMobileSidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        <div className="flex flex-col h-full overflow-hidden">
          {/* Logo Area */}
          <div className="flex items-center justify-between h-[80px] px-6 border-b border-gray-50/50 shrink-0">
            <div className={`flex items-center gap-3 overflow-hidden ${(!isSidebarOpen && !isMobileSidebarOpen) ? 'lg:w-0 lg:opacity-0' : 'w-auto opacity-100'} transition-all duration-300`}>
              <ShieldCheck className="h-7 w-7 text-indigo-600 shrink-0" />
              <span className="font-bold text-[22px] tracking-tight text-gray-900 whitespace-nowrap">RecoverAI</span>
            </div>
            
            {/* Desktop Toggle */}
            <button 
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className={`hidden lg:block p-2 rounded-xl text-gray-400 hover:text-gray-700 hover:bg-gray-50 transition-colors ${!isSidebarOpen && 'mx-auto'}`}
              title="Toggle Sidebar"
            >
              <Menu className="h-5 w-5" />
            </button>
            {/* Mobile Close */}
            <button 
              onClick={() => setIsMobileSidebarOpen(false)}
              className="lg:hidden p-2 rounded-xl text-gray-400 hover:text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <Menu className="h-5 w-5" />
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto p-4 space-y-1.5 custom-scrollbar">
            <NavItem icon={Home} label="Overview" href="/" />
            <NavItem icon={Briefcase} label="Recovery Cases" href="/recovery-cases" />
            <NavItem icon={List} label="Audit Trail" href="/audit-trail" />
            <NavItem icon={Eye} label="Ghost Revenue Hunter" href="/ghost-revenue" />
            <NavItem icon={Users} label="Customers" href="/customers" />
            <NavItem icon={CreditCard} label="Payments" href="/payments" />
            <NavItem icon={BarChart2} label="Analytics" href="/analytics" />
            <NavItem icon={Brain} label="Recovery Passport" href="/recovery-passport" />
            <NavItem icon={BookOpen} label="User Guide" href="/guide" />
            <div className="pt-2 pb-1">
              <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest px-3 mb-1">Automation</p>
            </div>
            <NavItem icon={Zap} label="Recovery assistant" href="/recover" accent={true} />
          </nav>

          {/* User Profile & Account Switcher */}
          <div className="p-4 border-t border-gray-50/50">
            <div 
              onClick={() => {
                setAuthModalTab('login');
                setIsAuthModalOpen(true);
              }}
              className={`flex items-center ${isSidebarOpen ? 'justify-between p-3' : 'justify-center p-2'} bg-[#F8F9FA] rounded-[18px] hover:bg-indigo-50/60 hover:border-indigo-200 cursor-pointer transition-all border border-gray-100 group shadow-xs`}
              title="Click to Switch Merchant Profile or Account"
            >
              <div className="flex items-center gap-3 overflow-hidden">
                <Avatar className="h-9 w-9 bg-indigo-600 text-white font-bold text-sm shrink-0 shadow-sm ring-2 ring-indigo-100">
                  <AvatarFallback className="bg-indigo-600">{initials}</AvatarFallback>
                </Avatar>
                <div className={`flex flex-col transition-all duration-300 ${!isSidebarOpen ? 'w-0 opacity-0' : 'w-auto opacity-100 whitespace-nowrap'}`}>
                  <span className="font-semibold text-[13px] text-gray-900 leading-none mb-1 group-hover:text-indigo-600 transition-colors">
                    {user?.full_name || 'Rohit Kumar'}
                  </span>
                  <span className="text-[11px] text-gray-500 leading-none flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block"></span>
                    {user?.company_name || 'Admin'}
                  </span>
                </div>
              </div>
              {isSidebarOpen && <ChevronDown className="h-4 w-4 text-gray-400 group-hover:text-indigo-600 shrink-0 transition-colors" />}
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden min-w-0">
        
        {/* Mobile Header (Only visible on small screens) */}
        <div className="lg:hidden flex items-center justify-between px-4 h-[64px] bg-white border-b border-gray-100 shrink-0">
          <div className="flex items-center gap-3">
            <button 
              onClick={() => setIsMobileSidebarOpen(true)}
              className="p-2 -ml-2 text-gray-600 hover:bg-gray-50 rounded-lg transition-colors"
            >
              <Menu className="h-5 w-5" />
            </button>
            <span className="font-bold text-gray-900 truncate max-w-[150px] sm:max-w-[200px]">{getPageTitle()}</span>
          </div>
          
          <div className="flex items-center gap-3">
            <AgentStatusPill />
            <button onClick={toggleTheme} aria-label={darkMode ? 'Use light mode' : 'Use dark mode'} className="rounded-lg p-2 text-gray-500 hover:bg-gray-100">{darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</button>
            <Avatar className="h-8 w-8 bg-indigo-600 text-white font-bold text-xs shrink-0 shadow-sm ring-2 ring-indigo-100 cursor-pointer" onClick={() => setIsAuthModalOpen(true)}>
              <AvatarFallback className="bg-indigo-600">{initials}</AvatarFallback>
            </Avatar>
          </div>
        </div>

        {/* Top Header Background (Desktop) */}
        <div className="hidden lg:block px-6 md:px-10 pt-6 pb-2 shrink-0">
          <header className="flex justify-between items-center bg-white p-3 pr-4 pl-6 rounded-full shadow-sm border border-gray-100 h-[64px] w-full">
            {/* Search Bar - only shown if not overview */}
            {pathname !== '/' ? (
              <div className="flex items-center gap-3 w-[360px]">
                <Search className="h-4 w-4 text-gray-400" />
                <input 
                  type="text" 
                  placeholder="Search by Payment ID, Customer or Status..." 
                  className="bg-transparent border-none outline-none text-sm w-full placeholder:text-gray-400 font-medium"
                />
              </div>
            ) : (
              <div>
                <span className="text-sm font-medium text-gray-400 tracking-wide">
                  Dashboard / <span className="text-indigo-600 font-semibold">{getPageTitle()}</span>
                </span>
              </div>
            )}
            
            <div className="flex items-center gap-4 shrink-0 ml-auto">
              {/* Active Workspace / Profile Switcher Pill */}
              <button
                onClick={() => {
                  setAuthModalTab('login');
                  setIsAuthModalOpen(true);
                }}
                className="flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-indigo-100 bg-indigo-50/50 hover:bg-indigo-100/70 text-indigo-700 text-xs font-bold transition-all shadow-xs"
                title="Switch Merchant Workspace"
              >
                <Building className="h-3.5 w-3.5 text-indigo-600" />
                <span className="max-w-[140px] truncate">{user?.company_name || 'Fashion D2C'}</span>
                <span className="text-[10px] bg-white px-1.5 py-0.5 rounded text-indigo-600 font-semibold border border-indigo-200">
                  Switch
                </span>
              </button>

              <div className="h-6 w-[1px] bg-gray-100"></div>

              {/* Agent Status Pill — always visible in header */}
              <AgentStatusPill />
              
              <div className="h-6 w-[1px] bg-gray-100"></div>

              <button onClick={toggleTheme} aria-label={darkMode ? 'Use light mode' : 'Use dark mode'} title={darkMode ? 'Use light mode' : 'Use dark mode'} className="relative rounded-full p-2 text-gray-400 transition-all hover:bg-indigo-50 hover:text-indigo-600">
                {darkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </button>
              
              <button className="relative p-2 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-full transition-all">
                <Bell className="h-5 w-5" />
                <span className="absolute top-1.5 right-1.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-indigo-600 text-[10px] font-bold text-white border-2 border-white px-1">
                  3
                </span>
              </button>
              
              <div className="h-6 w-[1px] bg-gray-100"></div>
              
              <Link href="/settings" className="relative p-2 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-full transition-all">
                <Settings className="h-5 w-5" />
              </Link>
            </div>
          </header>
        </div>

        {/* Scrollable Content (Children) */}
        <div className="flex-1 overflow-y-auto px-4 lg:px-6 md:px-10 pb-10 pt-4 lg:pt-0 custom-scrollbar min-w-0">
          {children}
        </div>
      </main>

      {/* Auth & Profile Switcher Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        defaultTab={authModalTab}
      />
    </div>
  );
}

// ── Agent Status Pill — shown in every page header ─────────────────────────
function AgentStatusPill() {
  const [active, setActive] = React.useState<boolean | null>(null);
  const { apiFetch } = useAuth();

  React.useEffect(() => {
    const poll = async () => {
      try {
        const res = await apiFetch('/agent/status');
        if (res.ok) {
          const d = await res.json();
          React.startTransition(() => setActive(d.active));
        }
      } catch {}
    };
    poll();
    const id = setInterval(poll, 15000); // poll every 15s
    return () => clearInterval(id);
  }, [apiFetch]);

  if (active === null) return null;

  return (
    <Link
      href="/recover"
      className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-bold transition-all cursor-pointer ${
        active
          ? 'bg-emerald-50 border-emerald-200 text-emerald-700 hover:bg-emerald-100'
          : 'bg-gray-50 border-gray-200 text-gray-500 hover:bg-gray-100'
      }`}
    >
      <div className={`h-1.5 w-1.5 rounded-full ${active ? 'bg-emerald-500 animate-pulse' : 'bg-gray-400'}`} />
      Agent {active ? '● Active' : '○ Paused'}
    </Link>
  );
}

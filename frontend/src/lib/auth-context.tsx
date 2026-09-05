'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

export interface UserProfile {
  user_id: string;
  merchant_id: string;
  email: string;
  full_name: string;
  company_name: string;
  role: string;
  api_key?: string;
  created_at?: string;
  last_login_at?: string;
}

export interface UserSummary {
  user_id: string;
  email: string;
  full_name: string;
  company_name: string;
  role: string;
  is_current: boolean;
}

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  availableProfiles: UserSummary[];
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  register: (data: { email: string; password: string; full_name: string; company_name?: string }) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;
  updateProfile: (data: { full_name?: string; company_name?: string; new_password?: string }) => Promise<{ success: boolean; error?: string }>;
  refreshProfiles: () => Promise<void>;
  apiFetch: (url: string, options?: RequestInit) => Promise<Response>;
}

// Read API base from env; falls back to localhost for dev
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

async function fetchWithTimeout(input: RequestInfo | URL, init: RequestInit = {}, timeoutMs = 60000) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try { return await fetch(input, { ...init, signal: controller.signal }); }
  finally { window.clearTimeout(timer); }
}

function getConnectionError(error: unknown) {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return 'The server is taking too long to respond. Please try again.';
  }
  if (error instanceof TypeError) {
    return 'Unable to reach the server. Please check that the API is running and try again.';
  }
  return error instanceof Error && error.message ? error.message : 'Connection error';
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [availableProfiles, setAvailableProfiles] = useState<UserSummary[]>([]);

  // Authenticated fetch helper that injects Bearer token
  const apiFetch = useCallback(
    async (url: string, options: RequestInit = {}): Promise<Response> => {
      const targetUrl = url.startsWith('http') ? url : `${API_BASE}${url.startsWith('/') ? '' : '/'}${url}`;
      const headers = new Headers(options.headers || {});

      const activeToken = token || (typeof window !== 'undefined' ? localStorage.getItem('recoverai_auth_token') : null);
      if (activeToken && !headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${activeToken}`);
      }

      return fetch(targetUrl, {
        ...options,
        headers,
      });
    },
    [token]
  );

  // Fetch available registered profiles for the current merchant
  const refreshProfiles = useCallback(async () => {
    try {
      const res = await apiFetch('/auth/profiles');
      if (res.ok) {
        const data: UserSummary[] = await res.json();
        setAvailableProfiles(data);
      }
    } catch (e) {
      console.debug('Failed to fetch profile list:', e);
    }
  }, [apiFetch]);

  // Initial session restoration
  useEffect(() => {
    const initAuth = async () => {
      setIsLoading(true);
      try {
        const storedToken = localStorage.getItem('recoverai_auth_token');
        if (storedToken) {
          setToken(storedToken);
          const res = await fetch(`${API_BASE}/auth/me`, {
            headers: { Authorization: `Bearer ${storedToken}` },
          });
          if (res.ok) {
            const userData = await res.json();
            setUser(userData);
          } else {
            localStorage.removeItem('recoverai_auth_token');
            setToken(null);
            setUser(null);
          }
        } else {
          setUser(null);
        }
      } catch (e) {
        console.debug('Auth init error:', e);
        localStorage.removeItem('recoverai_auth_token');
        setToken(null);
        setUser(null);
      } finally {
        setIsLoading(false);
        refreshProfiles();
      }
    };

    initAuth();
  }, [refreshProfiles]);

  const login = async (email: string, password: string) => {
    try {
      const res = await fetchWithTimeout(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        return { success: false, error: data.detail || 'Login failed' };
      }

      setToken(data.access_token);
      setUser(data.user);
      localStorage.setItem('recoverai_auth_token', data.access_token);
      refreshProfiles().catch(() => undefined);
      return { success: true };
    } catch (e: unknown) {
      return { success: false, error: getConnectionError(e) };
    }
  };

  const register = async (data: { email: string; password: string; full_name: string; company_name?: string }) => {
    try {
      const res = await fetchWithTimeout(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      const resData = await res.json();
      if (!res.ok) {
        return { success: false, error: resData.detail || 'Registration failed' };
      }

      setToken(resData.access_token);
      setUser(resData.user);
      localStorage.setItem('recoverai_auth_token', resData.access_token);
      refreshProfiles().catch(() => undefined);
      return { success: true };
    } catch (e: unknown) {
      return { success: false, error: getConnectionError(e) };
    }
  };

  const updateProfile = async (data: { full_name?: string; company_name?: string; new_password?: string }) => {
    try {
      const res = await apiFetch('/auth/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      const resData = await res.json();
      if (!res.ok) {
        return { success: false, error: resData.detail || 'Update failed' };
      }

      setUser(resData);
      await refreshProfiles();
      return { success: true };
    } catch (e: any) {
      return { success: false, error: e.message || 'Connection error' };
    }
  };

  const logout = () => {
    const activeToken = token || localStorage.getItem('recoverai_auth_token');
    if (activeToken) {
      fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${activeToken}` },
      }).catch(() => undefined);
    }
    localStorage.removeItem('recoverai_auth_token');
    setToken(null);
    setUser(null);
    setAvailableProfiles([]);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user,
        isLoading,
        availableProfiles,
        login,
        register,
        logout,
        updateProfile,
        refreshProfiles,
        apiFetch,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

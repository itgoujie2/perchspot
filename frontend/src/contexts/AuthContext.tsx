import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface AuthUser {
  id: string;
  email: string;
  credit_balance: number;
}

interface RegisterResult {
  promoMessage?: string;
}

interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, referralCode?: string, promoCode?: string) => Promise<RegisterResult>;
  logout: () => void;
  updateBalance: (newBalance: number) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount, check for stored token
  useEffect(() => {
    const stored = localStorage.getItem('auth_token');
    if (stored) {
      setToken(stored);
      validateToken(stored);
    } else {
      setIsLoading(false);
    }
  }, []);

  const validateToken = async (t: string) => {
    try {
      const res = await axios.get(`${API_BASE}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${t}` },
      });
      setUser({
        id: res.data.user_id,
        email: res.data.email,
        credit_balance: res.data.credit_balance,
      });
      setToken(t);
    } catch {
      localStorage.removeItem('auth_token');
      setToken(null);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    const res = await axios.post(`${API_BASE}/api/v1/auth/login`, { email, password });
    const { user_id, email: userEmail, credit_balance, token: jwt } = res.data;
    localStorage.setItem('auth_token', jwt);
    setToken(jwt);
    setUser({ id: user_id, email: userEmail, credit_balance });
  };

  const register = async (email: string, password: string, referralCode?: string, promoCode?: string): Promise<RegisterResult> => {
    const payload: { email: string; password: string; referral_code?: string; promo_code?: string } = { email, password };
    if (referralCode) {
      payload.referral_code = referralCode;
    }
    if (promoCode) {
      payload.promo_code = promoCode;
    }
    const res = await axios.post(`${API_BASE}/api/v1/auth/register`, payload);
    const { user_id, email: userEmail, credit_balance, token: jwt, promo_message } = res.data;
    localStorage.setItem('auth_token', jwt);
    setToken(jwt);
    setUser({ id: user_id, email: userEmail, credit_balance });
    return { promoMessage: promo_message };
  };

  const logout = useCallback(() => {
    localStorage.removeItem('auth_token');
    setToken(null);
    setUser(null);
  }, []);

  const updateBalance = useCallback((newBalance: number) => {
    setUser(prev => prev ? { ...prev, credit_balance: newBalance } : null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user,
        isLoading,
        login,
        register,
        logout,
        updateBalance,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

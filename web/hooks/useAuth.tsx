'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { authApi, statsApi, User, UserStats, getAccessToken } from '../lib/api';

interface AuthContextType {
  user: User | null;
  stats: UserStats | null;
  loading: boolean;
  login: (email: string, pass: string) => Promise<void>;
  register: (email: string, pass: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  refreshStats: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshStats = useCallback(async () => {
    try {
      const s = await statsApi.getStats('30d');
      setStats(s);
    } catch {
      // stats error ignored for non-logged in state
    }
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const u = await authApi.me();
      setUser(u);
      await refreshStats();
    } catch {
      setUser(null);
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, [refreshStats]);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = async (email: string, pass: string) => {
    await authApi.login(email, pass);
    await refreshUser();
  };

  const register = async (email: string, pass: string) => {
    await authApi.register(email, pass);
    await refreshUser();
  };

  const logout = async () => {
    await authApi.logout();
    setUser(null);
    setStats(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        stats,
        loading,
        login,
        register,
        logout,
        refreshUser,
        refreshStats,
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

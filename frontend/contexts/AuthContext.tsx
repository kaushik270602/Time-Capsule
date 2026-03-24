"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { authApi, UserResponse } from "@/lib/api";

interface AuthState {
  user: UserResponse | null;
  loading: boolean;
  error: string | null;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    loading: true,
    error: null,
  });

  const setError = (error: string | null) =>
    setState((prev) => ({ ...prev, error }));

  const clearError = () => setError(null);

  const fetchUser = useCallback(async () => {
    try {
      const { data } = await authApi.me();
      setState({ user: data, loading: false, error: null });
    } catch {
      setState({ user: null, loading: false, error: null });
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const login = async (email: string, password: string) => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      await authApi.login(email, password);
      // The httpOnly cookie is set by the server automatically.
      await fetchUser();
    } catch (err: any) {
      const message =
        err.response?.data?.detail || "Login failed. Please try again.";
      setState((prev) => ({ ...prev, loading: false, error: message }));
      throw new Error(message);
    }
  };

  const register = async (email: string, password: string) => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      await authApi.register(email, password);
      setState((prev) => ({ ...prev, loading: false }));
    } catch (err: any) {
      const message =
        err.response?.data?.detail || "Registration failed. Please try again.";
      setState((prev) => ({ ...prev, loading: false, error: message }));
      throw new Error(message);
    }
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch {
      // Best-effort: clear local state even if the server call fails
    }
    setState({ user: null, loading: false, error: null });
  };

  return (
    <AuthContext.Provider
      value={{ ...state, login, register, logout, clearError }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

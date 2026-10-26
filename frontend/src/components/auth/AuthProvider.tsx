"use client";

/**
 * Client-side auth state, backed by the real backend (backend/app/api/v1/endpoints/auth.py).
 *
 * The backend issues a JWT bearer token (no cookies), so the token is kept in
 * localStorage and every authenticated request sends `Authorization: Bearer …`.
 * On load a stored token is re-validated against GET /auth/me; invalid tokens
 * are dropped instead of leaving the UI in a half-signed-in state.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

import { api, ApiError } from "@/lib/api-client";
import type { User } from "@/lib/api-client";

const TOKEN_KEY = "zenvy.auth.token";
const USER_KEY = "zenvy.auth.user";

type AuthStatus = "loading" | "anonymous" | "authenticated";

interface RegisterPayload {
  email: string;
  password: string;
  full_name?: string;
  phone_number?: string;
}

interface AuthContextValue {
  status: AuthStatus;
  token: string | null;
  user: User | null;
  login: (email: string, password: string) => Promise<User>;
  register: (payload: RegisterPayload) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function persist(token: string, user: User) {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function clearStorage() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);

  // Re-validate the stored session once on mount (SSR renders "loading", so
  // there is no hydration mismatch either way).
  useEffect(() => {
    let active = true;

    const toAnonymous = () => {
      if (!active) return;
      setToken(null);
      setUser(null);
      setStatus("anonymous");
    };

    const stored = window.localStorage.getItem(TOKEN_KEY);
    if (!stored) {
      // Defer one tick: no setState synchronously inside the effect (lint rule).
      const idle = window.setTimeout(toAnonymous, 0);
      return () => {
        active = false;
        window.clearTimeout(idle);
      };
    }

    api
      .getMe(stored)
      .then((profile) => {
        if (!active) return;
        persist(stored, profile);
        setToken(stored);
        setUser(profile);
        setStatus("authenticated");
      })
      .catch((error: unknown) => {
        if (!active) return;
        // Expired/malformed token → forget it. Network trouble → surface the
        // logged-out state; the user can simply sign in again.
        const unauthorised =
          error instanceof ApiError && (error.status === 401 || error.status === 403);
        if (unauthorised) {
          clearStorage();
        }
        toAnonymous();
      });

    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const result = await api.login({ email, password });
    persist(result.access_token, result.user);
    setToken(result.access_token);
    setUser(result.user);
    setStatus("authenticated");
    return result.user;
  }, []);

  const register = useCallback(async (payload: RegisterPayload) => {
    const result = await api.register({
      email: payload.email,
      password: payload.password,
      full_name: payload.full_name || undefined,
      phone_number: payload.phone_number || undefined,
      role: "farmer",
      preferred_language: "en",
    });
    persist(result.access_token, result.user);
    setToken(result.access_token);
    setUser(result.user);
    setStatus("authenticated");
    return result.user;
  }, []);

  const logout = useCallback(() => {
    clearStorage();
    setToken(null);
    setUser(null);
    setStatus("anonymous");
  }, []);

  const value = useMemo(
    () => ({ status, token, user, login, register, logout }),
    [status, token, user, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside <AuthProvider>.");
  }
  return context;
}

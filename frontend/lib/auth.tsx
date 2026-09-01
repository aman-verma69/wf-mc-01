"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { api, type Customer } from "./api";

type AuthContextValue = { customer: Customer | null; loading: boolean; signIn: (email: string, password: string) => Promise<void>; signUp: (email: string, password: string) => Promise<void>; signOut: () => void };
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { if (!localStorage.getItem("fieldhouse_token")) { setLoading(false); return; } api.me().then(setCustomer).catch(() => localStorage.removeItem("fieldhouse_token")).finally(() => setLoading(false)); }, []);
  async function signIn(email: string, password: string) { const result = await api.login(email, password); localStorage.setItem("fieldhouse_token", result.access_token); setCustomer(await api.me()); }
  async function signUp(email: string, password: string) { await api.register(email, password); await signIn(email, password); }
  function signOut() { localStorage.removeItem("fieldhouse_token"); setCustomer(null); }
  return <AuthContext.Provider value={{ customer, loading, signIn, signUp, signOut }}>{children}</AuthContext.Provider>;
}
export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error("useAuth must be used inside AuthProvider"); return value; }

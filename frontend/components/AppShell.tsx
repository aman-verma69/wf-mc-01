"use client";

import Link from "next/link";
import { ShoppingBag, UserRound } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";

const links = [{ href: "/products", label: "Shop" }, { href: "/orders", label: "Orders" }, { href: "/cart", label: "Cart" }];
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname(); const router = useRouter(); const { customer, loading, signOut } = useAuth();
  useEffect(() => { if (!loading && !customer && !["/", "/login", "/register"].includes(pathname)) router.replace(`/login?next=${encodeURIComponent(pathname)}`); }, [customer, loading, pathname, router]);
  if (loading) return <div className="min-h-screen grid place-items-center text-sm text-[var(--muted-foreground)]">Loading your account...</div>;
  if (!customer && ["/", "/login", "/register"].includes(pathname)) return <>{children}</>;
  if (!customer) return <div className="grid min-h-screen place-items-center text-sm text-[var(--muted-foreground)]">Redirecting to sign in...</div>;
  return <div className="min-h-screen"><header className="sticky top-0 z-20 border-b border-[var(--border)] bg-[var(--background)]/95 backdrop-blur"><div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 lg:px-8"><Link href="/products" className="flex items-center gap-2 font-display text-lg font-bold tracking-tight"><span className="grid h-8 w-8 place-items-center bg-[var(--primary)] text-white"><ShoppingBag size={16} /></span>fieldhouse</Link><nav className="hidden items-center gap-8 md:flex">{links.map(link => <Link key={link.href} href={link.href} className={`text-sm ${pathname.startsWith(link.href) ? "font-semibold text-[var(--primary)]" : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"}`}>{link.label}</Link>)}{customer.role === "merchant" && <Link href="/merchant" className="text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)]">Merchant</Link>}</nav><div className="flex items-center gap-3"><Link href="/account" aria-label="Account" className="rounded-full p-2 hover:bg-[var(--surface-muted)]"><UserRound size={18} /></Link><button onClick={signOut} className="hidden text-xs font-semibold text-[var(--muted-foreground)] hover:text-[var(--destructive)] sm:block">Sign out</button></div></div></header><main>{children}</main><nav className="fixed bottom-0 left-0 right-0 z-20 grid grid-cols-3 border-t border-[var(--border)] bg-white md:hidden">{links.map(link => <Link key={link.href} href={link.href} className="py-3 text-center text-xs font-medium">{link.label}</Link>)}</nav></div>;
}

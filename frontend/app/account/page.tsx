"use client";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { SectionHeading } from "@/components/ui";
export default function AccountPage() { const { customer } = useAuth(); return <div className="mx-auto max-w-3xl px-5 py-10 lg:px-8 lg:py-16"><SectionHeading eyebrow="Account" title="Your details" /><div className="border-y border-[var(--border)] bg-white px-5 py-6"><p className="text-xs uppercase tracking-wider text-[var(--muted-foreground)]">Email</p><p className="mt-2 font-semibold">{customer?.email}</p><p className="mt-6 text-xs uppercase tracking-wider text-[var(--muted-foreground)]">Member since</p><p className="mt-2 text-sm">{customer?.created_at ? new Date(customer.created_at).toLocaleDateString("en-IN", { dateStyle: "long" }) : ""}</p></div><Link href="/products" className="mt-7 inline-block text-sm font-semibold text-[var(--primary)]">Continue shopping</Link></div>; }

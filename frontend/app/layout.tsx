import "./globals.css";
import type { Metadata } from "next";
export const metadata: Metadata = { title: "AI Commerce Agent", description: "Agentic checkout demo" };
export default function Layout({ children }: { children: React.ReactNode }) { return <html lang="en"><body>{children}</body></html>; }

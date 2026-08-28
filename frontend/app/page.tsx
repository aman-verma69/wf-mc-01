"use client";
import { FormEvent, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Product = { id:string; name:string; description:string; price:number; stock:number; quantity?:number; line_total?:number };
type Message = { role:"user"|"agent"; text:string; products?:Product[]; blocked?:boolean };
type RazorpayResponse = { razorpay_order_id:string; razorpay_payment_id:string; razorpay_signature:string };

declare global { interface Window { Razorpay?: new (options: Record<string, unknown>) => { open: () => void } } }

const rupees = (value: number) => new Intl.NumberFormat("en-IN", {style:"currency",currency:"INR",maximumFractionDigits:0}).format(value);

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([{role:"agent",text:"Hi! I’m your AI Commerce Agent. Ask me to find ANC headphones under ₹3000."}]);
  const [input, setInput] = useState(""); const [cart, setCart] = useState<Product[]>([]); const [busy, setBusy] = useState(false); const [notice, setNotice] = useState("");
  const openRazorpay = async (payment:{order_id:string; amount:number; currency:string; key_id:string}) => {
    if (!window.Razorpay) { setNotice("Razorpay Checkout failed to load. Check your connection and test key."); return; }
    const razorpay = new window.Razorpay({ key: payment.key_id, amount: payment.amount * 100, currency: payment.currency, order_id: payment.order_id, name: "AI Commerce Agent", description: "Secure test payment", handler: async (response: RazorpayResponse) => {
      const r = await fetch(`${API}/api/payment/verify`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({order_id:response.razorpay_order_id,payment_id:response.razorpay_payment_id,signature:response.razorpay_signature})});
      if (r.ok) { setNotice("Payment verified server-side. Purchase complete."); setCart([]); } else setNotice("Payment was received but signature verification failed.");
    }, theme: {color:"#22d3ee"} }); razorpay.open();
  };
  const send = async (message = input) => {
    if (!message.trim() || busy) return; setBusy(true); setInput(""); setMessages(m => [...m, {role:"user",text:message}]);
    try { const r = await fetch(`${API}/api/chat`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message})}); const data = await r.json();
      setMessages(m => [...m,{role:"agent",text:data.message,products:data.products,blocked:data.blocked}]); if (data.cart) setCart(data.cart); if (data.payment?.mode === "razorpay") await openRazorpay(data.payment);
    } catch { setMessages(m => [...m,{role:"agent",text:"Backend unavailable. Start FastAPI on port 8000.",blocked:true}]); } finally { setBusy(false); }
  };
  const add = async (p:Product) => { const r=await fetch(`${API}/api/cart`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:p.id})}); const data=await r.json(); if(data.cart){setCart(data.cart); setNotice(`${p.name} added to cart`)} };
  const failDemo = async () => { const r=await fetch(`${API}/api/demo/price-change`,{method:"POST"}); const d=await r.json(); setNotice(d.message); };
  const total = cart.reduce((sum, item) => sum + (item.line_total ?? item.price * (item.quantity ?? 1)), 0);
  return <main className="min-h-screen bg-[radial-gradient(ellipse_at_top,_#112e4d,_#07111f_55%)] p-5 lg:p-10"><script src="https://checkout.razorpay.com/v1/checkout.js" />
    <div className="mx-auto max-w-6xl"><header className="mb-7 flex items-center justify-between"><div><p className="text-xs font-bold uppercase tracking-[.2em] text-cyan-300">Razorpay Track 01 · Test mode</p><h1 className="mt-1 text-3xl font-semibold">AI Commerce Agent</h1></div><div className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs text-emerald-300">● Guardrails active</div></header>
    <div className="grid gap-5 lg:grid-cols-[1fr_330px]"><section className="overflow-hidden rounded-3xl border border-white/10 bg-slate-950/50 shadow-2xl"><div className="border-b border-white/10 px-6 py-4 text-sm text-slate-300">Conversation <span className="float-right text-cyan-300">Live catalog data</span></div><div className="h-[500px] space-y-4 overflow-y-auto p-6">{messages.map((m,i)=><div key={i} className={m.role === "user" ? "ml-12 text-right" : "mr-8"}><div className={`inline-block max-w-full rounded-2xl px-4 py-3 text-left text-sm ${m.role==="user"?"bg-cyan-500 text-slate-950":"bg-slate-800 text-slate-100"} ${m.blocked?"border border-rose-400 bg-rose-950/60":""}`}>{m.text}</div>{m.products && <div className="mt-3 grid gap-3 sm:grid-cols-2">{m.products.map(p=><article key={p.id} className="rounded-2xl border border-white/10 bg-slate-900 p-4 text-left"><div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-cyan-400/10 text-xl">🎧</div><h3 className="font-medium">{p.name}</h3><p className="mt-1 h-10 text-xs text-slate-400">{p.description}</p><div className="mt-3 flex items-center justify-between"><span className="font-semibold text-cyan-300">{rupees(p.price)}</span><button onClick={()=>add(p)} className="rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-slate-900">Add</button></div><p className="mt-2 text-[11px] text-slate-500">{p.stock} in stock</p></article>)}</div>}</div>)}</div><form onSubmit={(e:FormEvent)=>{e.preventDefault();send()}} className="flex gap-2 border-t border-white/10 p-4"><input value={input} onChange={e=>setInput(e.target.value)} placeholder="Try: Find ANC headphones under ₹3000" className="min-w-0 flex-1 rounded-xl border border-white/10 bg-slate-900 px-4 py-3 text-sm outline-none ring-cyan-400 focus:ring-1"/><button className="rounded-xl bg-cyan-400 px-5 text-sm font-bold text-slate-950 disabled:opacity-60" disabled={busy}>{busy?"Thinking…":"Send"}</button></form></section>
    <aside className="space-y-4"><div className="rounded-3xl border border-white/10 bg-slate-950/60 p-5"><div className="flex justify-between"><h2 className="font-semibold">Your cart</h2><span className="text-xs text-slate-500">{cart.length} items</span></div>{cart.length===0?<p className="py-8 text-center text-sm text-slate-500">Nothing here yet.</p>:<><div className="mt-4 space-y-3">{cart.map(i=><div key={i.id} className="flex justify-between text-sm"><span>{i.name} <span className="text-slate-500">×{i.quantity ?? 1}</span></span><b>{rupees(i.line_total ?? i.price)}</b></div>)}</div><div className="mt-5 flex justify-between border-t border-white/10 pt-4 font-semibold"><span>Exact total</span><span className="text-cyan-300">{rupees(total)}</span></div><button onClick={()=>send("Buy it")} className="mt-4 w-full rounded-xl bg-cyan-400 py-3 text-sm font-bold text-slate-950">Prepare checkout</button></>}</div>
      <div className="rounded-3xl border border-amber-400/20 bg-amber-300/5 p-5"><p className="text-xs font-bold uppercase tracking-wider text-amber-300">Required failure demo</p><p className="mt-2 text-sm text-slate-300">After preparing a ₹2499 quote, simulate a price change. Confirmation will be blocked and authorization invalidated.</p><button onClick={failDemo} className="mt-3 text-sm font-semibold text-amber-200 underline">Simulate price change → ₹2799</button></div>
      {notice && <p className="rounded-xl border border-cyan-400/20 bg-cyan-400/10 p-3 text-xs text-cyan-100">{notice}</p>}
      <p className="px-2 text-xs leading-5 text-slate-500">Pricing, inventory, totals, policy checks and payment verification happen in the backend. AI only routes intents and recommends catalog results.</p></aside></div></div></main>;
}

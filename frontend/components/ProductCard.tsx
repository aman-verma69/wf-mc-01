import { Product } from "./types";

const rupees = (value: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value);
const visual: Record<string, { label: string; art: string }> = {
  audio: { label: "AUDIO", art: "◉" }, wearables: { label: "WEARABLE", art: "◌" }, accessories: { label: "ACCESSORY", art: "↯" }, work: { label: "WORKSPACE", art: "⌁" },
};

export function ProductCard({ product, onAdd }: { product: Product; onAdd: (product: Product) => void }) {
  const productVisual = visual[product.category] || visual.accessories;
  return <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition duration-200 hover:-translate-y-1 hover:border-[#3156e8]/35 hover:shadow-xl hover:shadow-[#3156e8]/10">
    <div className={`product-art product-art-${product.category}`}><span>{productVisual.art}</span><div className="product-orb" /><p>{productVisual.label}</p></div>
    <div className="p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold text-[#142046]">{product.name}</h3><p className="mt-1 text-xs leading-5 text-slate-500">{product.description}</p></div><span className="shrink-0 rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-semibold text-emerald-700">In stock</span></div><div className="mt-4 flex items-center justify-between"><span className="text-base font-bold text-[#142046]">{rupees(product.price)}</span><button onClick={() => onAdd(product)} className="rounded-lg border border-[#3156e8] px-3 py-2 text-xs font-semibold text-[#3156e8] transition hover:bg-[#3156e8] hover:text-white">Add</button></div></div>
  </article>;
}

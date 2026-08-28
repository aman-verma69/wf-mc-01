export type Product = { id: string; name: string; description: string; price: number; stock: number; category: string; quantity?: number; line_total?: number };
export type Message = { role: "user" | "agent"; text: string; products?: Product[]; blocked?: boolean };

export type Brand = {
  id: string;
  org_id: string;
  sport: "tennis" | "padel" | "pickleball" | "badminton" | "squash";
  name: string;
  website_url: string;
  timezone: string;
  active: boolean;
  accent_color: string;
};

export type Me = {
  id: string;
  org_id: string;
  email: string;
  role: "owner" | "admin" | "growth_head" | "marketer" | "intern" | "viewer";
  active: boolean;
};

export type CostMeter = {
  cap_usd: number;
  spent_usd: number;
  remaining_usd: number;
  pct_used: number;
};

export type Job = {
  id: string;
  type: string;
  status: "queued" | "running" | "done" | "failed" | "cancelled";
  brand_id: string | null;
  cost_usd: number;
  progress: number;
  created_at: string;
  error: string;
};

export type Product = {
  id: string;
  brand_id: string;
  sku: string;
  title: string;
  description: string;
  price: number;
  margin: number;
  image_urls: string[];
  is_new: boolean;
  is_bestseller: boolean;
  is_dead_stock: boolean;
};

-- ============================================================================
-- Marketing Dog — Supabase schema (web data layer)
-- ----------------------------------------------------------------------------
-- This is the data plane for the Next.js surface: auth, orgs, members, brands,
-- and the brand theme/scan that powers BrandSkin. The Python agent backend keeps
-- its own operational tables; this gives the web app a Supabase-native home for
-- identity + brand identity, with Row Level Security enforcing tenant isolation
-- (the DB-layer mirror of apps/api/app/guards/no_cross_brand.py).
--
-- Apply with: supabase db push   (or paste into the SQL editor)
-- ============================================================================

create extension if not exists "pgcrypto";

-- ---------- enums ----------
do $$ begin
  create type member_role as enum ('owner','admin','growth_head','marketer','intern','viewer');
exception when duplicate_object then null; end $$;

-- ---------- profiles (1:1 with auth.users) ----------
create table if not exists public.profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  email       text,
  full_name   text,
  created_at  timestamptz not null default now()
);

-- ---------- orgs ----------
create table if not exists public.orgs (
  id                   uuid primary key default gen_random_uuid(),
  name                 text not null,
  -- white-label / default brand theme for the org chrome
  theme                jsonb not null default '{}'::jsonb,   -- { primary, accent, mode }
  logo_url             text default '',
  monthly_cost_cap_usd numeric not null default 200,
  created_at           timestamptz not null default now()
);

-- ---------- membership ----------
create table if not exists public.org_members (
  org_id     uuid not null references public.orgs(id) on delete cascade,
  user_id    uuid not null references auth.users(id) on delete cascade,
  role       member_role not null default 'viewer',
  created_at timestamptz not null default now(),
  primary key (org_id, user_id)
);

-- ---------- brands (one isolated vertical per row) ----------
create table if not exists public.brands (
  id           uuid primary key default gen_random_uuid(),
  org_id       uuid not null references public.orgs(id) on delete cascade,
  name         text not null,
  vertical     text not null default '',            -- e.g. tennis | saas | skincare ...
  website_url  text not null default '',
  timezone     text not null default 'Asia/Kolkata',
  active        boolean not null default true,
  -- BrandSkin inputs/outputs:
  accent_color text not null default '#CCFF00',      -- primary seed
  brand_colors jsonb not null default '{}'::jsonb,    -- { primary, accent, extracted:[...] }
  theme        jsonb not null default '{}'::jsonb,    -- cached buildTheme() output (light+dark)
  logo_url     text not null default '',
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index if not exists brands_org_idx on public.brands(org_id);

-- ---------- brand scans (what "Sniff" extracts from a website) ----------
create table if not exists public.brand_scans (
  id           uuid primary key default gen_random_uuid(),
  brand_id     uuid not null references public.brands(id) on delete cascade,
  source_url   text not null,
  palette      jsonb not null default '[]'::jsonb,    -- ["#0058A3","#FFDB00", ...]
  logo_url     text default '',
  voice        text default '',
  raw          jsonb not null default '{}'::jsonb,
  created_at   timestamptz not null default now()
);
create index if not exists brand_scans_brand_idx on public.brand_scans(brand_id);

-- ---------- updated_at trigger ----------
create or replace function public.touch_updated_at() returns trigger
language plpgsql as $$ begin new.updated_at = now(); return new; end $$;
drop trigger if exists brands_touch on public.brands;
create trigger brands_touch before update on public.brands
  for each row execute function public.touch_updated_at();

-- ============================================================================
-- Row Level Security — tenant isolation
-- ============================================================================
alter table public.profiles     enable row level security;
alter table public.orgs         enable row level security;
alter table public.org_members  enable row level security;
alter table public.brands       enable row level security;
alter table public.brand_scans  enable row level security;

-- helper: is the current user a member of :org ?
create or replace function public.is_member(target_org uuid) returns boolean
language sql security definer stable set search_path = public as $$
  select exists (
    select 1 from public.org_members m
    where m.org_id = target_org and m.user_id = auth.uid()
  );
$$;

-- helper: does the current user have an elevated role in :org ?
create or replace function public.is_manager(target_org uuid) returns boolean
language sql security definer stable set search_path = public as $$
  select exists (
    select 1 from public.org_members m
    where m.org_id = target_org and m.user_id = auth.uid()
      and m.role in ('owner','admin','growth_head')
  );
$$;

-- profiles: a user sees/edits only their own row
drop policy if exists profiles_self on public.profiles;
create policy profiles_self on public.profiles
  using (id = auth.uid()) with check (id = auth.uid());

-- orgs: members can read their orgs; managers can update
drop policy if exists orgs_read on public.orgs;
create policy orgs_read on public.orgs for select using (public.is_member(id));
drop policy if exists orgs_update on public.orgs;
create policy orgs_update on public.orgs for update using (public.is_manager(id)) with check (public.is_manager(id));

-- org_members: a user can see membership rows for orgs they belong to
drop policy if exists members_read on public.org_members;
create policy members_read on public.org_members for select using (public.is_member(org_id));

-- brands: full CRUD limited to the owning org (THE isolation boundary)
drop policy if exists brands_select on public.brands;
create policy brands_select on public.brands for select using (public.is_member(org_id));
drop policy if exists brands_write on public.brands;
create policy brands_write on public.brands for all
  using (public.is_member(org_id)) with check (public.is_member(org_id));

-- brand_scans: reachable only through a brand the user's org owns
drop policy if exists scans_all on public.brand_scans;
create policy scans_all on public.brand_scans for all
  using (exists (select 1 from public.brands b where b.id = brand_id and public.is_member(b.org_id)))
  with check (exists (select 1 from public.brands b where b.id = brand_id and public.is_member(b.org_id)));

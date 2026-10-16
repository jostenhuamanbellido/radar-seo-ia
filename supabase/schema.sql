-- Cítame · esquema de base de datos (Supabase / Postgres)
-- Ejecutar una vez en Supabase > SQL Editor.
-- Todas las tablas tienen RLS activado y SIN políticas: solo el backend (service_role) accede.

create table if not exists public.profiles (
  user_id uuid primary key references auth.users (id) on delete cascade,
  email text,
  plan text not null default 'free' check (plan in ('free', 'negocio', 'agencia')),
  agency_name text,
  country text default 'pe',
  created_at timestamptz not null default now()
);

create table if not exists public.sites (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (user_id) on delete cascade,
  url text not null,
  domain text not null,
  brand text,
  service text,
  city text,
  country text not null default 'pe',
  queries text[] not null default '{}',
  last_audit_at timestamptz,
  last_score int,
  created_at timestamptz not null default now()
);
create index if not exists sites_user_idx on public.sites (user_id);

create table if not exists public.audits (
  id bigint generated always as identity primary key,
  public_id text not null unique default replace(gen_random_uuid()::text, '-', ''),
  site_id uuid references public.sites (id) on delete cascade,
  user_id uuid references public.profiles (user_id) on delete cascade,
  url text,
  domain text,
  total int, local int, geo int, aeo int, ai int,
  data jsonb,
  created_at timestamptz not null default now()
);
create index if not exists audits_site_idx on public.audits (site_id, created_at desc);
create index if not exists audits_user_idx on public.audits (user_id, created_at desc);

create table if not exists public.rankings (
  id bigint generated always as identity primary key,
  country text not null,
  city text not null,
  category text not null,
  slug text not null,
  data jsonb not null,
  updated_at timestamptz not null default now(),
  unique (country, slug)
);

create table if not exists public.leads (
  id bigint generated always as identity primary key,
  email text not null,
  plan text,
  country text,
  note text,
  created_at timestamptz not null default now()
);

create table if not exists public.rate_limits (
  key text not null,
  day date not null,
  count int not null default 0,
  primary key (key, day)
);

alter table public.profiles enable row level security;
alter table public.sites enable row level security;
alter table public.audits enable row level security;
alter table public.rankings enable row level security;
alter table public.leads enable row level security;
alter table public.rate_limits enable row level security;

-- Crea el perfil automáticamente cuando alguien se registra
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (user_id, email) values (new.id, new.email)
  on conflict (user_id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Para activar un plan de pago a mano:
--   update public.profiles set plan = 'negocio' where email = 'cliente@correo.com';

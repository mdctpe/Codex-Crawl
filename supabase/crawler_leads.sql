create table if not exists public.crawler_leads (
  lead_id text primary key,
  source_tag text not null,
  region text,
  permit_number text,
  project_name text,
  developer_name text,
  architect_name text,
  constructor_name text,
  site_address text,
  construction_cost bigint,
  permit_issued_at date,
  usage text,
  land_use_zoning text,
  gcis_company_name text,
  gcis_business_no text,
  gcis_company_status text,
  gcis_responsible_name text,
  gcis_company_location text,
  google_maps_name text,
  google_maps_address text,
  google_maps_place_id text,
  google_maps_url text,
  tracking_status text not null default '未處理',
  tracking_owner text,
  tracking_next_action_date date,
  tracking_note text,
  tracking_updated_at timestamptz,
  tracking_updated_by_email text,
  last_crawled_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists crawler_leads_source_tag_idx
  on public.crawler_leads (source_tag);

create index if not exists crawler_leads_permit_issued_at_idx
  on public.crawler_leads (permit_issued_at desc);

create index if not exists crawler_leads_construction_cost_idx
  on public.crawler_leads (construction_cost desc);

create or replace function public.set_crawler_leads_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

drop trigger if exists set_crawler_leads_updated_at on public.crawler_leads;

create trigger set_crawler_leads_updated_at
before update on public.crawler_leads
for each row
execute function public.set_crawler_leads_updated_at();

alter table public.crawler_leads enable row level security;

drop policy if exists "eonian members can read crawler leads" on public.crawler_leads;
create policy "eonian members can read crawler leads"
on public.crawler_leads
for select
to authenticated
using (
  lower(coalesce(auth.jwt() ->> 'email', '')) like '%@eonian.space'
);

drop policy if exists "eonian members can update crawler leads" on public.crawler_leads;
create policy "eonian members can update crawler leads"
on public.crawler_leads
for update
to authenticated
using (
  lower(coalesce(auth.jwt() ->> 'email', '')) like '%@eonian.space'
)
with check (
  lower(coalesce(auth.jwt() ->> 'email', '')) like '%@eonian.space'
);

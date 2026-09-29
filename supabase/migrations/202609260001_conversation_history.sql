-- Durable, tenant-isolated conversation history for authenticated users.
--
-- The API must use the caller's Supabase JWT (or a tightly scoped server-side
-- operation) when it is wired to these tables. Never expose the service-role
-- key to a browser: service_role bypasses row-level security.

create extension if not exists pgcrypto with schema extensions;

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table public.profiles (
  user_id uuid primary key references auth.users (id) on delete cascade,
  display_name text,
  locale text not null default 'en',
  timezone text not null default 'UTC',
  preferences jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profiles_display_name_check check (
    display_name is null
    or (
      char_length(btrim(display_name)) between 1 and 100
      and display_name = btrim(display_name)
    )
  ),
  constraint profiles_locale_check check (
    locale ~ '^[A-Za-z]{2,3}([_-][A-Za-z0-9]{2,8})*$'
  ),
  constraint profiles_timezone_check check (
    char_length(btrim(timezone)) between 1 and 100
    and timezone = btrim(timezone)
  ),
  constraint profiles_preferences_object_check check (
    jsonb_typeof(preferences) = 'object'
    and octet_length(preferences::text) <= 16384
  ),
  constraint profiles_timestamps_check check (updated_at >= created_at)
);

create table public.conversations (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.profiles (user_id) on delete cascade,
  title text,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_message_at timestamptz,
  constraint conversations_id_owner_key unique (id, owner_id),
  constraint conversations_title_check check (
    title is null
    or (
      char_length(btrim(title)) between 1 and 160
      and title = btrim(title)
    )
  ),
  constraint conversations_status_check check (status in ('active', 'archived')),
  constraint conversations_timestamps_check check (
    updated_at >= created_at
    and (last_message_at is null or last_message_at >= created_at)
  )
);

create table public.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null,
  owner_id uuid not null,
  role text not null,
  content text not null,
  request_id uuid,
  client_message_id uuid,
  model text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint messages_conversation_owner_fkey
    foreign key (conversation_id, owner_id)
    references public.conversations (id, owner_id)
    on delete cascade,
  constraint messages_id_conversation_owner_key
    unique (id, conversation_id, owner_id),
  constraint messages_role_check check (role in ('user', 'assistant', 'system')),
  constraint messages_content_check check (
    char_length(btrim(content)) between 1 and 20000
  ),
  constraint messages_model_check check (
    model is null
    or (
      char_length(btrim(model)) between 1 and 200
      and model = btrim(model)
    )
  ),
  constraint messages_metadata_object_check check (
    jsonb_typeof(metadata) = 'object'
    and octet_length(metadata::text) <= 32768
  )
);

create table public.conversation_summaries (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null,
  owner_id uuid not null,
  through_message_id uuid not null,
  revision integer not null,
  source_message_count integer not null,
  summary text not null,
  model text not null,
  prompt_version text not null,
  created_at timestamptz not null default now(),
  constraint conversation_summaries_conversation_owner_fkey
    foreign key (conversation_id, owner_id)
    references public.conversations (id, owner_id)
    on delete cascade,
  constraint conversation_summaries_through_message_fkey
    foreign key (through_message_id, conversation_id, owner_id)
    references public.messages (id, conversation_id, owner_id)
    on delete cascade,
  constraint conversation_summaries_revision_check check (revision > 0),
  constraint conversation_summaries_source_count_check check (
    source_message_count > 0
  ),
  constraint conversation_summaries_summary_check check (
    char_length(btrim(summary)) between 1 and 8000
  ),
  constraint conversation_summaries_model_check check (
    char_length(btrim(model)) between 1 and 200
    and model = btrim(model)
  ),
  constraint conversation_summaries_prompt_version_check check (
    char_length(btrim(prompt_version)) between 1 and 100
    and prompt_version = btrim(prompt_version)
  ),
  constraint conversation_summaries_conversation_revision_key
    unique (conversation_id, revision),
  constraint conversation_summaries_conversation_through_message_key
    unique (conversation_id, through_message_id)
);

-- Foreign keys are not indexed automatically. These indexes also support the
-- expected owner-scoped, keyset-paginated history reads and RLS predicates.
create index conversations_owner_updated_id_idx
  on public.conversations (owner_id, updated_at desc, id desc);

create index messages_conversation_owner_created_id_idx
  on public.messages (conversation_id, owner_id, created_at, id);

create index messages_owner_created_id_idx
  on public.messages (owner_id, created_at desc, id desc);

create index messages_request_id_idx
  on public.messages (request_id)
  where request_id is not null;

create unique index messages_owner_client_message_key
  on public.messages (owner_id, client_message_id)
  where client_message_id is not null;

create index conversation_summaries_conversation_owner_created_idx
  on public.conversation_summaries (
    conversation_id,
    owner_id,
    created_at desc,
    id desc
  );

create index conversation_summaries_owner_created_id_idx
  on public.conversation_summaries (owner_id, created_at desc, id desc);

create index conversation_summaries_through_message_idx
  on public.conversation_summaries (
    through_message_id,
    conversation_id,
    owner_id
  );

create or replace function private.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

revoke execute on function private.set_updated_at() from public, anon, authenticated;

create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function private.set_updated_at();

create trigger conversations_set_updated_at
before update on public.conversations
for each row execute function private.set_updated_at();

create or replace function private.touch_conversation_after_message()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  update public.conversations
  set last_message_at = greatest(
        coalesce(last_message_at, new.created_at),
        new.created_at
      )
  where id = new.conversation_id and owner_id = new.owner_id;
  return new;
end;
$$;

revoke execute on function private.touch_conversation_after_message()
  from public, anon, authenticated;

create trigger messages_touch_conversation
after insert on public.messages
for each row execute function private.touch_conversation_after_message();

create or replace function private.create_profile_for_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (user_id) values (new.id)
  on conflict (user_id) do nothing;
  return new;
end;
$$;

revoke execute on function private.create_profile_for_new_user()
  from public, anon, authenticated;

create trigger auth_user_created_profile
after insert on auth.users
for each row execute function private.create_profile_for_new_user();

-- Backfill profiles when this migration is applied to a project that already
-- has authenticated users.
insert into public.profiles (user_id)
select id from auth.users
on conflict (user_id) do nothing;

alter table public.profiles enable row level security;
alter table public.conversations enable row level security;
alter table public.messages enable row level security;
alter table public.conversation_summaries enable row level security;

create policy profiles_select_own
on public.profiles for select to authenticated
using ((select auth.uid()) = user_id);

create policy profiles_insert_own
on public.profiles for insert to authenticated
with check ((select auth.uid()) = user_id);

create policy profiles_update_own
on public.profiles for update to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy conversations_select_own
on public.conversations for select to authenticated
using ((select auth.uid()) = owner_id);

create policy conversations_insert_own
on public.conversations for insert to authenticated
with check ((select auth.uid()) = owner_id);

create policy conversations_update_own
on public.conversations for update to authenticated
using ((select auth.uid()) = owner_id)
with check ((select auth.uid()) = owner_id);

create policy conversations_delete_own
on public.conversations for delete to authenticated
using ((select auth.uid()) = owner_id);

create policy messages_select_own
on public.messages for select to authenticated
using ((select auth.uid()) = owner_id);

-- Authenticated clients may append their own user messages. Assistant and
-- system records are written only by the trusted backend (service_role).
create policy messages_insert_own_user_message
on public.messages for insert to authenticated
with check ((select auth.uid()) = owner_id and role = 'user');

create policy conversation_summaries_select_own
on public.conversation_summaries for select to authenticated
using ((select auth.uid()) = owner_id);

revoke all on public.profiles from anon, authenticated;
revoke all on public.conversations from anon, authenticated;
revoke all on public.messages from anon, authenticated;
revoke all on public.conversation_summaries from anon, authenticated;

grant select on public.profiles to authenticated;
grant insert (user_id, display_name, locale, timezone, preferences)
  on public.profiles to authenticated;
grant update (display_name, locale, timezone, preferences)
  on public.profiles to authenticated;

grant select, delete on public.conversations to authenticated;
grant insert (id, owner_id, title, status)
  on public.conversations to authenticated;
grant update (title, status)
  on public.conversations to authenticated;

grant select on public.messages to authenticated;
grant insert (
  id,
  conversation_id,
  owner_id,
  role,
  content,
  request_id,
  client_message_id,
  metadata
) on public.messages to authenticated;
grant select on public.conversation_summaries to authenticated;

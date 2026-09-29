# Supabase setup

Gita Guide uses Supabase only for optional authentication and durable history.
Guest and offline conversations are not written to Supabase.

## Recommended: tracked migration workflow

Run these commands from the repository root. The first command is needed because
the repository already contains migrations but does not yet contain the CLI-generated
`supabase/config.toml`.

```bash
supabase init
supabase login
supabase link --project-ref YOUR_PROJECT_REF
supabase db push --dry-run
supabase db push
```

Find `YOUR_PROJECT_REF` in the project URL:
`https://supabase.com/dashboard/project/YOUR_PROJECT_REF`.

The push applies
`supabase/migrations/202609260001_conversation_history.sql`. It creates:

- `profiles`
- `conversations`
- `messages`
- `conversation_summaries`
- ownership indexes, timestamp/profile triggers, least-privilege grants, and ten
  row-level-security policies

Review the dry-run output before applying it. Do not use `db reset --linked`; that
command deletes remote data.

For repeatable local RLS verification, start Docker and run:

```bash
supabase start
supabase test db
```

The pgTAP suite in `supabase/tests/database/history_rls.test.sql` runs in a
transaction and rolls its fixtures back.

## Dashboard fallback

Use this only if you do not want to install the CLI yet and the Supabase project is
new. In **SQL Editor**, create a new query, paste the complete contents of
`supabase/migrations/202609260001_conversation_history.sql`, and select **Run** once.
Do not subsequently run the initial `db push` without first reconciling migration
history, because the same schema would be applied twice.

After either installation method, this read-only query should show all four tables
with `rowsecurity = true`:

```sql
select tablename, rowsecurity
from pg_tables
where schemaname = 'public'
  and tablename in (
    'profiles',
    'conversations',
    'messages',
    'conversation_summaries'
  )
order by tablename;
```

This query should return `10`:

```sql
select count(*) as history_policy_count
from pg_policies
where schemaname = 'public'
  and tablename in (
    'profiles',
    'conversations',
    'messages',
    'conversation_summaries'
  );
```

## Authentication configuration

In **Authentication → URL Configuration**:

- Add `http://localhost:3000/auth/callback` as a local redirect URL.
- Add `http://localhost:3000/auth/callback?next=/reset-password` for local
  password recovery.
- When deployed, set **Site URL** to the exact production origin.
- Add `https://YOUR_DOMAIN/auth/callback` as an exact production redirect URL.
- Add `https://YOUR_DOMAIN/auth/callback?next=/reset-password` as the exact
  production password-recovery redirect URL.
- Add preview wildcard URLs only when previews need sign-in.

The web application needs these values in `web/.env` locally and in the frontend
Vercel project in production:

```text
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
```

The service-role key must remain server-only. Never expose it in a
`NEXT_PUBLIC_*` variable, browser bundle, log, or screenshot.

## Smoke test

Restart the Next.js server after setting environment variables. Then:

1. Open `/login` and sign in with a confirmed test account.
2. Confirm successful sign-in returns to `/` and shows private history as
   enabled.
3. Send one message while signed in.
4. Refresh the page and confirm the conversation remains visible.
5. Sign out and confirm the authenticated conversation is not visible.
6. From `/login`, request password recovery and confirm the emailed link opens
   `/reset-password` through `/auth/callback`.

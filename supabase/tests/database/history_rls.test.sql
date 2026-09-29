begin;

create extension if not exists pgtap with schema extensions;

select plan(17);

select is(
  (
    select count(*)::integer
    from pg_class
    where oid in (
      'public.profiles'::regclass,
      'public.conversations'::regclass,
      'public.messages'::regclass,
      'public.conversation_summaries'::regclass
    )
    and relrowsecurity
  ),
  4,
  'RLS is enabled on every user-history table'
);

select is(
  (
    select count(*)::integer
    from pg_policies
    where schemaname = 'public'
      and tablename in (
        'profiles',
        'conversations',
        'messages',
        'conversation_summaries'
      )
  ),
  10,
  'all expected ownership policies exist'
);

insert into auth.users (id, email)
values
  ('11111111-1111-4111-8111-111111111111', 'history-owner@example.test'),
  ('22222222-2222-4222-8222-222222222222', 'history-intruder@example.test');

insert into public.conversations (id, owner_id, title)
values
  (
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1',
    '11111111-1111-4111-8111-111111111111',
    'Owner conversation'
  ),
  (
    'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1',
    '22222222-2222-4222-8222-222222222222',
    'Intruder conversation'
  );

insert into public.messages (
  id,
  conversation_id,
  owner_id,
  role,
  content
)
values
  (
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2',
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1',
    '11111111-1111-4111-8111-111111111111',
    'user',
    'I am worried about the result.'
  ),
  (
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3',
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1',
    '11111111-1111-4111-8111-111111111111',
    'assistant',
    'Focus on the action that is yours to take.'
  ),
  (
    'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb2',
    'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1',
    '22222222-2222-4222-8222-222222222222',
    'user',
    'This belongs to another user.'
  );

insert into public.conversation_summaries (
  conversation_id,
  owner_id,
  through_message_id,
  revision,
  source_message_count,
  summary,
  model,
  prompt_version
)
values
  (
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1',
    '11111111-1111-4111-8111-111111111111',
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3',
    1,
    2,
    'The user is anxious about an outcome and was encouraged to focus on action.',
    'test-summary-model',
    'summary-v1'
  ),
  (
    'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1',
    '22222222-2222-4222-8222-222222222222',
    'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb2',
    1,
    1,
    'Another user summary.',
    'test-summary-model',
    'summary-v1'
  );

set local role authenticated;
set local "request.jwt.claim.sub" = '11111111-1111-4111-8111-111111111111';
set local "request.jwt.claims" = '{"sub":"11111111-1111-4111-8111-111111111111","role":"authenticated"}';

select is(
  (select count(*) from public.profiles),
  1::bigint,
  'a user can see only their own profile'
);

select is(
  (
    select count(*)
    from public.profiles
    where user_id = '22222222-2222-4222-8222-222222222222'
  ),
  0::bigint,
  'another profile is hidden'
);

select is(
  (select count(*) from public.conversations),
  1::bigint,
  'a user can see only their own conversation'
);

select is(
  (
    select count(*)
    from public.conversations
    where id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1'
  ),
  0::bigint,
  'another conversation is hidden'
);

select is(
  (select count(*) from public.messages),
  2::bigint,
  'a user can see only messages in their ownership boundary'
);

select is(
  (select count(*) from public.conversation_summaries),
  1::bigint,
  'a user can see only their own summaries'
);

select lives_ok(
  $$
    insert into public.conversations (id, owner_id, title)
    values (
      'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa4',
      '11111111-1111-4111-8111-111111111111',
      'New owned conversation'
    )
  $$,
  'a user can create their own conversation'
);

select throws_ok(
  $$
    insert into public.conversations (id, owner_id, title)
    values (
      'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa5',
      '22222222-2222-4222-8222-222222222222',
      'Forbidden conversation'
    )
  $$,
  '42501',
  null,
  'a user cannot create a conversation for another owner'
);

select lives_ok(
  $$
    insert into public.messages (
      id, conversation_id, owner_id, role, content
    ) values (
      'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa6',
      'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1',
      '11111111-1111-4111-8111-111111111111',
      'user',
      'An appended user message.'
    )
  $$,
  'a user can append a user-role message to their conversation'
);

select throws_ok(
  $$
    insert into public.messages (
      id, conversation_id, owner_id, role, content
    ) values (
      'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa7',
      'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1',
      '11111111-1111-4111-8111-111111111111',
      'assistant',
      'A forged assistant message.'
    )
  $$,
  '42501',
  null,
  'a browser user cannot forge assistant history'
);

select throws_ok(
  $$
    insert into public.messages (
      id, conversation_id, owner_id, role, content
    ) values (
      'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa8',
      'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1',
      '11111111-1111-4111-8111-111111111111',
      'user',
      'A cross-tenant message.'
    )
  $$,
  '23503',
  null,
  'the composite foreign key blocks cross-tenant message attachment'
);

select throws_ok(
  $$
    update public.messages
    set content = 'Rewritten history.'
    where id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2'
  $$,
  '42501',
  null,
  'authenticated users cannot rewrite message history'
);

select throws_ok(
  $$
    insert into public.conversation_summaries (
      conversation_id,
      owner_id,
      through_message_id,
      revision,
      source_message_count,
      summary,
      model,
      prompt_version
    ) values (
      'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1',
      '11111111-1111-4111-8111-111111111111',
      'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3',
      2,
      3,
      'A forged summary.',
      'forged-model',
      'summary-v1'
    )
  $$,
  '42501',
  null,
  'only the trusted backend can write summaries'
);

select lives_ok(
  $$
    update public.profiles
    set display_name = 'Arjuna'
    where user_id = '11111111-1111-4111-8111-111111111111'
  $$,
  'a user can update approved profile fields'
);

select throws_ok(
  $$
    update public.profiles
    set created_at = now()
    where user_id = '11111111-1111-4111-8111-111111111111'
  $$,
  '42501',
  null,
  'a user cannot rewrite immutable profile fields'
);

select * from finish();

rollback;

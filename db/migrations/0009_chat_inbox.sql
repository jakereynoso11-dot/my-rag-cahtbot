-- Adds what the admin inbox needs on top of chat_sessions: which sessions
-- came from a visitor on the public share link (vs. the owner testing their
-- own chatbot from the dashboard), and enough denormalized state to render
-- an inbox list (last activity, a preview, an unread flag) without a
-- per-row messages query.
--
-- Run this once in the Powabase Studio SQL editor.

alter table public.chat_sessions
    add column if not exists origin text not null default 'owner'
        check (origin in ('owner', 'public'));

alter table public.chat_sessions
    add column if not exists last_message_at timestamptz;

alter table public.chat_sessions
    add column if not exists last_message_preview text;

alter table public.chat_sessions
    add column if not exists unread boolean not null default false;

-- Backfill last_message_at for sessions created before this migration from
-- their existing messages, so older conversations still sort correctly.
update public.chat_sessions cs
set last_message_at = latest.max_created_at
from (
    select session_id, max(created_at) as max_created_at
    from public.messages
    group by session_id
) latest
where latest.session_id = cs.id
  and cs.last_message_at is null;

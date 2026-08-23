-- Public chat link: every chatbot gets a random, unguessable share_token.
-- Anyone with the link (/chat/<share_token> in the frontend) can chat with
-- it without a Powabase login. The backend resolves the chatbot by this
-- token using the service role key (see app/api/routes/public_chat.py), so
-- no RLS policy changes are needed -- the public routes never use a
-- visitor's own JWT because visitors don't have one.
--
-- Run this once in the Powabase Studio SQL editor.

alter table public.chatbots
    add column if not exists share_token uuid not null default gen_random_uuid();

create unique index if not exists chatbots_share_token_idx
    on public.chatbots (share_token);

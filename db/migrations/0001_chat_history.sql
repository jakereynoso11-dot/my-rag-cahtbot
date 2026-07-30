-- Adds chat session/message history on top of the existing chatbots /
-- documents / chatbot_documents schema. Scoped by chatbot_id, using the
-- existing user_has_chatbot_access() helper, matching the conventions of
-- the schema already in this project.
--
-- Run this once in the Powabase Studio SQL editor.

create table if not exists public.chat_sessions (
    id uuid primary key default gen_random_uuid(),
    chatbot_id uuid not null references public.chatbots (id) on delete cascade,
    powabase_session_id text,
    title text,
    created_at timestamptz not null default now()
);

alter table public.chat_sessions enable row level security;

create policy "chat_sessions_select" on public.chat_sessions
    for select using (user_has_chatbot_access(chatbot_id));

create policy "chat_sessions_insert" on public.chat_sessions
    for insert with check (user_has_chatbot_access(chatbot_id));

create policy "chat_sessions_update" on public.chat_sessions
    for update using (user_has_chatbot_access(chatbot_id));

create table if not exists public.messages (
    id uuid primary key default gen_random_uuid(),
    session_id uuid not null references public.chat_sessions (id) on delete cascade,
    role text not null check (role in ('user', 'assistant')),
    content text not null,
    created_at timestamptz not null default now()
);

alter table public.messages enable row level security;

create policy "messages_select" on public.messages
    for select using (
        exists (
            select 1 from public.chat_sessions cs
            where cs.id = messages.session_id and user_has_chatbot_access(cs.chatbot_id)
        )
    );

create policy "messages_insert" on public.messages
    for insert with check (
        exists (
            select 1 from public.chat_sessions cs
            where cs.id = messages.session_id and user_has_chatbot_access(cs.chatbot_id)
        )
    );

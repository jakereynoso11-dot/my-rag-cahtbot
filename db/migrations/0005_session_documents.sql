-- Lets a single chat session have its own private documents, separate from
-- the chatbot's shared knowledge base. A session that has its own documents
-- gets its own dedicated Powabase agent (mirroring how specialists work),
-- and chat requests for that session answer through it instead of the
-- chatbot's shared agent or a specialist -- so a document uploaded to one
-- conversation never leaks into another conversation or the chatbot's
-- general knowledge.
--
-- Run this once in the Powabase Studio SQL editor.

alter table public.chat_sessions add column if not exists powabase_agent_id text;

create table if not exists public.chat_session_documents (
    id uuid primary key default gen_random_uuid(),
    session_id uuid not null references public.chat_sessions (id) on delete cascade,
    document_id uuid not null references public.documents (id) on delete cascade,
    display_name text,
    created_at timestamptz not null default now()
);

alter table public.chat_session_documents enable row level security;

create policy "chat_session_documents_select" on public.chat_session_documents
    for select using (
        exists (
            select 1 from public.chat_sessions cs
            where cs.id = chat_session_documents.session_id
              and user_has_chatbot_access(cs.chatbot_id)
        )
    );

create policy "chat_session_documents_insert" on public.chat_session_documents
    for insert with check (
        exists (
            select 1 from public.chat_sessions cs
            where cs.id = chat_session_documents.session_id
              and user_has_chatbot_access(cs.chatbot_id)
        )
    );

create policy "chat_session_documents_delete" on public.chat_session_documents
    for delete using (
        exists (
            select 1 from public.chat_sessions cs
            where cs.id = chat_session_documents.session_id
              and user_has_chatbot_access(cs.chatbot_id)
        )
    );

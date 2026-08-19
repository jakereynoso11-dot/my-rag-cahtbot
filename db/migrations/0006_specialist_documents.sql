-- Lets a specialist have its own private documents, on top of whatever the
-- parent chatbot already shares with it. Uploading a document here trains
-- just that one specialist -- it links the document's knowledge base only
-- to the specialist's own Powabase agent, not the chatbot or sibling
-- specialists.
--
-- Run this once in the Powabase Studio SQL editor.

create table if not exists public.specialist_documents (
    id uuid primary key default gen_random_uuid(),
    specialist_id uuid not null references public.chatbot_specialists (id) on delete cascade,
    document_id uuid not null references public.documents (id) on delete cascade,
    display_name text,
    created_at timestamptz not null default now()
);

alter table public.specialist_documents enable row level security;

create policy "specialist_documents_select" on public.specialist_documents
    for select using (
        exists (
            select 1 from public.chatbot_specialists sp
            where sp.id = specialist_documents.specialist_id
              and user_has_chatbot_access(sp.chatbot_id)
        )
    );

create policy "specialist_documents_insert" on public.specialist_documents
    for insert with check (
        exists (
            select 1 from public.chatbot_specialists sp
            where sp.id = specialist_documents.specialist_id
              and user_has_chatbot_access(sp.chatbot_id)
        )
    );

create policy "specialist_documents_delete" on public.specialist_documents
    for delete using (
        exists (
            select 1 from public.chatbot_specialists sp
            where sp.id = specialist_documents.specialist_id
              and user_has_chatbot_access(sp.chatbot_id)
        )
    );

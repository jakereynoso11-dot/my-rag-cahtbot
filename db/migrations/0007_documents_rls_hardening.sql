-- Documents are deduplicated globally by content hash (register_or_get_document),
-- so the same `documents` row/Powabase KB can be reused across different
-- users who happen to upload byte-identical files. That reuse is not itself
-- a leak (nothing new is exposed beyond content the user already has), but
-- the `public.documents` table predates this migration folder -- it was
-- created directly in Studio -- so its own row-level security has never
-- been verified here.
--
-- This migration makes the SELECT policy explicit and defensive: a user may
-- only read a `documents` row through one of the three ownership-scoped join
-- tables (chatbot_documents, chat_session_documents, specialist_documents --
-- the last one added by 0007_specialist_documents.sql). No policy grants a
-- bare, unscoped read of the whole table.
--
-- Safe to run even if a documents_select policy already exists (drops and
-- recreates it). Run this once in the Powabase Studio SQL editor -- after
-- 0006_specialist_documents.sql, since this policy references
-- specialist_documents.
--
-- Before running, it's worth sanity-checking what's already in place:
--   select policyname, cmd, qual from pg_policies where tablename = 'documents';
--   select prosrc from pg_proc where proname = 'user_has_chatbot_access';

alter table public.documents enable row level security;

drop policy if exists "documents_select" on public.documents;

create policy "documents_select" on public.documents
    for select using (
        exists (
            select 1 from public.chatbot_documents cd
            where cd.document_id = documents.id
              and user_has_chatbot_access(cd.chatbot_id)
        )
        or exists (
            select 1 from public.chat_session_documents csd
            join public.chat_sessions cs on cs.id = csd.session_id
            where csd.document_id = documents.id
              and user_has_chatbot_access(cs.chatbot_id)
        )
        or exists (
            select 1 from public.specialist_documents sd
            join public.chatbot_specialists sp on sp.id = sd.specialist_id
            where sd.document_id = documents.id
              and user_has_chatbot_access(sp.chatbot_id)
        )
    );

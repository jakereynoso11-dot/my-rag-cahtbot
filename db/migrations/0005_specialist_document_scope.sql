-- Lets a document be scoped to a single specialist instead of being shared
-- with every specialist under a chatbot. When chatbot_documents.specialist_id
-- is set, only that specialist's Powabase agent gets the document's
-- knowledge base attached (see app/services/document_ingestion.py); when
-- it's null, the document is shared with the parent chatbot and all of its
-- specialists, same as before this migration.
--
-- Run this once in the Powabase Studio SQL editor.

alter table public.chatbot_documents
    add column if not exists specialist_id uuid references public.chatbot_specialists (id) on delete cascade;

create index if not exists chatbot_documents_specialist_id_idx
    on public.chatbot_documents (specialist_id);

-- rename_chatbot already updates the owned "chatbots" table via the user's
-- own JWT, so an update policy on owned rows is an established pattern here;
-- chatbot_documents needs the same to let ingestion set specialist_id after
-- attach_document_to_chatbot() runs.
drop policy if exists "chatbot_documents_update" on public.chatbot_documents;
create policy "chatbot_documents_update" on public.chatbot_documents
    for update using (user_has_chatbot_access(chatbot_id));

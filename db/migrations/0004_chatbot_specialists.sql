-- Lets a chatbot have multiple specialist sub-agents underneath it (e.g. a
-- "Support Bot" chatbot with a Billing specialist and a Returns specialist).
-- Each specialist is its own Powabase agent, sharing the parent chatbot's
-- documents but with a narrower system prompt. Incoming chat messages are
-- auto-routed to the best-matching specialist when one exists (see
-- app/services/specialist_routing.py); otherwise the parent chatbot answers.
--
-- Run this once in the Powabase Studio SQL editor.

create table if not exists public.chatbot_specialists (
    id uuid primary key default gen_random_uuid(),
    chatbot_id uuid not null references public.chatbots (id) on delete cascade,
    name text not null,
    specialty text not null,
    powabase_agent_id text not null,
    created_at timestamptz not null default now()
);

alter table public.chatbot_specialists enable row level security;

create policy "chatbot_specialists_select" on public.chatbot_specialists
    for select using (user_has_chatbot_access(chatbot_id));

create policy "chatbot_specialists_insert" on public.chatbot_specialists
    for insert with check (user_has_chatbot_access(chatbot_id));

create policy "chatbot_specialists_delete" on public.chatbot_specialists
    for delete using (user_has_chatbot_access(chatbot_id));

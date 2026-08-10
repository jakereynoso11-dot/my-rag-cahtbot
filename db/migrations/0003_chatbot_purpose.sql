-- Adds a short "purpose" description to chatbots, separate from the
-- system_prompt (which lives only in Powabase, not in this table).
-- Shown in the agent creation form and the agents list.
--
-- Run this once in the Powabase Studio SQL editor.

alter table public.chatbots add column if not exists purpose text;

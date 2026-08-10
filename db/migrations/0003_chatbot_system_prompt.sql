-- Stores each chatbot's system prompt ("purpose") on the chatbots row itself.
-- Previously this text was only ever sent to Powabase when the agent was
-- created and never persisted anywhere the app could read it back, so the
-- frontend had no way to show a chatbot's stated purpose in the chatbots
-- table.
--
-- Run this once in the Powabase Studio SQL editor.

alter table public.chatbots add column if not exists system_prompt text;

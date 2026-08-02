-- Adds the missing DELETE policies for chat_sessions/messages so a user can
-- delete their own conversations. 0001_chat_history.sql only added
-- select/insert/update policies; without an explicit delete policy, RLS
-- denies DELETE by default even for the owning user.
--
-- Run this once in the Powabase Studio SQL editor.

create policy "chat_sessions_delete" on public.chat_sessions
    for delete using (user_has_chatbot_access(chatbot_id));

create policy "messages_delete" on public.messages
    for delete using (
        exists (
            select 1 from public.chat_sessions cs
            where cs.id = messages.session_id and user_has_chatbot_access(cs.chatbot_id)
        )
    );

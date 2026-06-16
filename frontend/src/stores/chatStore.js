import { create } from 'zustand';
import { streamMessage } from '../api';
import { fetchMessages } from '../services/chatService';
import useBrainstormStore from './brainstormStore';

const useChatStore = create((set, get) => ({
  // State
  messages: [],
  sending: false,
  chatError: '',
  streamAbort: null,

  // Internal refs (not reactive — for callbacks that need stable refs)
  _sending: false,

  // Actions

  loadMessages: async (brainstormId) => {
    const msgs = await fetchMessages(brainstormId);
    set({ messages: msgs });
    return msgs;
  },

  sendMessage: async (content) => {
    const brainstorm = useBrainstormStore.getState().activeBrainstorm;
    if (!brainstorm || get()._sending) return;

    get()._sending = true;
    set({ sending: true, chatError: '' });

    const userMsgId = Date.now().toString();
    const thinkingMessageId = `thinking-${userMsgId}`;

    const userMsg = {
      id: userMsgId,
      brainstorm_id: brainstorm.id,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };

    set((s) => ({
      messages: [
        ...s.messages,
        userMsg,
        {
          id: thinkingMessageId,
          brainstorm_id: brainstorm.id,
          role: 'assistant',
          content: '',
          isThinking: true,
          isStreaming: true,
          created_at: new Date().toISOString(),
        },
      ],
    }));

    let streamedContent = '';
    let firstToken = true;

    const controller = streamMessage(
      { brainstorm_id: brainstorm.id, message: content },
      {
        onToken: (token) => {
          streamedContent += token;
          set((s) => ({
            messages: s.messages.map((msg) =>
              msg.id === thinkingMessageId
                ? { ...msg, content: streamedContent, isThinking: firstToken }
                : msg
            ),
          }));
          firstToken = false;
        },

        onDone: () => {
          set((s) => ({
            messages: s.messages.map((msg) =>
              msg.id === thinkingMessageId
                ? { ...msg, isThinking: false, isStreaming: false }
                : msg
            ),
            sending: false,
            streamAbort: null,
          }));
          get()._sending = false;
          useBrainstormStore.getState().loadList();
        },

        onError: (error) => {
          set((s) => ({
            messages: s.messages.filter((msg) => msg.id !== thinkingMessageId),
            chatError: error,
            sending: false,
            streamAbort: null,
          }));
          get()._sending = false;
        },
      }
    );

    set({ streamAbort: controller });
  },

  abortStream: () => {
    const controller = get().streamAbort;
    if (controller) {
      controller.abort();
      set({ streamAbort: null, sending: false });
      get()._sending = false;
    }
  },

  clear: () => {
    get().abortStream();
    set({ messages: [], sending: false, chatError: '', streamAbort: null });
  },
}));

export default useChatStore;

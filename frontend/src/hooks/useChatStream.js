import { useState, useCallback } from 'react';

/**
 * Advanced Chat Streaming Hook 🚀
 * Handles real-time server-sent events for AI responses.
 */
export const useChatStream = (contextUrl) => {
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);

  // Send a message + handle streaming chunks
  const sendMessage = useCallback(async (query) => {
    const userMsg = { role: 'user', content: query };
    setMessages(prev => [...prev, userMsg]);
    setIsTyping(true);

    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1/chatbot';

    try {
      const response = await fetch(`${baseUrl}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query: query, 
          context_url: contextUrl 
        })
      });

      if (!response.ok) throw new Error('Stream connection failed');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let accumulatedContent = '';
      let aiMessageAdded = false;

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const data = JSON.parse(line);
              
              if (!aiMessageAdded) {
                setMessages(prev => [...prev, { role: 'ai', content: '', status: '', sources: [] }]);
                aiMessageAdded = true;
              }
              
              if (data.type === 'status') {
                setMessages(prev => {
                  const newMsgs = [...prev];
                  newMsgs[newMsgs.length - 1].status = data.content;
                  return newMsgs;
                });
              } else if (data.type === 'metadata') {
                setMessages(prev => {
                  const newMsgs = [...prev];
                  newMsgs[newMsgs.length - 1].sources = data.sources;
                  return newMsgs;
                });
              } else if (data.type === 'token') {
                accumulatedContent += data.content;
                setMessages(prev => {
                  const newMsgs = [...prev];
                  newMsgs[newMsgs.length - 1].content = accumulatedContent;
                  return newMsgs;
                });
              }
            } catch (err) {
              console.error("Partial JSON parse error:", err);
            }
          }
        }
      }

      // 4. CLEAR STATUS ON COMPLETION ✅
      // Once the stream is done, we remove the 'Thinking' bar so the response looks clean.
      setMessages(prev => {
        const newMsgs = [...prev];
        if (newMsgs.length > 0) {
          newMsgs[newMsgs.length - 1].status = null;
        }
        return newMsgs;
      });

    } catch (error) {
      console.error("AI stream error:", error);
      setMessages(prev => [...prev, { 
        role: 'ai', 
        content: "Sorry, I lost the connection to the thinking engine.", 
        sources: [] 
      }]);
    } finally {
      setIsTyping(false);
    }
  }, [contextUrl]);

  // Utility to inject a Swoop Card into the chat flow
  const addSwoopCard = useCallback((taskId) => {
    setMessages(prev => [...prev, { role: 'swoop', taskId }]);
  }, []);

  return { 
    messages, 
    setMessages, 
    isTyping, 
    sendMessage, 
    addSwoopCard 
  };
};

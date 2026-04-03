import { useState, useCallback, useRef, useEffect } from 'react';

/**
 * Advanced Chat Streaming Hook 🚀
 * Now with persistent Memorization and Session Tracking.
 */
export const useChatStream = (contextUrl) => {
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  const [sessionId, setSessionId] = useState(localStorage.getItem('swoop_session_id') || '');
  const controllerRef = useRef(null);

  // Initialize Session ID on first load
  useEffect(() => {
    if (!sessionId) {
      const newId = `session_${Math.random().toString(36).substring(2, 15)}_${Date.now()}`;
      setSessionId(newId);
      localStorage.setItem('swoop_session_id', newId);
    }
  }, [sessionId]);

  // Stop the current streaming session
  const stopStreaming = useCallback(() => {
    if (controllerRef.current) {
      controllerRef.current.abort();
      controllerRef.current = null;
      setIsTyping(false);
      
      setMessages(prev => {
        const newMsgs = [...prev];
        if (newMsgs.length > 0 && newMsgs[newMsgs.length - 1].role === 'ai') {
          newMsgs[newMsgs.length - 1].status = null;
        }
        return newMsgs;
      });
    }
  }, []);

  // Wipe chat history locally and in Redis
  const clearHistory = useCallback(async () => {
    setMessages([]);
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1/chatbot';
    
    // Tell backend to wipe Redis session
    try {
      await fetch(`${baseUrl}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query: "RESET_HISTORY", 
          session_id: sessionId,
          clear_history: true 
        })
      });
    } catch (e) {
      console.warn("Could not sync history clear with server:", e);
    }
  }, [sessionId]);

  // Send a message + handle streaming chunks
  const sendMessage = useCallback(async (query) => {
    if (controllerRef.current) controllerRef.current.abort();
    controllerRef.current = new AbortController();

    const userMsg = { role: 'user', content: query };
    setMessages(prev => [...prev, userMsg]);
    setIsTyping(true);

    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1/chatbot';

    try {
      const response = await fetch(`${baseUrl}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controllerRef.current.signal,
        body: JSON.stringify({ 
          query: query, 
          session_id: sessionId,
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

      setMessages(prev => {
        const newMsgs = [...prev];
        if (newMsgs.length > 0) {
          newMsgs[newMsgs.length - 1].status = null;
        }
        return newMsgs;
      });

    } catch (error) {
      if (error.name === 'AbortError') {
        console.log("Stream stopped by user.");
      } else {
        console.error("AI stream error:", error);
        setMessages(prev => [...prev, { 
          role: 'ai', 
          content: "Sorry, I lost the connection to the thinking engine.", 
          sources: [] 
        }]);
      }
    } finally {
      setIsTyping(false);
      controllerRef.current = null;
    }
  }, [contextUrl, sessionId]);

  const addSwoopCard = useCallback((taskId, url) => {
    setMessages(prev => [...prev, { role: 'swoop', taskId, url }]);
  }, []);

  return { 
    messages, 
    setMessages, 
    sessionId,
    isTyping, 
    sendMessage, 
    clearHistory,
    addSwoopCard,
    stopStreaming 
  };
};

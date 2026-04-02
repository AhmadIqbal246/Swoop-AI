import React, { useState, useRef, useEffect, useCallback } from 'react';
import { chatService } from '../../services/api';
import SwoopDiscoveryCard from './SwoopDiscoveryCard';

const ChatInterface = ({ taskState, setTaskState }) => {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  const scrollRef = useRef(null);

  const PROCESSING_STATES = ['PENDING', 'PROGRESS', 'STARTING'];
  const isActivelyProcessing = taskState?.taskId && PROCESSING_STATES.includes(taskState?.status);
  const isKnowledgeReady = !isActivelyProcessing;

  const getSafeHostname = (urlStr) => {
    try { return new URL(urlStr).hostname; } catch { return "the site"; }
  };

  const getSafePathname = (urlStr) => {
    try { return new URL(urlStr).pathname; } catch { return "/"; }
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping, taskState, isKnowledgeReady]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!query.trim() || !isKnowledgeReady) return;

    const userMsg = { role: 'user', content: query };
    setMessages(prev => [...prev, userMsg]);
    setQuery('');
    setIsTyping(true);

    try {
      const data = await chatService.sendMessage(query, taskState?.url);
      const aiMsg = { 
        role: 'ai', 
        content: data.answer, 
        sources: data.sources || [] 
      };
      setMessages(prev => [...prev, aiMsg]);
    } catch (error) {
      console.error("Chat error:", error);
    } finally {
      setIsTyping(false);
    }
  };

  const handleDiscoveryComplete = useCallback((pagesCount) => {
    setTaskState(prev => ({
      ...prev,
      status: 'SUCCESS',
      chatReady: true,
      pagesMapped: pagesCount
    }));
  }, [setTaskState]);

  return (
    <div className="w-full flex-1 min-h-0 flex flex-col bg-white relative">
      
      {/* Scrollable Message Feed */}
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto scroll-smooth pb-40" /* pb-40 ensures we can scroll past the floating input */
      >
        
        {/* EMPTY STATE */}
        {messages.length === 0 && isKnowledgeReady && !taskState.taskId && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-4 mb-20 animate-fade-in -z-0">
            <div className="w-16 h-16 bg-slate-50 border border-slate-100 rounded-full flex items-center justify-center mb-6 shadow-sm">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-8 h-8 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
            </div>
            <h3 className="text-2xl font-semibold text-slate-800 tracking-tight">How can I help you today?</h3>
            <p className="text-[15px] font-medium text-slate-500 mt-2 max-w-sm">
              The Parallel Engine has mapped {getSafeHostname(taskState?.url)}. Ask anything to retrieve specific knowledge.
            </p>
          </div>
        )}

        {/* MESSAGES */}
        <div className="flex flex-col pb-10">
          
          {/* DISCOVERY CARD AS "SYSTEM MESSAGE 0" */}
          {taskState.taskId && (
            <div className="w-full pt-8 pb-4">
              <div className="max-w-3xl mx-auto w-full px-4 flex justify-end">
                <SwoopDiscoveryCard 
                  taskId={taskState.taskId} 
                  onComplete={handleDiscoveryComplete}
                />
              </div>
            </div>
          )}

          {messages.map((msg, idx) => (
            msg.role === 'user' ? (
              // USER MESSAGE - Right Aligned Bubble
              <div key={idx} className="w-full py-4 bg-white">
                <div className="max-w-3xl mx-auto w-full px-4 flex justify-end">
                  <div className="bg-slate-100 text-slate-800 px-5 py-3 rounded-2xl max-w-[80%] text-[15px] font-medium leading-relaxed">
                    {msg.content}
                  </div>
                </div>
              </div>
            ) : (
              // AI MESSAGE - Left Aligned Full Width
              <div key={idx} className="w-full py-8 border-b border-black/5 bg-slate-50/50">
                <div className="max-w-3xl mx-auto w-full px-4 flex gap-6">
                  
                  {/* Avatar */}
                  <div className="flex-shrink-0 mt-1">
                    <div className="w-8 h-8 bg-primary text-white rounded-full flex items-center justify-center shadow-sm">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
                      </svg>
                    </div>
                  </div>

                  {/* Content */}
                  <div className="flex-1 space-y-4">
                    <div className="prose prose-slate max-w-none text-[15px] leading-relaxed text-slate-700 font-medium">
                      {msg.content}
                    </div>
                    
                    {/* Sources Anchor Box */}
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-4 flex flex-wrap gap-2">
                        {msg.sources.map((url, sIdx) => {
                          const p = getSafePathname(url);
                          return (
                            <a 
                              key={sIdx} 
                              href={url} 
                              target="_blank" 
                              rel="noreferrer" 
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-[11px] font-bold text-slate-500 hover:text-primary hover:border-primary/30 transition-all shadow-sm"
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                              </svg>
                              <span>{p === '/' ? 'Home Page' : p}</span>
                            </a>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )
          ))}

          {/* Typing Indicator */}
          {isTyping && (
            <div className="w-full py-8 bg-slate-50/50 border-b border-black/5">
              <div className="max-w-3xl mx-auto w-full px-4 flex gap-6">
                <div className="flex-shrink-0 mt-1">
                  <div className="w-8 h-8 bg-primary text-white rounded-full flex items-center justify-center shadow-sm">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                      <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
                    </svg>
                  </div>
                </div>
                <div className="flex-1 flex items-center space-x-1.5 pt-2">
                    <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce delay-75"></div>
                    <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce delay-150"></div>
                    <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce delay-300"></div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Floating Minimal Input Area - Fixed strictly to bottom viewport */}
      <div className="fixed bottom-0 left-0 w-full bg-gradient-to-t from-white via-white to-transparent pt-20 pb-8 px-4 z-50 pointer-events-none">
        <div className="max-w-3xl mx-auto w-full pointer-events-auto">
          <form onSubmit={handleSend} className="relative shadow-[0_0_30px_rgba(0,0,0,0.08)] bg-white rounded-[2rem]">
            <input 
              type="text"
              placeholder={isActivelyProcessing ? "Mapping context... engine is busy 🕵️‍♂️" : "Message Swoop..."}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={!isKnowledgeReady}
              className={`w-full h-14 pl-6 pr-14 rounded-[2rem] text-[15px] font-medium transition-all outline-none border 
                ${isKnowledgeReady 
                  ? 'bg-white border-slate-200 focus:border-slate-300 focus:ring-4 focus:ring-slate-100 text-slate-800' 
                  : 'bg-slate-50 border-slate-100 opacity-60 cursor-not-allowed italic text-slate-500'}`}
            />
            <button 
              type="submit"
              disabled={!isKnowledgeReady || !query.trim()}
              className={`absolute right-3 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center rounded-full transition-all
                ${isKnowledgeReady && query.trim() 
                  ? 'bg-primary text-white hover:opacity-90 pointer-events-auto shadow-sm' 
                  : 'bg-slate-100 text-slate-300 pointer-events-none'}`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 10l7-7m0 0l7 7m-7-7v18" />
              </svg>
            </button>
          </form>
          <p className="text-center text-[10px] text-slate-400 font-medium mt-3 tracking-wide bg-white/50 backdrop-blur-sm rounded-full py-1 inline-block px-4 mx-auto block w-max">
            Swoop AI can make mistakes. Always verify critical technical details against the raw sources.
          </p>
        </div>
      </div>

    </div>
  );
};

export default ChatInterface;

import React, { useState } from 'react';
import UrlInput from '../components/Discovery/UrlInput';
import SwoopStatus from '../components/Discovery/SwoopStatus';
import { scraperService } from '../services/api';
import { useNavigate } from 'react-router-dom';

const HomePage = ({ taskState, setTaskState }) => {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    
    // START THE PARALLEL SWOOP — Navigate with Router State (Bulletproof 🛡️)
    const handleStartSwooping = async (url) => {
      setLoading(true);
      try {
        const data = await scraperService.processUrl(url);
        
        const newTask = {
          taskId: data.task_id,
          url,
          status: 'PENDING',
          message: 'Mapping Site Structure...',
          pagesMapped: 0,
          processedPages: [],
          chatReady: false
        };

        // Update global state AND pass via router state simultaneously
        // This guarantees ChatPage receives taskId on FIRST render
        setTaskState(newTask);
        navigate('/chat', { state: { taskId: data.task_id, url } });

      } catch (error) {
        console.error("Swoop error:", error);
        setTaskState(prev => ({ ...prev, status: 'ERROR', message: 'Failed to start. Check backend.' }));
        setLoading(false);
      }
    };
  
    // LOCAL POLLING REMOVED - DELEGATED TO CHAT PAGE 🤖
  
  
    return (
        <main className="flex-1 max-w-5xl w-full mx-auto px-8 py-16 flex flex-col items-center justify-center space-y-24">
          <div className="w-full flex flex-col items-center space-y-20 animate-fade-in">
              <section className="text-center space-y-8">
                <h1 className="text-6xl md:text-8xl font-black tracking-tighter leading-none text-slate-main">
                  Intelligent <br className="hidden md:block"/>Parallel <span className="text-primary tracking-normal">RAG</span>
                </h1>
                <p className="text-lg md:text-2xl text-slate-muted max-w-2xl mx-auto font-light leading-relaxed">
                  Build your private AI knowledge base in a single burst. Just drop a URL and our parallel engine will swoop and index.
                </p>
              </section>
  
              <UrlInput onStartSwooping={handleStartSwooping} isLoading={loading} />
  
              <SwoopStatus 
                status={taskState.status} 
                message={taskState.message} 
                activePageCount={taskState.pagesMapped} 
              />
          </div>
        </main>
    );
};

export default HomePage;

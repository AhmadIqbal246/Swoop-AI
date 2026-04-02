import React from 'react';
import UrlInput from '../components/Discovery/UrlInput';
import { useSwoop } from '../hooks/useSwoop';
import { useNavigate } from 'react-router-dom';

const HomePage = ({ taskState, setTaskState }) => {
    const navigate = useNavigate();
    
    // DATA HOOK 🎣
    const { startSwoop, isPending: isLoading } = useSwoop();
    
    const handleStartSwooping = (url) => {
      startSwoop(url, {
        onSuccess: (data) => {
          const newTask = {
            taskId: data.task_id,
            url,
            status: 'PENDING',
            message: 'Mapping Site Structure...',
            pagesMapped: 0,
            processedPages: [],
            chatReady: false
          };
          setTaskState(newTask);
          navigate('/chat', { state: { taskId: data.task_id, url } });
        },
        onError: (error) => {
          console.error("Swoop error:", error);
          setTaskState(prev => ({ 
            ...prev, 
            status: 'ERROR', 
            message: 'Failed to start. Check backend.' 
          }));
        }
      });
    };
  
    // LOCAL POLLING REMOVED - DELEGATED TO CHAT PAGE 🤖
  
  
    return (
        <main className="flex-1 max-w-5xl w-full mx-auto px-8 py-16 flex flex-col items-center justify-center space-y-24">
          <div className="w-full flex flex-col items-center space-y-20 animate-fade-in">
              <section className="text-center space-y-8">
                <h1 className="text-6xl md:text-8xl font-black tracking-tighter leading-none text-slate-main">
                  Get Instant <br className="hidden md:block"/>Answers from <span className="text-primary tracking-normal">Your Content</span>
                </h1>
                <p className="text-lg md:text-2xl text-slate-muted max-w-2xl mx-auto font-light leading-relaxed">
                  Transform any website into a searchable AI playground. Paste a link to start chatting with its content instantly.
                </p>
              </section>
  
              <UrlInput onStartSwooping={handleStartSwooping} isLoading={isLoading} />
  

          </div>
        </main>
    );
};

export default HomePage;

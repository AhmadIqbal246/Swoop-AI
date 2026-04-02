import React from 'react';

const SwoopStatus = ({ status, message, activePageCount }) => {
  if (status === 'IDLE') return null;

  const isCompleted = status === 'SUCCESS';
  const isProgressing = status === 'PROGRESS';

  return (
    <div className="w-full max-w-2xl mx-auto mt-12 space-y-6 glass-effect p-8 shadow-soft border-slate-50 animate-fade-in animate-float">
      <div className="flex justify-between items-center">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary glow-halo">
            <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <div className="flex flex-col">
             <span className="text-xs font-bold text-slate-800 tracking-wider">SWOOP STATUS</span>
             <span className="text-[10px] text-slate-400 font-mono tracking-widest uppercase">
               NODE: PARALLEL_CRAWLER_V2
             </span>
          </div>
        </div>
        
        <div className={`px-3 py-1 rounded-full text-[10px] font-bold tracking-widest uppercase border ${isCompleted ? 'bg-green-50 text-green-600 border-green-200' : 'bg-primary/5 text-primary border-primary/20 animate-pulse'}`}>
          {status}
        </div>
      </div>

      {/* Progress Bar (Futuristic Linear Style) */}
      <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
        <div 
          className={`h-full bg-primary transition-all duration-1000 ease-out glow-halo ${isCompleted ? 'w-full' : isProgressing ? 'w-2/3' : 'w-1/3'}`}
        />
      </div>

      <div className="flex justify-between items-end">
        <p className="text-sm font-medium text-slate-600 max-w-sm">
          {message || "Initializing the Parallel Engine..."}
        </p>
        <div className="flex flex-col items-end">
          <span className="text-[24px] font-black text-slate-800 leading-none">
            {activePageCount || 0}
          </span>
          <span className="text-[10px] text-slate-400 font-bold tracking-tighter uppercase">
            PAGES_MAPPED
          </span>
        </div>
      </div>
    </div>
  );
};

export default SwoopStatus;

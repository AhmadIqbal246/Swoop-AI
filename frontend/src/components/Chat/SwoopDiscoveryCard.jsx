import React, { useState } from 'react';
import { useTaskStatus } from '../../hooks/useTaskStatus';

const SwoopDiscoveryCard = ({ taskId, onComplete }) => {
  const [isExpanded, setIsExpanded] = useState(true);
  
  // CONSUME THE CUSTOM HOOK 🧪
  const { 
    status, 
    message, 
    logs,
    processedPages, 
    isWorking, 
    isSuccess 
  } = useTaskStatus(taskId, onComplete);

  const cardStatus = isSuccess ? 'SUCCESS' : status === 'FAILURE' ? 'FAILURE' : 'PROGRESS';

  return (
    <div className="w-fit mb-8 animate-fade-in flex flex-col items-end">
      <div className="flex items-center space-x-3 bg-slate-50 border border-slate-200 py-2.5 px-4 rounded-xl shadow-sm hover:shadow-md transition-shadow cursor-default">
        
        {/* Animated Icon */}
        <div className="flex-shrink-0">
          {isWorking ? (
            <svg className="w-4 h-4 text-slate-500 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          ) : isSuccess ? (
            <svg className="w-4 h-4 text-green-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1  1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
          ) : (
            <svg className="w-4 h-4 text-red-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}
        </div>

        {/* Text */}
        <div className="flex items-center space-x-3">
          <span className="text-[14px] font-medium text-slate-700">
            {isWorking ? 'Analyzing site content...' : isSuccess ? 'Knowledge mapped! You can ask questions now.' : 'Analysis failed'}
          </span>
          
          <button 
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-slate-400 hover:text-slate-600 transition-colors p-1"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className={`w-4 h-4 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>
      </div>

      {/* Expanded Details Logging */}
      {isExpanded && (
        <div className="mt-2 mr-1 p-4 bg-slate-50 border border-slate-100 rounded-xl space-y-3 w-fit min-w-[300px] max-w-sm relative shadow-lg">
          
          {logs && logs.length > 0 ? (
            <div className="space-y-2">
              {logs.map((log, idx) => (
                <div key={idx} className="flex items-start space-x-2 text-xs font-medium text-slate-500">
                  <div className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${idx === logs.length - 1 && isWorking ? 'bg-primary animate-pulse' : 'bg-green-400'}`}></div>
                  <p className="max-w-[260px] italic leading-tight">"{log}"</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center space-x-2 text-xs font-medium text-slate-500">
              <div className={`w-1.5 h-1.5 rounded-full ${isWorking ? 'bg-primary animate-pulse' : isSuccess ? 'bg-green-400' : 'bg-red-400'}`}></div>
              <p className="truncate block max-w-[260px] italic">"{message}"</p>
            </div>
          )}
          
          {processedPages.length > 0 && (
            <div className="border-t border-slate-200/60 pt-3 mt-3">
              <span className="text-[10px] font-bold tracking-[0.1em] text-slate-400 mb-2 block uppercase">
                Mapped Context ({processedPages.length} urls)
              </span>
              <div className="grid grid-cols-1 gap-1 max-h-32 overflow-y-auto pr-2 custom-scrollbar">
                {processedPages.map((url, idx) => {
                  let path = url;
                  try { path = new URL(url).pathname; } catch {}
                  return (
                    <div key={idx} className="flex items-center space-x-2">
                       <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3 flex-shrink-0 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                         <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                       </svg>
                      <span className="text-[11.5px] font-medium text-slate-500 truncate">
                        {path === '/' ? 'Home Page' : path}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SwoopDiscoveryCard;

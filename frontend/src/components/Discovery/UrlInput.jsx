import React, { useState } from 'react';

const UrlInput = ({ onStartSwooping, isLoading }) => {
  const [url, setUrl] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (url && url.startsWith('http')) {
      onStartSwooping(url);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      <form 
        onSubmit={handleSubmit}
        className={`group relative flex items-center transition-all duration-500 bg-white rounded-3xl p-1.5 shadow-soft border border-slate-100 ${isLoading ? 'opacity-50 pointer-events-none' : 'hover:shadow-halo hover:border-primary/20'}`}
      >
        {/* Futuristic Icon Prefix */}
        <div className="flex-shrink-0 ml-4 mr-2 text-slate-300">
           <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
           </svg>
        </div>

        {/* Input Field */}
        <input 
          type="url"
          required
          placeholder="https://example.com"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          className="w-full h-14 bg-transparent border-none focus:ring-0 text-slate-800 placeholder:text-slate-300 text-lg font-medium selection:bg-primary/20"
        />

        {/* The Action Button */}
        <button 
          type="submit"
          disabled={isLoading}
          className="flex-shrink-0 h-14 px-8 bg-primary text-white rounded-2xl font-bold tracking-tight shadow-lg transition-all hover:scale-105 active:scale-95 disabled:opacity-50"
        >
          {isLoading ? (
            <div className="flex items-center space-x-2">
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
              <span>SWOOPING...</span>
            </div>
          ) : (
            "PARALLEL SWOOP"
          )}
        </button>
      </form>
      
      {/* Subtle Hint Text */}
      <p className="mt-6 text-center text-[10px] uppercase font-bold tracking-[0.25em] text-slate-400 opacity-60">
        Enter ANY Website URL to Start One-Shot Indexing
      </p>
    </div>
  );
};

export default UrlInput;

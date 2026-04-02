import React from 'react';

const Navbar = () => {
  return (
    <nav className="sticky top-0 z-50 w-full px-8 py-5 flex justify-between items-center glass border-b border-white/40 flex-shrink-0 animate-fade-in">
      {/* Elegant Pure Logo Section */}
      <div className="flex items-center space-x-3 group cursor-pointer">
        <div className="w-11 h-11 bg-primary text-white flex items-center justify-center rounded-xl shadow-[0_8px_16px_rgba(37,99,235,0.2)] transform group-hover:scale-110 transition-transform duration-300">
           <svg 
            xmlns="http://www.w3.org/2000/svg" 
            className="w-6 h-6" 
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor"
           >
             <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
           </svg>
        </div>
        <div className="flex flex-col">
          <span className="text-xl font-bold tracking-tight text-slate-800">
            PARALLEL <span className="text-primary tracking-normal">RAG</span>
          </span>
          <span className="text-[11px] text-slate-400 font-medium tracking-[0.2em] uppercase">
            Pure Intelligence
          </span>
        </div>
      </div>

      {/* Backend Status Indicator (Elegant Version) */}
      <div className="hidden md:flex items-center space-x-2.5 px-4 py-2 rounded-full bg-slate-50 border border-slate-100 group transition-all hover:bg-white hover:shadow-sm">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-30"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
        </span>
        <span className="text-[11px] font-bold text-slate-500 uppercase tracking-widest leading-none">
          SYSTEM: ONLINE
        </span>
      </div>
    </nav>
  );
};

export default Navbar;

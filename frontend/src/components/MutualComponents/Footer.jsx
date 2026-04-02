import React from 'react';

const Footer = () => {
  return (
    <footer className="w-full py-8 px-10 border-t border-slate-50 flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0 text-[10px] font-bold tracking-[0.2em] text-slate-400 uppercase bg-white/30 backdrop-blur-sm">
        <div className="flex items-center space-x-2">
          <span className="w-2 h-2 bg-primary/40 rounded-full animate-pulse"></span>
          <span>System Uptime: 99.98%</span>
        </div>
        
        <div className="flex items-center space-x-6">
          <span>© 2026 Z SOFT AI Systems</span>
          <span className="text-slate-200">|</span>
          <span>Dubai Headquarters</span>
        </div>

        <div className="flex items-center space-x-2">
            <span className="text-slate-300">CORE:</span>
            <span className="text-slate-500">LLAMA 3.3 × GROQ</span>
        </div>
    </footer>
  );
};

export default Footer;

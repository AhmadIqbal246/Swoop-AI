import React from 'react';
import { Link, useLocation } from 'react-router-dom';

const Navbar = () => {
  const location = useLocation();

  const isActive = (path) => location.pathname === path;

  return (
    <nav className="sticky top-0 z-50 w-full px-12 py-5 flex items-center glass border-b border-white/40 flex-shrink-0 animate-fade-in shadow-sm">
      {/* Left: Logo Section */}
      <div className="flex-1 flex justify-start">
        <Link to="/" className="flex items-center group cursor-pointer no-underline">
            <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-primary text-white flex items-center justify-center rounded-xl shadow-[0_8px_16px_rgba(37,99,235,0.2)] transform group-hover:rotate-6 transition-all duration-300">
               <svg 
                xmlns="http://www.w3.org/2000/svg" 
                className="w-5 h-5" 
                fill="none" 
                viewBox="0 0 24 24" 
                stroke="currentColor"
               >
                 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
               </svg>
            </div>
            <span className="text-xl font-black tracking-tighter text-slate-800 flex items-center">
              Swoop <span className="text-primary ml-1.5 font-extrabold opacity-90">AI</span>
            </span>
          </div>
        </Link>
      </div>

      {/* Center: Navigation Links */}
      <div className="hidden md:flex items-center justify-center space-x-12 flex-1">
        <Link 
          to="/" 
          className={`text-sm font-bold tracking-wide transition-all duration-300 relative group py-1 ${
            isActive('/') ? 'text-primary' : 'text-slate-500 hover:text-slate-900'
          }`}
        >
          Home
          <span className={`absolute -bottom-1 left-0 w-full h-0.5 bg-primary rounded-full transition-all duration-300 transform ${isActive('/') ? 'scale-x-100' : 'scale-x-0 group-hover:scale-x-100'}`}></span>
        </Link>
        <Link 
          to="/chat" 
          className={`text-sm font-bold tracking-wide transition-all duration-300 relative group py-1 ${
            isActive('/chat') ? 'text-primary' : 'text-slate-500 hover:text-slate-900'
          }`}
        >
          Chat
          <span className={`absolute -bottom-1 left-0 w-full h-0.5 bg-primary rounded-full transition-all duration-300 transform ${isActive('/chat') ? 'scale-x-100' : 'scale-x-0 group-hover:scale-x-100'}`}></span>
        </Link>
      </div>

      {/* Right: Action Button */}
      <div className="flex-1 flex justify-end items-center space-x-6">
        <Link 
          to="/chat" 
          className="px-6 py-2.5 bg-slate-900 text-white rounded-xl text-xs font-bold uppercase tracking-widest shadow-xl shadow-slate-200 hover:bg-primary hover:-translate-y-0.5 transition-all duration-300 active:scale-95"
        >
          Launch Chat
        </Link>
      </div>
    </nav>
  );
};

export default Navbar;



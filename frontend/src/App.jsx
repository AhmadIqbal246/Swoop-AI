import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/MutualComponents/Navbar';
import Footer from './components/MutualComponents/Footer';
import HomePage from './pages/HomePage';
import ChatPage from './pages/ChatPage';

function App() {
  const [taskState, setTaskState] = useState(() => {
    const saved = localStorage.getItem('swoop_task_state');
    if (saved) {
      try { return JSON.parse(saved); } catch {}
    }
    return {
      taskId: null,
      url: '',
      status: 'IDLE',
      message: '',
      pagesMapped: 0,
      processedPages: [],
      chatReady: false
    };
  });

  React.useEffect(() => {
    localStorage.setItem('swoop_task_state', JSON.stringify(taskState));
  }, [taskState]);

  return (
    <Router>
      <div className="relative flex flex-col min-h-screen">
        {/* Soft Halo Background Effects */}
        <div className="fixed top-[-100px] left-[-100px] w-[600px] h-[600px] bg-primary/5 blur-[120px] rounded-full animate-pulse-slow"></div>
        <div className="fixed bottom-[-100px] right-[-100px] w-[600px] h-[600px] bg-indigo-500/5 blur-[120px] rounded-full animate-pulse-slow delayed-animation"></div>

        <Navbar />

        <Routes>
          <Route path="/" element={<HomePage taskState={taskState} setTaskState={setTaskState} />} />
          <Route path="/chat" element={<ChatPage taskState={taskState} setTaskState={setTaskState} />} />
        </Routes>

        <Footer />
      </div>
    </Router>
  );
}

export default App;

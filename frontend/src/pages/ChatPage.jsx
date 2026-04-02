import React, { useEffect } from 'react';
import ChatInterface from '../components/Chat/ChatInterface';
import { useNavigate, useLocation } from 'react-router-dom';

const ChatPage = ({ taskState, setTaskState }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const routerTask = location.state || {};
  
  const effectiveTaskState = {
    ...taskState,
    taskId: taskState?.taskId || routerTask.taskId || null,
    url:    taskState?.url    || routerTask.url    || '',
  };

  useEffect(() => {
    if (routerTask.taskId) {
      if (!taskState?.taskId) {
        setTaskState(prev => ({
          ...prev,
          taskId: routerTask.taskId,
          url:    routerTask.url || prev.url,
          status: 'PENDING',
          chatReady: false,
        }));
      }
      // Clear the router state to prevent old tasks from reviving on manual refresh
      navigate(location.pathname, { replace: true, state: null });
    } else {
      // If user presses F5 / Refreshes page AND the task was already completed, flush it.
      if (taskState?.status === 'SUCCESS' && taskState?.taskId) {
        setTaskState(prev => ({ ...prev, taskId: null }));
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const hostname = (() => {
    try { return effectiveTaskState.url ? new URL(effectiveTaskState.url).hostname : null; }
    catch { return null; }
  })();

  return (
    // Full-height flex column — no padding, edge-to-edge like ChatGPT
    <main className="flex-1 flex flex-col min-h-0 overflow-hidden">
      

      {/* Chat fills all remaining height */}
      <div className="flex-1 min-h-0 flex flex-col relative w-full">
        <ChatInterface taskState={effectiveTaskState} setTaskState={setTaskState} />
      </div>
    </main>
  );
};

export default ChatPage;

import { useState, useEffect } from 'react';
import { scraperService } from '../services/api';

/**
 * Advanced Task Polling Hook 🕵️‍♂️
 * Encapsulates the logic for watching a Celery background task.
 */
export const useTaskStatus = (taskId, onComplete) => {
  const [taskData, setTaskData] = useState({
    status: 'PENDING',
    message: 'Initializing the Parallel Engine...',
    logs: [],
    processedPages: [],
    isWorking: true,
    isSuccess: false,
    isFailed: false
  });

  useEffect(() => {
    let timeoutId;
    let isActive = true;

    if (!taskId) return;

    const poll = async () => {
      try {
        const res = await scraperService.getTaskStatus(taskId);
        
        if (!isActive) return;

        const currentStatus = res.status;
        const isDone = currentStatus === 'COMPLETED';
        const isError = currentStatus === 'FAILURE';

        setTaskData({
          status: currentStatus,
          message: res.message,
          logs: res.logs || [],
          processedPages: res.processed_pages || [],
          isWorking: !isDone && !isError,
          isSuccess: isDone,
          isFailed: isError
        });

        if (isDone) {
          if (onComplete) onComplete(res.processed_pages?.length || 0);
          return; // Stop polling
        }
        
        if (isError) return; // Stop polling

        // Queue next check only if still working
        timeoutId = setTimeout(poll, 1500);
      } catch (err) {
        console.error("Task Polling Error:", err);
        // Retry anyway after a delay
        timeoutId = setTimeout(poll, 3000);
      }
    };

    poll();

    return () => {
      isActive = false;
      clearTimeout(timeoutId);
    };
  }, [taskId, onComplete]);

  return taskData;
};

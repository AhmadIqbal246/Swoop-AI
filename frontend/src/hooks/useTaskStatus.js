import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { scraperService } from '../services/api';

/**
 * Advanced Task Polling Hook 🕵️‍♂️
 * Uses TanStack Query to declarative watch a background task.
 */
export const useTaskStatus = (taskId, onComplete) => {
  const query = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => scraperService.getTaskStatus(taskId),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.status === 'COMPLETED' || data?.status === 'FAILURE') return false;
      return 1500; // Poll every 1.5s
    },
    select: (res) => ({
      status: res.status,
      message: res.message,
      logs: res.logs || [],
      processedPages: res.processed_pages || [],
      isWorking: res.status !== 'COMPLETED' && res.status !== 'FAILURE',
      isSuccess: res.status === 'COMPLETED',
      isFailed: res.status === 'FAILURE'
    })
  });

  // Synchronize onComplete callback with Query success
  useEffect(() => {
    if (query.data?.isSuccess && onComplete) {
      onComplete(query.data.processedPages.length);
    }
  }, [query.data?.isSuccess, query.data?.processedPages.length, onComplete]);

  // Return the query data with fallback defaults
  return {
    ...(query.data || {
      status: 'PENDING',
      message: 'Connecting to Engine...',
      logs: [],
      processedPages: [],
      isWorking: true,
      isSuccess: false,
      isFailed: false
    }),
    isLoading: query.isLoading,
    isError: query.isError
  };
};

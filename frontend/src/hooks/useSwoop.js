import { useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import { scraperService } from '../services/api';

/**
 * Hook for initiating and stopping a website 'Swoop' (Scrape & Vectorize) 🕵️‍♂️
 */
export const useSwoop = () => {
  const mutation = useMutation({
    mutationFn: (url) => scraperService.processUrl(url),
  });

  const stopSwoop = useCallback(async (taskId) => {
    if (!taskId) return;
    try {
      await scraperService.stopTask(taskId);
    } catch (err) {
      console.error("Failed to stop swoop:", err);
    }
  }, []);

  return {
    startSwoop: mutation.mutate,
    startSwoopAsync: mutation.mutateAsync,
    stopSwoop,
    isPending: mutation.isPending,
    isError: mutation.isError,
    data: mutation.data,
    error: mutation.error,
    reset: mutation.reset
  };
};

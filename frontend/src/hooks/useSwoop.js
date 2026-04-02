import { useMutation } from '@tanstack/react-query';
import { scraperService } from '../services/api';

/**
 * Hook for initiating a website 'Swoop' (Scrape & Vectorize) 🕵️‍♂️
 */
export const useSwoop = () => {
  const mutation = useMutation({
    mutationFn: (url) => scraperService.processUrl(url),
  });

  return {
    startSwoop: mutation.mutate,
    startSwoopAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isError: mutation.isError,
    data: mutation.data,
    error: mutation.error,
    reset: mutation.reset
  };
};

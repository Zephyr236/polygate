/**
 * TanStack Query hooks and query keys for the admin API.
 */

import { useMutation, useQuery } from "@tanstack/react-query";

import { chat, fetchMetrics, fetchProviders, saveProviders, simulate } from "../api/client";
import type { ProviderConfig } from "../api/types";

/** Query keys shared by dashboard widgets. */
const keys = {
  providers: ["providers"] as const,
  metrics: (range: string) => ["metrics", range] as const,
};

/** Poll provider list and health every 20 seconds. */
export function useProviders() {
  return useQuery({ queryKey: keys.providers, queryFn: fetchProviders, refetchInterval: 20_000 });
}

/** Poll metrics for the selected time range. */
export function useMetrics(range: string) {
  return useQuery({
    queryKey: keys.metrics(range),
    queryFn: () => fetchMetrics(range),
    refetchInterval: 30_000,
  });
}

/** Persist a new provider pool. */
export function useSaveProviders() {
  return useMutation({ mutationFn: (providers: ProviderConfig[]) => saveProviders(providers) });
}

/** Simulate a routing decision. */
export function useSimulate() {
  return useMutation({
    mutationFn: (input: { model: string; prompt: string }) => simulate(input.model, input.prompt),
  });
}

/** Run one chat completion through the router. */
export function useChat() {
  return useMutation({
    mutationFn: (input: { model: string; prompt: string; stream: boolean }) =>
      chat(input.model, input.prompt, input.stream),
  });
}

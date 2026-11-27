/**
 * TanStack Query hooks and query keys for the admin API.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  chat,
  createApiKey,
  fetchApiKeys,
  fetchMetrics,
  fetchProviders,
  revokeApiKey,
  saveProviders,
  simulate,
} from "../api/client";
import type { ApiKeyTier, ProviderConfig } from "../api/types";

/** Query keys shared by dashboard widgets. */
const keys = {
  providers: ["providers"] as const,
  metrics: (range: string) => ["metrics", range] as const,
  apiKeys: ["api-keys"] as const,
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

/** List generated caller API keys. */
export function useApiKeys() {
  return useQuery({ queryKey: keys.apiKeys, queryFn: fetchApiKeys });
}

/** Generate a new caller API key and refresh the list. */
export function useCreateApiKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; tier: ApiKeyTier; allowed_providers: string[] }) =>
      createApiKey(input),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.apiKeys }),
  });
}

/** Revoke a generated caller API key. */
export function useRevokeApiKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => revokeApiKey(id),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.apiKeys }),
  });
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

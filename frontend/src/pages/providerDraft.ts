/**
 * Editable provider shape shared by the editor and card.
 */

import type { ProviderConfig } from "../api/types";

/** Editable copy of a provider config with string-encoded numeric inputs. */
export interface ProviderDraft {
  id: string;
  base_url: string;
  protocol: ProviderConfig["protocol"];
  model: string;
  api_key_env: string;
  auth_style: ProviderConfig["auth_style"];
  session_header: string;
  session_mode: ProviderConfig["session_mode"];
  lanes: string;
  max_concurrency: string;
  max_tokens_min: string;
  stream_usage: ProviderConfig["stream_usage"];
  cost_coefficient: string;
  priority: string;
  enabled: boolean;
  tags: string;
}

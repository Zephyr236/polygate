# Configuration reference

Generated from the pydantic models in `backend/src/polygate/config.py`
by `scripts/gen_config_reference.py`. Run the script after changing the models.

## ProviderConfig

| Field | Description |
| --- | --- |
| `id` | stable channel identifier, lowercase with dashes |
| `base_url` | upstream base URL without the protocol suffix |
| `protocol` | wire protocol the upstream speaks |
| `model` | upstream model name sent with each request |
| `aliases` | client-facing model aliases |
| `api_key_env` | environment variable holding the API key |
| `auth_style` | which credential header to send |
| `session_header` | header carrying a session id |
| `session_mode` | how session ids are generated |
| `lanes` | parallel session buckets |
| `max_concurrency` | concurrency slots per lane |
| `max_tokens_min` | floor applied to the request max_tokens |
| `stream_usage` | where the upstream reports usage while streaming |
| `error_rules` | rules mapping payloads or text onto error classes |
| `retry` | retry policy for retryable failures |
| `timeouts` | connect and total timeouts |
| `active_windows` | UTC windows restricting traffic with an optional multiplier |
| `cost_coefficient` | user-defined relative price weight |
| `priority` | lower values are tried first |
| `enabled` | whether the channel participates in routing |
| `tags` | free-form labels shown in the dashboard |
| `input_price_per_mtok` | USD per million prompt tokens |
| `output_price_per_mtok` | USD per million completion tokens |

## RetryPolicy

| Field | Description |
| --- | --- |
| `attempts` | retry attempts per provider |
| `base_delay_ms` | first retry delay |
| `max_delay_ms` | retry delay cap |
| `jitter` | multiplicative jitter applied to delays |

## Timeouts

| Field | Description |
| --- | --- |
| `connect_seconds` | connect timeout |
| `total_seconds` | total request timeout |

## TimeWindow

| Field | Description |
| --- | --- |
| `start_hour` | window start hour in UTC |
| `end_hour` | window end hour in UTC |
| `multiplier` | cost multiplier applied inside the window |
| `weekday_from` | first ISO weekday the window applies to |
| `weekday_to` | last ISO weekday the window applies to |

## ErrorRule

| Field | Description |
| --- | --- |
| `json_path` | dotted JSON path that must be present |
| `match` | case-insensitive text fragment that must appear |
| `error_class` | normalized error class |
| `retryable` | whether the error consumes retry budget |

## RoutingConfig

| Field | Description |
| --- | --- |
| `weights` | relative weights of the routing score components |
| `exploration_ratio` | share of requests that may try a lower priority tier |
| `max_switches` | maximum provider switches per request |
| `failure_threshold` | consecutive failures that open a circuit |
| `cooldown_base_ms` | first cooldown duration |
| `cooldown_max_ms` | cooldown cap |
| `half_open_probes` | probes allowed while half open |
| `success_ema_alpha` | smoothing factor for success rate |
| `latency_ema_alpha` | smoothing factor for latency |
| `speed_target_ms` | latency that scores a perfect speed value |

## RoutingWeights

| Field | Description |
| --- | --- |
| `success` | weight of the success rate component |
| `speed` | weight of the latency component |
| `cost` | weight of the inverse cost component |
| `cache` | weight of the cache hit component |

## ClientKeyConfig

| Field | Description |
| --- | --- |
| `id` | stable channel identifier, lowercase with dashes |
| `name` | human-readable caller key name |
| `api_key_env` | environment variable holding the API key |
| `allowed_providers` | provider ids this caller key may use; at least one is required |
| `weights` | relative weights of the routing score components |
| `respect_priority` | see the model definition |

## AppConfig (dataclass)

| Field | Description |
| --- | --- |
| `providers` | channel configurations loaded from the seed file |
| `client_keys` | caller keys with provider allowlists and routing weights |
| `routing` | see the dataclass definition |
| `database_path` | SQLite file for metrics, events and provider overrides |
| `admin_token` | bearer token protecting the admin API and UI |
| `proxy_api_key` | optional bearer token protecting /v1/* |
| `providers_file` | path of the provider seed file when set |


# Open Source Default Config Seed

## Context

Release bundles exclude runtime `data/` and `configs/`, so first deploys generated `holo-cortex-zero.yaml` from code defaults. That produced an empty `MODEL_GROUPS` map even though the source runtime config had default model groups.

## Change

The release script now generates `default_configs/holo-cortex-zero.yaml` from the source runtime config with secret-like fields mechanically blanked. Install scripts copy this seed to `${HCZ_DATA_DIR}/configs/holo-cortex-zero.yaml` only when the runtime config is missing.

## Safety

Existing runtime configs are never overwritten. Runtime `data/` remains excluded from the release bundle.

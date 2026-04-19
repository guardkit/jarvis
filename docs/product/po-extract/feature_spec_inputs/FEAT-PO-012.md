# Dual Reachy Role Configuration

## Description

The adapter stack must support two Reachy Mini units with identical adapter software but different default routing roles: Scholar for GCSE English tutoring and Bridge for Jarvis access. This configuration model needs to keep the adapter reusable while allowing per-unit defaults and resource planning on the shared GB10 host.

## Bounded Context

Adapter Interface

## Source Documents

- reachy-mini-integration.md

## Constraints

- Both Reachy units are physically connected to the GB10 via USB in the documented topology.
- Adapter software is identical and only default routing differs.
- Shared GB10 resources may become a contention point for both units.

## Dependencies

- FEAT-PO-009
- FEAT-PO-010

## Suggested Context Files

- reachy-mini-integration.md

# GB10-Centred Hardware Topology and Connectivity

## Description

The deployed system must use the DGX Spark GB10 as the execution host for NATS, vLLM, Graphiti, and fleet agents, while MacBook Pro acts as dashboard and CLI client and Reachy Mini connects as an embodied adapter endpoint. The topology must also account for Tailscale mesh connectivity and shared storage or persistence roles described for the NAS and FalkorDB.

## Bounded Context

Infrastructure and Runtime

## Source Documents

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
- reachy-mini-integration.md

## Constraints

- GB10 hosts NATS, vLLM, Graphiti, and agent execution.
- Reachy units are physically connected to GB10 via USB in the documented integration plan.
- Tailscale mesh networking is part of the operating context.

## Dependencies

- FEAT-PO-020

## Suggested Context Files

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
- reachy-mini-integration.md

# Reachy Proactive Notifications and Expressive Feedback

## Description

The Reachy adapter must subscribe to `notifications.reachy-bridge`, play attention animations, wait for user engagement, and then speak notification content back through the robot. This gives Jarvis persistent presence and expressive feedback through head movement, antenna motion, and spoken updates rather than relying only on user-initiated requests.

## Bounded Context

Adapter Interface

## Source Documents

- reachy-mini-integration.md
- jarvis-vision.md

## Constraints

- Notifications are delivered through `notifications.{adapter}` subjects.
- The adapter should leverage existing Reachy movement and expression capabilities.
- Proactive notifications are a key part of the Ship's Computer feel.

## Dependencies

- FEAT-PO-004
- FEAT-PO-010

## Suggested Context Files

- reachy-mini-integration.md
- jarvis-vision.md

#!/usr/bin/env python3
"""Validation scenarios from quickstart.md against real Mosquitto broker.

This script validates the quickstart examples against a live MQTT broker.
Run with: python tests/validate_quickstart.py

Requirements:
- Mosquitto broker running at mqtt://localhost:1883
- tars-core package installed
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tars.adapters.mqtt_client import MQTTClient
from tars.contracts.envelope import Envelope


async def scenario_1_minimal_publish():
    """Scenario 1: Minimal Example (7 LOC) - Publish event."""
    print("\n=== Scenario 1: Minimal Publish ===")
    
    # Create and connect (URL + client ID)
    client = MQTTClient("mqtt://localhost:1883", "quickstart-test-1")
    await client.connect()
    
    # Publish event
    await client.publish_event("test/topic", "test.event", {"message": "Hello MQTT!"})
    print("✓ Published event to test/topic")
    
    # Cleanup
    await client.shutdown()
    print("✓ Scenario 1 passed")


async def scenario_2_subscribe_handler():
    """Scenario 2: Subscribe with handler."""
    print("\n=== Scenario 2: Subscribe + Publish ===")
    
    messages_received = []
    
    async def handle_message(payload: bytes) -> None:
        envelope = Envelope.model_validate_json(payload)
        messages_received.append(envelope)
        print(f"  Received: {envelope.type} - {envelope.data}")
    
    # Subscriber client
    subscriber = MQTTClient("mqtt://localhost:1883", "quickstart-test-sub")
    await subscriber.connect()
    await subscriber.subscribe("test/scenario2", handle_message)
    await asyncio.sleep(0.5)  # Wait for subscription
    
    # Publisher client
    publisher = MQTTClient("mqtt://localhost:1883", "quickstart-test-pub")
    await publisher.connect()
    await publisher.publish_event(
        topic="test/scenario2",
        event_type="test.scenario2",
        data={"value": 42},
        qos=1,
    )
    
    # Wait for message
    await asyncio.sleep(1.0)
    
    # Validate
    assert len(messages_received) == 1, f"Expected 1 message, got {len(messages_received)}"
    assert messages_received[0].type == "test.scenario2"
    assert messages_received[0].data["value"] == 42
    print("✓ Message received and validated")
    
    await publisher.shutdown()
    await subscriber.shutdown()
    print("✓ Scenario 2 passed")


async def scenario_3_context_manager():
    """Scenario 3: Context manager pattern."""
    print("\n=== Scenario 3: Context Manager ===")
    
    async with MQTTClient("mqtt://localhost:1883", "quickstart-test-ctx") as client:
        await client.publish_event("test/context", "test.ctx", {"msg": "Auto-cleanup!"})
        print("✓ Published event with context manager")
    
    print("✓ Scenario 3 passed (auto-cleanup)")


async def scenario_4_health_enabled():
    """Scenario 4: Health publishing."""
    print("\n=== Scenario 4: Health Publishing ===")
    
    health_messages = []
    
    async def handle_health(payload: bytes) -> None:
        data = Envelope.model_validate_json(payload).data
        health_messages.append(data)
        print(f"  Health: ok={data.get('ok')}, event={data.get('event')}")
    
    # Monitor health
    monitor = MQTTClient("mqtt://localhost:1883", "quickstart-health-monitor")
    await monitor.connect()
    await monitor.subscribe("system/health/quickstart-health-test", handle_health)
    await asyncio.sleep(0.5)
    
    # Service with health
    client = MQTTClient(
        "mqtt://localhost:1883",
        "quickstart-health-test",
        enable_health=True,
    )
    await client.connect()
    await asyncio.sleep(0.5)  # Wait for health publish
    
    await client.publish_health(ok=True, event="ready")
    await asyncio.sleep(0.5)
    
    await client.shutdown()
    await asyncio.sleep(0.5)
    
    # Validate
    assert len(health_messages) >= 2, f"Expected ≥2 health messages, got {len(health_messages)}"
    print(f"✓ Received {len(health_messages)} health messages")
    
    await monitor.shutdown()
    print("✓ Scenario 4 passed")


async def scenario_5_wildcard_subscription():
    """Scenario 5: Wildcard subscriptions."""
    print("\n=== Scenario 5: Wildcard Subscriptions ===")
    
    messages = []
    
    async def handle_wildcard(payload: bytes) -> None:
        envelope = Envelope.model_validate_json(payload)
        messages.append(envelope.type)
    
    subscriber = MQTTClient("mqtt://localhost:1883", "quickstart-wildcard-sub")
    await subscriber.connect()
    await subscriber.subscribe("sensors/+/temperature", handle_wildcard)
    await asyncio.sleep(0.5)
    
    publisher = MQTTClient("mqtt://localhost:1883", "quickstart-wildcard-pub")
    await publisher.connect()
    
    # Publish to matching topics
    await publisher.publish_event("sensors/room1/temperature", "sensor.temp", {"value": 20.5})
    await publisher.publish_event("sensors/room2/temperature", "sensor.temp", {"value": 21.3})
    # This should NOT match (wrong suffix)
    await publisher.publish_event("sensors/room1/humidity", "sensor.humidity", {"value": 60})
    
    await asyncio.sleep(1.0)
    
    # Validate: only 2 temperature messages should be received
    assert len(messages) == 2, f"Expected 2 messages, got {len(messages)}"
    print(f"✓ Wildcard subscription matched {len(messages)} messages correctly")
    
    await publisher.shutdown()
    await subscriber.shutdown()
    print("✓ Scenario 5 passed")


async def scenario_6_correlation_id():
    """Scenario 6: Request-response with correlation ID."""
    print("\n=== Scenario 6: Correlation ID ===")
    
    import uuid
    from asyncio import Future
    
    response_futures: dict[str, Future] = {}
    
    async def handle_response(payload: bytes) -> None:
        envelope = Envelope.model_validate_json(payload)
        # Envelope uses 'id' field for correlation
        if envelope.id in response_futures:
            response_futures[envelope.id].set_result(envelope.data)
    
    # Requester
    requester = MQTTClient("mqtt://localhost:1883", "quickstart-requester")
    await requester.connect()
    await requester.subscribe("test/response", handle_response)
    await asyncio.sleep(0.5)
    
    # Responder
    responder = MQTTClient("mqtt://localhost:1883", "quickstart-responder")
    await responder.connect()
    
    async def handle_request(payload: bytes) -> None:
        envelope = Envelope.model_validate_json(payload)
        # Echo back with correlation ID (stored in envelope.id)
        await responder.publish_event(
            "test/response",
            "test.response",
            {"echo": envelope.data.get("text")},
            correlation_id=envelope.id,  # Use the request's ID
        )
    
    await responder.subscribe("test/request", handle_request)
    await asyncio.sleep(0.5)
    
    # Send request
    request_id = str(uuid.uuid4())
    response_future = Future()
    response_futures[request_id] = response_future
    
    await requester.publish_event(
        "test/request",
        "test.request",
        {"text": "Hello"},
        correlation_id=request_id,
    )
    
    # Wait for response
    response = await asyncio.wait_for(response_future, timeout=3.0)
    assert response["echo"] == "Hello"
    print("✓ Request-response with correlation ID works")
    
    await requester.shutdown()
    await responder.shutdown()
    print("✓ Scenario 6 passed")


async def main():
    """Run all validation scenarios."""
    print("=" * 60)
    print("Quickstart Validation Scenarios")
    print("=" * 60)
    print("\nValidating against Mosquitto at mqtt://localhost:1883")
    
    scenarios = [
        scenario_1_minimal_publish,
        scenario_2_subscribe_handler,
        scenario_3_context_manager,
        scenario_4_health_enabled,
        scenario_5_wildcard_subscription,
        scenario_6_correlation_id,
    ]
    
    passed = 0
    failed = 0
    
    for scenario in scenarios:
        try:
            await scenario()
            passed += 1
        except Exception as e:
            print(f"\n✗ {scenario.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed > 0:
        sys.exit(1)
    else:
        print("\n✓ All validation scenarios passed!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

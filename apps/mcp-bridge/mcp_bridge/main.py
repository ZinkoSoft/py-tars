import asyncio, orjson, os, logging
from pydantic import BaseModel
from aiomqtt import Client as Mqtt
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.streamable_http import streamablehttp_client
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-bridge")

class McpToolSpec(BaseModel):
    server: str
    name: str
    description: str | None = None
    parameters: dict  # JSON Schema

def tool_to_openai_function(server_name, t) -> dict:
    # t is an MCP Tool (SDK object) with .name, .description, .inputSchema (JSONSchema)
    # Note: MCP uses camelCase (inputSchema), not snake_case (input_schema)
    # OpenAI function names: use underscores instead of colons (colons may cause issues)
    return {
        "type": "function",
        "function": {
            "name": f"mcp__{server_name}__{t.name}",
            "description": t.description or "",
            "parameters": t.inputSchema or {"type":"object","properties":{}}
        }
    }

async def load_servers_yaml():
    """Load MCP server configuration from YAML file."""
    yaml_path = os.getenv("MCP_SERVERS_YAML", "/config/mcp.server.yml")
    try:
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)
        servers = config.get("servers", [])
        logger.info(f"Loaded {len(servers)} MCP servers from {yaml_path}")
        return servers
    except Exception as e:
        logger.error(f"Failed to load MCP servers YAML: {e}")
        return []

async def main():
    host = os.getenv("MQTT_HOST", "127.0.0.1")
    port = int(os.getenv("MQTT_PORT", "1883"))
    user = os.getenv("MQTT_USER")
    pwd = os.getenv("MQTT_PASS")
    
    async with Mqtt(hostname=host, port=port, username=user, password=pwd) as mqtt:
        logger.info("Connected to MQTT")

        # Load YAML, iterate servers → connect & enumerate tools
        servers = await load_servers_yaml()
        tool_funcs = []
        sessions: dict[str, ClientSession] = {}
        active_contexts = []  # Keep context managers alive for the program duration

        for s in servers:
            try:
                logger.info(f"Connecting to MCP server: {s['name']}...")
                transport = s.get("transport", "stdio")
                
                if transport == "http":
                    # HTTP/streamable-http transport
                    url = s.get("url")
                    if not url:
                        logger.error(f"HTTP transport requires 'url' for server {s['name']}")
                        continue
                    
                    logger.debug(f"Connecting via HTTP to {url}")
                    context = streamablehttp_client(url)
                    read_stream, write_stream, _ = await context.__aenter__()
                    active_contexts.append((context, (read_stream, write_stream)))
                    
                elif transport == "stdio":
                    # stdio transport
                    params = StdioServerParameters(
                        command=s["command"],
                        args=s.get("args", []),
                        env=s.get("env", {})
                    )
                    logger.debug(f"Starting stdio client for {s['name']}")
                    context = stdio_client(params)
                    cm = await context.__aenter__()
                    active_contexts.append((context, cm))
                    read_stream, write_stream = cm
                    
                else:
                    logger.error(f"Unknown transport '{transport}' for server {s['name']}")
                    continue
                
                logger.debug(f"Creating ClientSession for {s['name']}")
                sess = ClientSession(read_stream, write_stream)
                
                # ClientSession needs to be entered as a context manager
                logger.debug(f"Entering ClientSession context for {s['name']}")
                try:
                    await sess.__aenter__()
                except Exception as e:
                    logger.error(f"❌ Error entering session context for {s['name']}: {e}", exc_info=True)
                    continue
                
                logger.info(f"Initializing MCP session for {s['name']}...")
                try:
                    # Try initializing with a reasonable timeout
                    init_result = await asyncio.wait_for(sess.initialize(), timeout=30.0)
                    logger.info(f"✅ Session initialized for {s['name']}: {init_result}")
                except asyncio.TimeoutError:
                    logger.error(f"❌ Timeout (30s) initializing session for {s['name']}")
                    logger.error(f"   This usually means the MCP server is not responding to initialize request")
                    continue
                except Exception as e:
                    logger.error(f"❌ Error initializing session for {s['name']}: {type(e).__name__}: {e}", exc_info=True)
                    continue
                    
                sessions[s["name"]] = sess
                logger.info(f"✅ Connected to MCP server: {s['name']}")

                # List tools (per MCP spec)
                logger.debug(f"Listing tools from {s['name']}")
                tools_result = await sess.list_tools()
                tools = tools_result.tools if hasattr(tools_result, 'tools') else tools_result
                logger.info(f"Found {len(tools)} tools in {s['name']}")
                
                for t in tools:
                    if s.get("tools_allowlist") and t.name not in s["tools_allowlist"]:
                        logger.debug(f"Skipping tool {t.name} (not in allowlist)")
                        continue
                    tool_funcs.append(tool_to_openai_function(s["name"], t))
                    logger.info(f"✅ Added tool: {s['name']}:{t.name}")
            except Exception as e:
                logger.error(f"❌ Failed to connect to MCP server {s['name']}: {e}", exc_info=True)
                continue

        # Publish merged registry for llm-worker (retained so new subscribers get it)
        registry_payload = orjson.dumps({"tools": tool_funcs})
        logger.info(f"Publishing {len(tool_funcs)} tools to registry (payload size: {len(registry_payload)} bytes, retained=True)")
        await mqtt.publish("llm/tools/registry", registry_payload, qos=1, retain=True)
        logger.info(f"✅ Published {len(tool_funcs)} tools to llm/tools/registry (retained)")

        # Publish health
        await mqtt.publish("system/health/mcp-bridge", orjson.dumps({"ok": True, "event": "ready"}), retain=True)

        # Handle tool calls from llm-worker
        await mqtt.subscribe("llm/tool.call.request/#")
        logger.info("Subscribed to tool call requests")
        async for m in mqtt.messages:
                try:
                    msg = orjson.loads(m.payload)
                    # Extract data payload (message is wrapped in event envelope)
                    req = msg.get("data", msg)  # Support both wrapped and direct formats
                    # Parse new format: "mcp__server__tool"
                    parts = req["name"].split("__")
                    if len(parts) != 3 or parts[0] != "mcp":
                        raise ValueError(f"Invalid tool name format: {req['name']}")
                    _, server, tool = parts
                    args = req.get("arguments", {})
                    logger.info(f"Tool call: {server}:{tool} with args: {args}")
                    result = await sessions[server].call_tool(tool, args)  # SDK invoke
                    logger.debug(f"Tool result type: {type(result)}, hasattr content: {hasattr(result, 'content')}")
                    # Extract content from CallToolResult (has content array with TextContent/ImageContent/etc)
                    result_content = []
                    for content_item in result.content:
                        if hasattr(content_item, 'text'):
                            result_content.append(content_item.text)
                        elif hasattr(content_item, 'model_dump'):
                            result_content.append(content_item.model_dump())
                    # Join text content or return structured content
                    result_value = " ".join(result_content) if all(isinstance(c, str) for c in result_content) else result_content
                    logger.info(f"Tool result extracted: {result_value}")
                    await mqtt.publish("llm/tool.call.result", orjson.dumps({
                        "call_id": req["call_id"], "result": result_value
                    }), qos=1)
                    logger.info(f"✅ Tool call result published for call_id: {req['call_id']}")
                except Exception as e:
                    logger.error(f"Tool call failed: {e}")
                    # Publish error result
                    try:
                        call_id = req.get("call_id", "unknown")
                        await mqtt.publish("llm/tool.call.result", orjson.dumps({
                            "call_id": call_id, "error": str(e)
                        }), qos=1)
                    except:
                        pass

        # Cleanup: close all active contexts
        for context, _ in active_contexts:
            try:
                await context.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing context: {e}")

if __name__ == "__main__":
    asyncio.run(main())
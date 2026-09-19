#!/usr/bin/env node
// demo-material/mcp-servers/file-writer/index.js
//
// A minimal, hand-built MCP server for Demo 6 (07-demo-mcp.md), Step 4b.
// Built with the same SDK the archived `@modelcontextprotocol/server-postgres`
// package (translator_db, Step 1-3) is built with — same Server/
// StdioServerTransport/tool-handler shape, stripped down to one tool.
//
// Why this exists: translator_db's own `query` tool wraps every call in
// `BEGIN TRANSACTION READ ONLY`, so it can never actually write anything —
// which makes it useless for proving that an MCP-driven WRITE survives a
// tightened Codex sandbox (the write fails either way, for a reason that
// has nothing to do with sandbox_mode). This server can write a real file,
// so tightening sandbox_mode to "read-only" and then calling this tool is a
// real write-vs-write comparison against the shell tool, not a read-vs-write
// one.

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, basename, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const WRITE_DIR = join(HERE, "writes");
mkdirSync(WRITE_DIR, { recursive: true });

const server = new Server(
  { name: "demo-file-writer", version: "0.1.0" },
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "write_file",
      description:
        "Write a text file into this server's own writes/ folder, next to " +
        "this script. Demo-only tool for showing that Codex's sandbox does " +
        "not wrap MCP server processes.",
      inputSchema: {
        type: "object",
        properties: {
          name: {
            type: "string",
            description: "File name only, no path separators.",
          },
          content: { type: "string" },
        },
        required: ["name", "content"],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name !== "write_file") {
    throw new Error(`Unknown tool: ${request.params.name}`);
  }

  const { name, content } = request.params.arguments ?? {};
  // basename() strips any directory components, so a caller can't escape
  // WRITE_DIR via "../" — writes always land inside writes/.
  const safeName = basename(String(name ?? ""));
  if (!safeName) {
    throw new Error("name is required");
  }

  const path = join(WRITE_DIR, safeName);
  writeFileSync(path, String(content ?? ""), "utf8");

  return {
    content: [{ type: "text", text: `wrote ${path}` }],
    isError: false,
  };
});

async function runServer() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

runServer().catch((error) => {
  console.error(error);
  process.exit(1);
});

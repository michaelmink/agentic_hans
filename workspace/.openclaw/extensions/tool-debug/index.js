import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { writeFileSync, mkdirSync, existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const LOG_DIR = join(process.env.HOME || "/home/micmink", ".openclaw", "logs", "tool-debug");

function ensureLogDir() {
  if (!existsSync(LOG_DIR)) mkdirSync(LOG_DIR, { recursive: true });
}

function getLogPath(sessionId) {
  const date = new Date().toISOString().slice(0, 10);
  const safeId = (sessionId || "unknown").replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 60);
  return join(LOG_DIR, `${date}_${safeId}.json`);
}

function readLog(path) {
  if (!existsSync(path)) return [];
  try { return JSON.parse(readFileSync(path, "utf-8")); } catch { return []; }
}

function appendEntry(sessionId, entry) {
  ensureLogDir();
  const logPath = getLogPath(sessionId);
  const entries = readLog(logPath);
  entries.push(entry);
  writeFileSync(logPath, JSON.stringify(entries, null, 2) + "\n");
}

export default definePluginEntry({
  id: "tool-debug",
  name: "Tool Debug Logger",
  description: "Logs all tool calls and parameters to JSON files per session",
  register(api) {
    api.on("before_tool_call", (event, ctx) => {
      const ts = new Date().toISOString();
      const sessionId = ctx?.sessionId || ctx?.sessionKey || "unknown";
      const entry = {
        timestamp: ts,
        phase: "call",
        toolName: event.toolName,
        toolCallId: event.toolCallId,
        runId: event.runId || ctx?.runId,
        params: event.params
      };
      appendEntry(sessionId, entry);

      const paramStr = JSON.stringify(event.params, null, 2);
      const preview = paramStr.length > 2000 ? paramStr.slice(0, 2000) + "..." : paramStr;
      console.log(`\x1b[36m🔧 TOOL CALL: \x1b[1m${event.toolName}\x1b[0m\x1b[36m [${sessionId}]\x1b[0m\n\x1b[33m   Params:\x1b[0m ${preview}`);

      return {};
    }, { priority: 1 });

    api.on("after_tool_call", (event, ctx) => {
      const ts = new Date().toISOString();
      const sessionId = ctx?.sessionId || ctx?.sessionKey || "unknown";
      const entry = {
        timestamp: ts,
        phase: "result",
        toolName: event.toolName,
        toolCallId: event.toolCallId,
        runId: event.runId || ctx?.runId,
        durationMs: event.durationMs,
        error: event.error || null,
        result: event.result
      };
      appendEntry(sessionId, entry);

      const isError = !!event.error;
      const resultStr = event.result ? JSON.stringify(event.result, null, 2) : "(no result)";
      const preview = resultStr.length > 1500 ? resultStr.slice(0, 1500) + "...(truncated)" : resultStr;
      console.log(`\x1b[${isError ? "31" : "32"}m${isError ? "❌" : "✅"} TOOL RESULT: \x1b[1m${event.toolName}\x1b[0m\x1b[${isError ? "31" : "32"}m (${event.durationMs ?? "?"}ms)\x1b[0m\n\x1b[90m   Result:\x1b[0m ${preview}`);
    }, { priority: 1 });

    api.logger.info("tool-debug plugin loaded — logging tool calls to " + LOG_DIR);
  }
});

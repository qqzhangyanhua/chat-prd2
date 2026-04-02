import type { WorkspaceEvent } from "./types";


function normalizeChunk(chunk: string): string {
  return chunk.replace(/\r\n/g, "\n");
}


export function parseSseEventBlock(block: string): WorkspaceEvent | null {
  const lines = block
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const eventLine = lines.find((line) => line.startsWith("event:"));
  const dataLines = lines.filter((line) => line.startsWith("data:"));
  if (!eventLine || dataLines.length === 0) {
    return null;
  }

  const type = eventLine.slice("event:".length).trim() as WorkspaceEvent["type"];
  const payloadText = dataLines
    .map((line) => line.slice("data:".length).trim())
    .join("");

  return {
    type,
    data: JSON.parse(payloadText) as WorkspaceEvent["data"],
  } as WorkspaceEvent;
}


export async function* parseEventStream(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<WorkspaceEvent, void, void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += normalizeChunk(decoder.decode(value, { stream: true }));
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";

    for (const block of blocks) {
      const event = parseSseEventBlock(block);
      if (event) {
        yield event;
      }
    }
  }

  buffer += normalizeChunk(decoder.decode());
  if (buffer.trim()) {
    const event = parseSseEventBlock(buffer);
    if (event) {
      yield event;
    }
  }
}

// WebSocket client (T022) — native WebSocket, auto-reconnect, seq backfill.
// research R5/R9: resume by last_seen_seq, dedup by seq (SC-006).

export interface ActivityMessage {
  type: "activity";
  seq: number;
  event: { type: string; payload: Record<string, unknown>; tool_id?: string | null };
}

type Handler = (msg: ActivityMessage) => void;

export class WsClient {
  private ws: WebSocket | null = null;
  private lastSeenSeq = 0;
  private seenSeqs = new Set<number>();
  private reconnectDelay = 500;
  private handlers: Handler[] = [];
  private closed = false;

  constructor(private sessionId: string) {}

  onActivity(h: Handler): void {
    this.handlers.push(h);
  }

  connect(): void {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${location.host}/ws/sessions/${this.sessionId}?last_seen_seq=${this.lastSeenSeq}`;
    this.ws = new WebSocket(url);
    this.ws.onmessage = (e) => {
      const msg = JSON.parse(e.data) as ActivityMessage;
      if (msg.type === "activity") {
        if (this.seenSeqs.has(msg.seq)) return; // dedup on reconnect
        this.seenSeqs.add(msg.seq);
        this.lastSeenSeq = Math.max(this.lastSeenSeq, msg.seq);
        this.handlers.forEach((h) => h(msg));
      }
    };
    this.ws.onclose = () => {
      if (this.closed) return;
      // ponytail: exponential backoff capped at 5s.
      setTimeout(() => this.connect(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 5000);
    };
    this.ws.onopen = () => {
      this.reconnectDelay = 500;
    };
  }

  send(obj: unknown): void {
    this.ws?.send(JSON.stringify(obj));
  }

  close(): void {
    this.closed = true;
    this.ws?.close();
  }
}

export class WebSocketClient {
    sessionId: string;
    ws: WebSocket | null;
    listeners: Map<string, Array<(data: any) => void>>;
  
    constructor(sessionId: string) {
      this.sessionId = sessionId;
      this.ws = null;
      this.listeners = new Map();
    }
  
    connect() {
      const WS_URL = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000';

      this.ws = new WebSocket(`${WS_URL}/ws/session/${this.sessionId}`);
  
      this.ws.onopen = () => {
        console.log('WebSocket connected');
      };
  
      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.emit(data.type, data);
        } catch (e) {
          console.error("Failed to parse websocket message:", e);
        }
      };
  
      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
  
      this.ws.onclose = () => {
        console.log('WebSocket disconnected. Attempting to reconnect in 5s...');
        // Auto-reconnect
        setTimeout(() => this.connect(), 5000);
      };
    }
  
    on(eventType: string, callback: (data: any) => void) {
      if (!this.listeners.has(eventType)) {
        this.listeners.set(eventType, []);
      }
      this.listeners.get(eventType)?.push(callback);
    }
  
    emit(eventType: string, data: any) {
      const callbacks = this.listeners.get(eventType) || [];
      callbacks.forEach((callback) => callback(data));
    }
  
    disconnect() {
      if (this.ws) {
        // Prevent auto-reconnect on manual disconnect
        this.ws.onclose = null;
        this.ws.close();
      }
    }
  }
  

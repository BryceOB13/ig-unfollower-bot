import { useEffect, useRef, useCallback } from 'react';
import { useAppStore } from '../stores/appStore';
import type { WSMessage } from '../types';

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number>();

  const {
    setBrowserConnected,
    setLoggedIn,
    updateOperationProgress,
    setActiveOperation,
  } = useAppStore();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);

        switch (msg.type) {
          case 'status_change':
            if (msg.browser !== undefined) setBrowserConnected(msg.browser);
            if (msg.logged_in !== undefined) setLoggedIn(msg.logged_in);
            break;

          case 'progress':
            if (msg.current !== undefined && msg.total !== undefined) {
              updateOperationProgress(msg.current, msg.total, msg.message || '');
            }
            break;

          case 'operation_complete':
            setActiveOperation(null);
            break;

          case 'heartbeat':
            // Ignore heartbeats
            break;
        }
      } catch (e) {
        console.error('WebSocket message parse error:', e);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected, reconnecting...');
      reconnectTimeoutRef.current = window.setTimeout(connect, 3000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }, [setBrowserConnected, setLoggedIn, updateOperationProgress, setActiveOperation]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  const sendMessage = useCallback((message: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(message);
    }
  }, []);

  return { sendMessage };
}

import React, { useEffect, useRef, useState } from 'react';
import { Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import clsx from 'clsx';

const TERMINAL_STATES = new Set(['completed', 'failed', 'cancelled']);

function buildWebSocketUrl(jobId) {
    const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/v1';
    const secure = window.location.protocol === 'https:';

    if (/^https?:\/\//i.test(apiBase)) {
        const parsed = new URL(apiBase);
        const wsProtocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${wsProtocol}//${parsed.host}${parsed.pathname}/jobs/${jobId}/ws`;
    }

    const protocol = secure ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}${apiBase}/jobs/${jobId}/ws`;
}

async function fetchJobStatus(jobId) {
    const token = localStorage.getItem('cn_access_token');
    const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/v1';
    const url = `${apiBase}/jobs/${jobId}/status`;
    const res = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(`Polling failed: ${res.status}`);
    return res.json();
}

export default function LiveJobTracker({ jobId, onComplete, onTerminal }) {
    const [status, setStatus] = useState('pending');
    const [progress, setProgress] = useState(0);
    const [message, setMessage] = useState('Initializing job tracker...');
    const [connectionMode, setConnectionMode] = useState('connecting'); // connecting | live | fallback

    const wsRef = useRef(null);
    const reconnectTimerRef = useRef(null);
    const reconnectAttemptsRef = useRef(0);
    const pollIntervalRef = useRef(null);
    const terminalNotifiedRef = useRef(false);

    const notifyTerminal = (payload) => {
        const nextStatus = String(payload?.status || '').toLowerCase();
        if (!TERMINAL_STATES.has(nextStatus) || terminalNotifiedRef.current) return;

        terminalNotifiedRef.current = true;
        onTerminal?.({
            status: nextStatus,
            progress: payload?.progress,
            message: payload?.message,
            error: payload?.error,
            result: payload?.result,
        });

        if (nextStatus === 'completed' && onComplete) {
            onComplete(payload?.result);
        }
    };

    const applyJobUpdate = (raw) => {
        const nextStatus = String(raw?.status || '').toLowerCase();
        if (nextStatus) setStatus(nextStatus);
        if (raw?.progress !== undefined) setProgress(Math.max(0, Math.min(100, Number(raw.progress) || 0)));
        if (raw?.message) setMessage(raw.message);

        if (TERMINAL_STATES.has(nextStatus)) {
            notifyTerminal(raw);
        }
    };

    const stopPolling = () => {
        if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
        }
    };

    const startPollingFallback = () => {
        if (pollIntervalRef.current) return;
        setConnectionMode('fallback');

        const poll = async () => {
            try {
                const data = await fetchJobStatus(jobId);
                applyJobUpdate(data);
                if (TERMINAL_STATES.has(String(data?.status || '').toLowerCase())) {
                    stopPolling();
                }
            } catch {
                // silent retry via interval
            }
        };

        poll();
        pollIntervalRef.current = setInterval(poll, 4000);
    };

    const closeWebSocket = () => {
        const ws = wsRef.current;
        if (!ws) return;
        ws.onopen = null;
        ws.onmessage = null;
        ws.onerror = null;
        ws.onclose = null;
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
            ws.close();
        }
        wsRef.current = null;
    };

    useEffect(() => {
        if (!jobId) return;

        terminalNotifiedRef.current = false;
        reconnectAttemptsRef.current = 0;

        const connect = () => {
            if (terminalNotifiedRef.current) return;

            let ws;
            try {
                const wsUrl = buildWebSocketUrl(jobId);
                ws = new WebSocket(wsUrl);
                wsRef.current = ws;
            } catch {
                startPollingFallback();
                return;
            }

            ws.onopen = () => {
                reconnectAttemptsRef.current = 0;
                setConnectionMode('live');
                stopPolling();
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    applyJobUpdate(data);
                } catch {
                    // ignore malformed events
                }
            };

            ws.onerror = () => {
                // Switch to polling quickly on errors for better UX reliability.
                startPollingFallback();
            };

            ws.onclose = () => {
                if (terminalNotifiedRef.current) return;

                reconnectAttemptsRef.current += 1;
                const attempts = reconnectAttemptsRef.current;
                if (attempts <= 5) {
                    const delay = Math.min(2000 * attempts, 8000);
                    reconnectTimerRef.current = setTimeout(connect, delay);
                } else {
                    startPollingFallback();
                }
            };
        };

        connect();

        return () => {
            if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
            closeWebSocket();
            stopPolling();
        };
    }, [jobId]);

    return (
        <div className="bg-white border border-neutral-200 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-neutral-900 flex items-center gap-2">
                    {status === 'pending' || status === 'running' ? <Loader2 size={16} className="animate-spin text-neutral-500" /> : null}
                    Live Job Progress
                </h3>
                <span className={clsx(
                    "text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full border",
                    connectionMode === 'live'
                        ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                        : connectionMode === 'fallback'
                            ? "bg-amber-50 text-amber-700 border-amber-200"
                            : "bg-neutral-100 text-neutral-600 border-neutral-200"
                )}>
                    {connectionMode === 'live' ? 'live' : connectionMode === 'fallback' ? 'sync' : 'connecting'}
                </span>
            </div>

            <div className="mb-2 flex items-center justify-between text-xs">
                <span className="text-neutral-500 truncate mr-3">{message}</span>
                <span className="text-neutral-900 font-medium shrink-0">{Math.floor(progress)}%</span>
            </div>

            <div className="w-full h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                <div
                    className={clsx(
                        "h-full transition-all duration-300 rounded-full",
                        status === 'failed' ? 'bg-red-500' :
                            status === 'completed' ? 'bg-emerald-500' :
                                'bg-neutral-900'
                    )}
                    style={{ width: `${Math.max(2, progress)}%` }}
                />
            </div>

            {status === 'completed' && (
                <div className="mt-4 flex items-start gap-2 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 p-3 rounded-lg">
                    <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
                    <span>Job completed successfully!</span>
                </div>
            )}

            {(status === 'failed' || status === 'cancelled') && (
                <div className="mt-4 flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 p-3 rounded-lg">
                    <AlertCircle size={16} className="mt-0.5 shrink-0" />
                    <span>{status === 'cancelled' ? 'Job was cancelled.' : 'Job encountered an error.'}</span>
                </div>
            )}
        </div>
    );
}

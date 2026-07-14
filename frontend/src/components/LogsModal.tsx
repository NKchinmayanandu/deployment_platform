import { useEffect, useRef } from 'react';
import { X, AlertCircle } from 'lucide-react';
import { useDeploymentLogs } from '../hooks/useDeployments';

interface LogsModalProps {
  appId: number;
  appName: string;
  onClose: () => void;
}

export function LogsModal({ appId, appName, onClose }: LogsModalProps) {
  const { data, isLoading, isError } = useDeploymentLogs(appId, true);
  const scrollRef = useRef<HTMLDivElement>(null);
  
  const logs = data?.logs ?? [];

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end p-4 sm:p-6 md:p-8">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-ink/30 backdrop-blur-[2px]"
        onClick={onClose}
      />

      {/* Modal / Drawer */}
      <div className="relative card w-full max-w-4xl mx-auto h-[70vh] flex flex-col bg-surface-card z-10 shadow-2xl overflow-hidden rounded-t-lg sm:rounded-lg">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-hairline bg-canvas">
          <div className="flex items-center gap-3">
            <div className="w-2.5 h-2.5 rounded-full bg-[#ff5f56]" />
            <div className="w-2.5 h-2.5 rounded-full bg-[#ffbd2e]" />
            <div className="w-2.5 h-2.5 rounded-full bg-[#27c93f]" />
            <span className="ml-2 text-caption text-ink font-mono font-medium">
              logs — {appName}
            </span>
          </div>
          <button
            className="btn-ghost w-8 h-8 p-0"
            onClick={onClose}
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        {/* Terminal Body */}
        <div 
          className="flex-1 bg-[#1e1e1e] p-4 overflow-y-auto"
          ref={scrollRef}
        >
          {isLoading && (
            <div className="flex items-center gap-3 text-muted-soft font-mono text-[13px]">
              <div className="w-3 h-3 rounded-full border-2 border-[#ffffff33] border-t-white animate-spin" />
              <span>Fetching logs...</span>
            </div>
          )}

          {isError && (
            <div className="flex items-center gap-2 text-semantic-error font-mono text-[13px]">
              <AlertCircle size={14} />
              <span>Failed to load logs.</span>
            </div>
          )}

          {!isLoading && !isError && logs.length === 0 && (
            <div className="text-muted-soft font-mono text-[13px]">
              No logs available.
            </div>
          )}

          {!isLoading && !isError && logs.length > 0 && (
            <div className="font-mono text-[13px] text-[#cccccc] leading-relaxed whitespace-pre-wrap">
              {logs.map((log: string, i: number) => (
                <div key={i} className="break-all">{log}</div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

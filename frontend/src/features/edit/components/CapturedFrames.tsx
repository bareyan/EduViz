import { Camera, AlertCircle } from 'lucide-react';

interface CapturedFrame {
  dataUrl: string;
  time: number;
}

interface CapturedFramesProps {
  frames: CapturedFrame[];
  onClearAll: () => void;
  onRemoveFrame: (idx: number) => void;
}

export function CapturedFrames({ 
  frames, 
  onClearAll, 
  onRemoveFrame 
}: CapturedFramesProps) {
  if (frames.length === 0) return null;

  return (
    <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-gray-400 flex items-center gap-2">
          <Camera className="w-4 h-4" /> CAPTURED CONTEXT ({frames.length})
        </h3>
        <button 
          onClick={onClearAll}
          className="text-xs text-red-400 hover:underline"
        >
          Clear All
        </button>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2">
        {frames.map((frame, idx) => (
          <div key={idx} className="relative shrink-0 group">
            <img 
              src={frame.dataUrl} 
              alt="Context" 
              className="h-20 rounded border border-gray-600 group-hover:border-blue-500 transition-colors"
            />
            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
              <button 
                onClick={() => onRemoveFrame(idx)}
                className="bg-red-500 p-1 rounded-full"
              >
                <AlertCircle className="w-4 h-4" />
              </button>
            </div>
            <span className="absolute bottom-0 left-0 right-0 bg-black/60 text-[10px] text-center">
              {frame.time.toFixed(1)}s
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

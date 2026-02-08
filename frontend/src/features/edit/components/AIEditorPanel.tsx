import { Wand2, RefreshCw, Terminal } from 'lucide-react';

interface AIEditorPanelProps {
  fixPrompt: string;
  setFixPrompt: (value: string) => void;
  isProcessing: boolean;
  capturedFramesCount: number;
  onFix: () => void;
  onRegenerate: () => void;
}

export function AIEditorPanel({
  fixPrompt,
  setFixPrompt,
  isProcessing,
  capturedFramesCount,
  onFix,
  onRegenerate
}: AIEditorPanelProps) {
  return (
    <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 h-full flex flex-col gap-4 shadow-xl text-left">
      <div className="flex items-center gap-2 text-purple-400">
        <Wand2 className="w-5 h-5" />
        <h3 className="font-bold text-lg">AI Vision Editor</h3>
      </div>
      
      <div className="flex-1 flex flex-col gap-2">
        <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
          What would you like to change?
        </label>
        <textarea
          value={fixPrompt}
          onChange={(e) => setFixPrompt(e.target.value)}
          placeholder="e.g. 'Move the text to the center', 'Make objects blue'..."
          className="flex-1 bg-gray-900 border border-gray-700 rounded-lg p-3 text-sm focus:ring-2 focus:ring-purple-500 outline-none resize-none transition-all"
        />
      </div>

      <div className="flex flex-col gap-2">
        <button
          onClick={onFix}
          disabled={isProcessing || (!fixPrompt.trim() && capturedFramesCount === 0)}
          className="w-full py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 disabled:from-gray-700 disabled:to-gray-700 rounded-lg font-bold flex items-center justify-center gap-2 shadow-lg transition-transform active:scale-95"
        >
          {isProcessing ? (
            <RefreshCw className="w-5 h-5 animate-spin" />
          ) : (
            <Wand2 className="w-5 h-5" />
          )}
          Ask AI to Fix & Regenerate
        </button>
        
        <button
          onClick={onRegenerate}
          disabled={isProcessing}
          className="w-full py-2 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg text-sm font-semibold flex items-center justify-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${isProcessing ? 'animate-spin' : ''}`} />
          Just Regenerate current code
        </button>
      </div>
      
      <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 text-xs text-blue-300">
        <p className="flex items-center gap-2">
          <Terminal className="w-3.5 h-3.5" />
          Tip: Pause the video at the moment of the issue and capture a frame.
        </p>
      </div>
    </div>
  );
}

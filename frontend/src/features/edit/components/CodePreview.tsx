import { Terminal } from 'lucide-react';

interface CodePreviewProps {
  code: string;
}

export function CodePreview({ code }: CodePreviewProps) {
  return (
    <div className="bg-gray-800 rounded-xl overflow-hidden border border-gray-700 shadow-xl text-left">
      <div className="bg-gray-900/50 p-3 border-b border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-2 text-gray-400">
          <Terminal className="w-4 h-4" />
          <span className="text-xs font-mono">manim_code.py</span>
        </div>
      </div>
      <div className="relative group">
        <pre className="p-4 text-xs font-mono text-gray-300 overflow-x-auto max-h-60 bg-[#1a1b26]">
          <code>{code}</code>
        </pre>
      </div>
    </div>
  );
}

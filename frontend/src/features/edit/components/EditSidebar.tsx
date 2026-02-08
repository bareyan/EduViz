import { Play } from 'lucide-react';
import { SectionEdit } from '../../../types/job.types';
import { formatDuration } from '../../../utils/format.utils';

interface EditSidebarProps {
  sections: SectionEdit[];
  selectedSection: SectionEdit | null;
  onSelectSection: (section: SectionEdit) => void;
}

export function EditSidebar({ 
  sections, 
  selectedSection, 
  onSelectSection 
}: EditSidebarProps) {
  return (
    <div className="w-80 bg-gray-800 border-r border-gray-700 flex flex-col h-full">
      <div className="p-4 border-b border-gray-700">
        <h2 className="font-semibold text-gray-300">Sections ({sections.length})</h2>
      </div>
      <div className="flex-1 overflow-y-auto">
        {sections.map((section, index) => (
          <button
            key={section.id}
            onClick={() => onSelectSection(section)}
            className={`w-full p-4 flex flex-col gap-1 text-left border-b border-gray-700 transition-all ${
              selectedSection?.id === section.id 
                ? 'bg-blue-600/20 border-l-4 border-l-blue-500' 
                : 'hover:bg-gray-700/50'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                Section {index + 1}
              </span>
              <span className="text-xs text-gray-500">
                {formatDuration(section.duration_seconds || 0)}
              </span>
            </div>
            <h3 className="font-semibold truncate text-gray-200">{section.title}</h3>
            <div className="flex items-center gap-2 mt-1">
              {section.video ? (
                <span className="flex items-center gap-1 text-[10px] bg-green-500/10 text-green-400 px-1.5 py-0.5 rounded border border-green-500/20">
                  <Play className="w-2.5 h-2.5" /> VIDEO Ready
                </span>
              ) : (
                <span className="text-[10px] bg-yellow-500/10 text-yellow-500 px-1.5 py-0.5 rounded border border-yellow-500/20">
                  NO VIDEO
                </span>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

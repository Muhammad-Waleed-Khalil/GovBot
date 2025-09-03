import React, { useState, useRef } from 'react';
import { ExternalLink } from 'lucide-react';

interface Source {
  id: string;
  title: string;
  url: string;
  snippet: string;
}

interface CitationsProps {
  sources: Source[];
}

const Citations: React.FC<CitationsProps> = ({ sources }) => {
  const [isHovered, setIsHovered] = useState(false);
  const hoverTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  const handleCitationClick = (url: string) => {
    // For now, redirect to a placeholder page
    window.open('/under-development', '_blank');
  };

  if (!sources || sources.length === 0) {
    return null;
  }

  return (
    <div 
      className="relative inline-block"
      onMouseEnter={() => {
        if (hoverTimeoutRef.current) {
          clearTimeout(hoverTimeoutRef.current);
          hoverTimeoutRef.current = null;
        }
        setIsHovered(true);
      }}
      onMouseLeave={() => {
        hoverTimeoutRef.current = setTimeout(() => {
          setIsHovered(false);
        }, 150);
      }}
    >
      {/* Citation trigger - shows citation numbers */}
      <div className="inline-flex items-center gap-1 mt-2 cursor-pointer">
        <span className="text-xs text-gray-500 font-medium">Sources:</span>
        {sources.slice(0, 3).map((source, index) => (
          <span
            key={source.id}
            className="inline-flex items-center justify-center w-5 h-5 bg-blue-500 text-white rounded-full text-xs font-semibold hover:bg-blue-600 transition-colors"
          >
            {source.id}
          </span>
        ))}
        {sources.length > 3 && (
          <span className="text-xs text-gray-500">+{sources.length - 3} more</span>
        )}
      </div>

      {/* Citation popup - shows on hover */}
      {isHovered && (
        <div 
          className="absolute bottom-full left-0 mb-1 w-96 max-h-80 overflow-hidden bg-white/80 backdrop-blur-2xl border border-white/20 rounded-3xl shadow-2xl shadow-black/5 z-50 transform transition-all duration-300 ease-out animate-in fade-in-0 slide-in-from-bottom-2 zoom-in-95"
          onMouseEnter={() => {
            if (hoverTimeoutRef.current) {
              clearTimeout(hoverTimeoutRef.current);
              hoverTimeoutRef.current = null;
            }
            setIsHovered(true);
          }}
          onMouseLeave={() => {
            hoverTimeoutRef.current = setTimeout(() => {
              setIsHovered(false);
            }, 150);
          }}
          style={{
            backdropFilter: 'blur(20px) saturate(180%)',
            WebkitBackdropFilter: 'blur(20px) saturate(180%)',
            background: 'rgba(255, 255, 255, 0.85)'
          }}
        >
          {/* Header with subtle gradient */}
          <div className="bg-gradient-to-r from-gray-50/60 to-blue-50/40 px-5 py-4 border-b border-white/30">
            <div className="flex items-center gap-3">
              <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse"></div>
              <h3 className="text-sm font-semibold text-gray-900 tracking-tight">Sources</h3>
              <div className="ml-auto text-xs text-gray-600 bg-white/60 px-3 py-1.5 rounded-full font-medium">
                {sources.length}
              </div>
            </div>
          </div>
          
          {/* Scrollable content with invisible scrollbar */}
          <div className="max-h-64 overflow-y-auto" style={{
            scrollbarWidth: 'none',
            msOverflowStyle: 'none',
            WebkitScrollbar: { display: 'none' }
          }}>
            <style jsx>{`
              div::-webkit-scrollbar {
                display: none;
              }
            `}</style>
            <div className="p-5 space-y-2">
              {sources.map((source, index) => (
                 <div
                   key={source.id}
                   className="group relative flex items-start gap-4 p-4 rounded-2xl hover:bg-white/60 transition-all duration-200 ease-out cursor-pointer border border-transparent hover:border-white/40 hover:shadow-lg hover:shadow-black/5 transform hover:scale-[1.02]"
                   style={{
                     transitionTimingFunction: 'cubic-bezier(0.4, 0.0, 0.2, 1)'
                   }}
                   onClick={() => handleCitationClick(source.url)}
                 >
                   {/* Source number with Apple-style design */}
                   <div className="flex-shrink-0 w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-full flex items-center justify-center text-xs font-semibold shadow-sm group-hover:shadow-md transition-all duration-200 ease-out group-hover:scale-105">
                     {source.id}
                   </div>
                   
                   <div className="flex-1 min-w-0">
                     <div className="flex items-center gap-2 mb-1.5">
                       <h4 className="text-sm font-semibold text-gray-900 truncate group-hover:text-blue-600 transition-colors duration-200 leading-snug">
                         {source.title}
                       </h4>
                       <ExternalLink className="w-3.5 h-3.5 text-gray-400 group-hover:text-blue-500 transition-all duration-200 ease-out opacity-0 group-hover:opacity-100 transform translate-x-1 group-hover:translate-x-0" />
                     </div>
                     <p className="text-xs text-gray-600 leading-relaxed line-clamp-2 group-hover:text-gray-700 transition-colors duration-200">
                       {source.snippet}
                     </p>
                   </div>
                   
                   {/* Subtle hover glow */}
                   <div className="absolute inset-0 rounded-2xl bg-gradient-to-r from-blue-500/3 to-blue-600/3 opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none"></div>
                 </div>
               ))}
            </div>
          </div>
          
          {/* Footer with Apple-style subtle design */}
          <div className="bg-gradient-to-r from-white/40 to-gray-50/40 px-5 py-3 border-t border-white/30">
            <p className="text-xs text-gray-600 text-center font-medium tracking-wide">
              Tap to explore sources
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default Citations;
import { Network, ShieldCheck } from 'lucide-react';

export interface GraphSource {
  label: string;
  url: string;
}

interface KnowledgeGraphCardProps {
  query: string;
  sources: GraphSource[];
}

const sourceColour = (index: number) => {
  const shades = ['#006a4e', '#0f766e', '#2563eb'];
  return shades[index % shades.length];
};

const KnowledgeGraphCard = ({ query, sources }: KnowledgeGraphCardProps) => {
  const nodes = sources.slice(0, 3);

  if (!query || nodes.length === 0) return null;

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_12px_32px_-24px_rgba(15,23,42,0.35)]">
      <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-4 py-3.5">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#006a4e]">Knowledge graph</p>
          <h2 className="mt-1 text-sm font-semibold text-slate-900">খোঁজার সংযোগ</h2>
          <p className="mt-1 text-xs text-slate-500">বর্তমান ফলাফলের উৎস-মানচিত্র</p>
        </div>
        <Network className="mt-0.5 h-4 w-4 text-[#006a4e]" aria-hidden="true" />
      </div>

      <div className="px-3 pt-3">
        <svg viewBox="0 0 288 158" className="h-auto w-full" role="img" aria-label={`খোঁজো source graph for ${query}`}>
          <title>Source connections for {query}</title>
          <defs>
            <linearGradient id="khujoGraphSurface" x1="0" x2="1" y1="0" y2="1">
              <stop offset="0%" stopColor="#ecfdf5" />
              <stop offset="100%" stopColor="#eff6ff" />
            </linearGradient>
          </defs>
          <rect x="0.5" y="0.5" width="287" height="157" rx="14" fill="url(#khujoGraphSurface)" stroke="#dbe7e1" />
          {nodes.map((source, index) => {
            const y = 35 + index * 45;
            return (
              <g key={source.url}>
                <path d={`M143 79 C 185 79, 190 ${y}, 222 ${y}`} fill="none" stroke={sourceColour(index)} strokeWidth="1.5" opacity="0.58" />
                <circle cx="226" cy={y} r="14" fill={sourceColour(index)} opacity="0.95" />
                <text x="226" y={y + 4} fill="white" fontSize="10" fontWeight="600" textAnchor="middle">{index + 1}</text>
                <text x="246" y={y + 4} fill="#334155" fontSize="10.5">{source.label.slice(0, 12)}</text>
              </g>
            );
          })}
          <circle cx="116" cy="79" r="31" fill="#006a4e" />
          <circle cx="116" cy="79" r="24" fill="none" stroke="white" strokeOpacity="0.35" />
          <text x="116" y="76" fill="white" fontSize="11" fontWeight="600" textAnchor="middle">খোঁজ</text>
          <text x="116" y="91" fill="white" fontSize="9" textAnchor="middle">{query.slice(0, 15)}</text>
        </svg>
      </div>

      <div className="px-4 pb-4 pt-2">
        <div className="flex items-center gap-1.5 text-[11px] leading-relaxed text-slate-500">
          <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-[#006a4e]" aria-hidden="true" />
          <span>এটি বর্তমান ফলাফলের উৎস-সংযোগ। যাচাইকৃত তথ্য এলে এখানে সত্তা ও প্রমাণও দেখা যাবে।</span>
        </div>
      </div>
    </section>
  );
};

export default KnowledgeGraphCard;

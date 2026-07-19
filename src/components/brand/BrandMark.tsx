import { Link } from 'react-router-dom';

interface BrandMarkProps {
  compact?: boolean;
  className?: string;
}

const BrandMark = ({ compact = false, className = '' }: BrandMarkProps) => (
  <Link
    to="/"
    className={`inline-flex items-center gap-2.5 text-slate-950 transition-opacity hover:opacity-80 ${className}`}
    aria-label="খোঁজো হোম"
  >
    <span className="relative grid h-9 w-9 place-items-center rounded-xl bg-[#006a4e] shadow-sm shadow-emerald-900/15">
      <span className="h-3.5 w-3.5 rounded-full border-[3px] border-white" />
      <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-[#ef4444]" />
    </span>
    {!compact && (
      <span className="flex flex-col leading-none">
        <span className="text-lg font-semibold tracking-[-0.04em]">khujo</span>
        <span className="mt-1 text-[9px] font-semibold uppercase tracking-[0.2em] text-[#006a4e]">বাংলার খোঁজ</span>
      </span>
    )}
  </Link>
);

export default BrandMark;

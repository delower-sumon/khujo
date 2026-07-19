import React, { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowUpRight, ExternalLink, FileText, SearchX, Sparkles } from 'lucide-react';
import BrandMark from '../components/brand/BrandMark';
import KnowledgeGraphCard, { GraphSource } from '../components/search/KnowledgeGraphCard';
import SearchBar from '../components/search/SearchBar';

interface SearchResult {
  id: string;
  title: string;
  snippet: string;
  url: string;
  favicon?: string;
  source: string;
  timestamp?: string;
  type?: string;
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const sourceLabel = (result: SearchResult) => {
  try {
    return new URL(result.url).hostname.replace(/^www\./, '');
  } catch {
    return result.source;
  }
};

const ResultCard = ({ result }: { result: SearchResult }) => (
  <article className="group border-b border-slate-200/80 py-6 first:pt-0">
    <div className="mb-2 flex min-w-0 items-center gap-2 text-xs text-slate-500">
      {result.favicon ? <img src={result.favicon} alt="" className="h-4 w-4 rounded-sm" /> : <span className="grid h-4 w-4 place-items-center rounded bg-emerald-50 text-[#006a4e]"><FileText className="h-2.5 w-2.5" /></span>}
      <span className="truncate font-medium text-slate-700">{sourceLabel(result)}</span>
      <span className="text-slate-300">/</span>
      <span className="truncate">{result.url.replace(/^https?:\/\//, '')}</span>
    </div>
    <a href={result.url} target="_blank" rel="noopener noreferrer" className="group/link inline-flex items-start gap-1 text-lg font-semibold leading-snug tracking-[-0.02em] text-slate-900 transition-colors hover:text-[#006a4e] sm:text-xl">
      <span>{result.title}</span>
      <ArrowUpRight className="mt-1 h-4 w-4 shrink-0 opacity-0 transition-opacity group-hover/link:opacity-100" aria-hidden="true" />
    </a>
    <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{result.snippet}</p>
    <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
      <span className="rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-600">{result.source}</span>
      {result.timestamp && <span>{result.timestamp}</span>}
    </div>
  </article>
);

const SearchResultsPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const query = searchParams.get('q') || '';
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const fetchResults = async () => {
      if (!query) {
        setResults([]);
        setError(false);
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const response = await fetch(`${apiBaseUrl}/api/v1/search?q=${encodeURIComponent(query)}&limit=10&offset=0`);
        if (!response.ok) throw new Error('Search request failed');
        const data = await response.json();
        setResults((data.results || []).filter((result: SearchResult) => result.type !== 'crawl_queue'));
        setError(false);
      } catch (requestError) {
        console.error('Error fetching search results:', requestError);
        setResults([]);
        setError(true);
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, [query]);

  const sources = useMemo<GraphSource[]>(() => {
    const unique = new Map<string, GraphSource>();
    results.forEach((result) => {
      if (!result.url) return;
      const label = sourceLabel(result);
      if (!unique.has(label)) unique.set(label, { label, url: result.url });
    });
    return Array.from(unique.values());
  }, [results]);

  return (
    <div className="min-h-screen bg-[#fbfcfc] text-slate-900">
      <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/90 px-4 py-3.5 backdrop-blur sm:px-6">
        <div className="mx-auto flex max-w-7xl flex-col items-center gap-3 sm:flex-row sm:gap-6">
          <BrandMark compact className="hidden sm:inline-flex" />
          <Link to="/" className="sm:hidden"><BrandMark /></Link>
          <div className="w-full max-w-3xl"><SearchBar initialValue={query} className="w-full" /></div>
          <span className="hidden whitespace-nowrap text-xs text-slate-500 lg:inline">স্থানীয় জ্ঞানের খোঁজ</span>
        </div>
      </header>

      <nav className="border-b border-slate-200 bg-white px-4 sm:px-6" aria-label="Result categories">
        <div className="mx-auto flex max-w-7xl gap-5 overflow-x-auto">
          <button className="border-b-2 border-[#006a4e] px-1 py-3 text-sm font-medium text-[#006a4e]">সব ফলাফল</button>
          <span className="whitespace-nowrap px-1 py-3 text-sm text-slate-400">খবর ও স্থানভিত্তিক ফলাফল শিগগিরই</span>
        </div>
      </nav>

      <main className="mx-auto grid max-w-7xl gap-10 px-4 py-7 sm:px-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <section className="min-w-0 max-w-3xl">
          <div className="mb-7"><p className="text-sm text-slate-500">{loading ? 'খুঁজছে…' : `${results.length}টি উৎসে ফলাফল`} <span className="font-medium text-slate-900">“{query}”</span></p></div>
          {loading ? (
            <div className="space-y-7 animate-pulse">
              {[1, 2, 3].map((item) => <div key={item} className="space-y-3 border-b border-slate-100 pb-7"><div className="h-3 w-1/3 rounded bg-slate-100" /><div className="h-5 w-3/4 rounded bg-slate-100" /><div className="h-3 w-full rounded bg-slate-50" /><div className="h-3 w-4/5 rounded bg-slate-50" /></div>)}
            </div>
          ) : error ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-950">খোঁজো সার্ভারের সাথে এখন সংযোগ করা যাচ্ছে না। সার্ভার চালু হলে আবার চেষ্টা করুন।</div>
          ) : results.length === 0 ? (
            <div className="rounded-2xl border border-slate-200 bg-white px-5 py-8 text-center"><SearchX className="mx-auto h-6 w-6 text-slate-400" aria-hidden="true" /><h1 className="mt-3 font-semibold text-slate-900">এখনও কোনো ফলাফল নেই</h1><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">ভিন্ন বানান, Banglish বা আরও নির্দিষ্ট স্থান ব্যবহার করে আবার খুঁজুন।</p></div>
          ) : (
            <div>
              <section className="mb-1 rounded-2xl border border-emerald-100 bg-[linear-gradient(135deg,#ecfdf5_0%,#f0fdfa_52%,#ffffff_100%)] px-5 py-4">
                <div className="flex items-start gap-3"><span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-[#006a4e] text-white"><Sparkles className="h-3.5 w-3.5" /></span><div><p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#006a4e]">Khujo context</p><p className="mt-1 text-sm leading-6 text-slate-700">এই অনুসন্ধানে {sources.length}টি আলাদা উৎস পাওয়া গেছে। খোঁজো উৎসের ঠিকানা দেখায়, যাতে আপনি নিজে তথ্য যাচাই করতে পারেন।</p></div></div>
              </section>
              <div className="mt-2">{results.map((result) => <ResultCard key={result.id} result={result} />)}</div>
            </div>
          )}
        </section>

        <aside className="hidden flex-col gap-4 lg:flex">
          <KnowledgeGraphCard query={query} sources={sources} />
          {sources.length > 0 && <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_12px_32px_-24px_rgba(15,23,42,0.35)]"><p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Top sources</p><div className="mt-3 space-y-2">{sources.slice(0, 4).map((source) => <a key={source.url} href={source.url} target="_blank" rel="noopener noreferrer" className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-sm text-slate-700 transition-colors hover:bg-slate-50 hover:text-[#006a4e]"><span className="truncate">{source.label}</span><ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden="true" /></a>)}</div></section>}
        </aside>
      </main>

      <footer className="border-t border-slate-200 bg-white px-4 py-6 text-xs text-slate-500 sm:px-6"><div className="mx-auto flex max-w-7xl flex-wrap justify-between gap-3"><span>খোঁজো · বাংলাদেশের জন্য স্থানীয় অনুসন্ধান</span><span>উৎস দেখুন, তথ্য যাচাই করুন</span></div></footer>
    </div>
  );
};

export default SearchResultsPage;

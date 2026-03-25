import React, { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
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

const SearchResultsPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const query = searchParams.get('q') || '';
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchResults = async () => {
      if (!query) {
        setResults([]);
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const response = await fetch(
          `http://localhost:8000/api/v1/search?q=${encodeURIComponent(query)}&limit=10&offset=0`
        );

        if (response.ok) {
          const data = await response.json();
          setResults(data.results || []);
        } else {
          setResults([]);
        }
      } catch (error) {
        console.error('Error fetching search results:', error);
        setResults([]);
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, [query]);

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white border-b border-gray-100 px-4 py-3 sm:px-8 flex flex-col sm:flex-row items-center space-y-4 sm:space-y-0 sm:space-x-8">
        <Link to="/" className="flex items-center">
          <img src="/src/assets/khojo.png" alt="খোঁজো" className="h-8 w-auto" />
        </Link>

        <div className="w-full max-w-2xl">
          <SearchBar initialValue={query} className="w-full" />
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl px-4 sm:px-8 py-6">
        <p className="text-sm text-gray-500 mb-6">
          About {results.length} results for <span className="font-medium text-gray-900">"{query}"</span>
        </p>

        {loading ? (
          <div className="space-y-8 animate-pulse">
            {[1, 2, 3].map((i) => (
              <div key={i} className="space-y-2">
                <div className="h-4 bg-gray-100 rounded w-3/4"></div>
                <div className="h-3 bg-gray-50 rounded w-1/2"></div>
                <div className="h-3 bg-gray-50 rounded w-full"></div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-10">
            {results.map((result) => (
              <article key={result.id} className="group">
                <div className="flex items-center space-x-2 mb-1">
                  {result.favicon && (
                    <img src={result.favicon} alt="" className="w-4 h-4 rounded-sm" />
                  )}
                  <span className="text-xs text-gray-600 truncate max-w-xs">
                    {result.url}
                  </span>
                  <ChevronRight className="w-3 h-3 text-gray-400" />
                </div>
                <h2 className="text-xl text-[#1a0dab] hover:underline mb-1">
                  <a href={result.url} target="_blank" rel="noopener noreferrer">
                    {result.title}
                  </a>
                </h2>
                <p className="text-sm text-gray-700 leading-relaxed max-w-2xl">
                  {result.snippet}
                </p>
                <div className="mt-2 flex items-center space-x-3 text-xs text-gray-400">
                  <span className="bg-gray-50 px-2 py-0.5 rounded border border-gray-100">
                    {result.source}
                  </span>
                  {result.timestamp && <span>{result.timestamp}</span>}
                </div>
              </article>
            ))}
          </div>
        )}
      </main>

      {/* Simple Footer */}
      <footer className="mt-20 border-t border-gray-100 bg-gray-50 px-8 py-6 text-xs text-gray-500">
        <div className="max-w-4xl flex space-x-6">
          <span>Bangladesh</span>
          <a href="#" className="hover:underline">Help</a>
          <a href="#" className="hover:underline">Privacy</a>
          <a href="#" className="hover:underline">Terms</a>
        </div>
      </footer>
    </div>
  );
};

export default SearchResultsPage;

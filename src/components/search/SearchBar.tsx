import React, { useState, useEffect, useRef } from 'react';
import { Search, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface SearchBarProps {
  initialValue?: string;
  autoFocus?: boolean;
  className?: string;
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const SearchBar: React.FC<SearchBarProps> = ({ initialValue = '', autoFocus = false, className = '' }) => {
  const [query, setQuery] = useState(initialValue);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isFocusedRef = useRef(false);

  useEffect(() => {
    setQuery(initialValue);
  }, [initialValue]);

  useEffect(() => {
    const fetchSuggestions = async () => {
      if (!isFocusedRef.current || query.trim().length < 2) {
        setSuggestions([]);
        setShowSuggestions(false);
        setActiveIndex(-1);
        return;
      }

      try {
        const response = await fetch(`${apiBaseUrl}/api/v1/suggestions?q=${encodeURIComponent(query.trim())}&limit=8`);
        if (response.ok && isFocusedRef.current) {
          const data = await response.json();
          setSuggestions(data);
          setShowSuggestions(data.length > 0);
          setActiveIndex(-1);
        }
      } catch {
        setSuggestions([]);
        setShowSuggestions(false);
      }
    };

    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    debounceTimerRef.current = setTimeout(fetchSuggestions, 200);
    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    };
  }, [query]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) setShowSuggestions(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSearch = (event?: React.FormEvent, selectedQuery?: string) => {
    event?.preventDefault();
    const finalQuery = selectedQuery || query;
    if (!finalQuery.trim()) return;

    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    isFocusedRef.current = false;
    setShowSuggestions(false);
    setSuggestions([]);
    setActiveIndex(-1);
    navigate(`/search?q=${encodeURIComponent(finalQuery.trim())}`);
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Escape') {
      setShowSuggestions(false);
      setActiveIndex(-1);
      return;
    }
    if (!showSuggestions || suggestions.length === 0) return;

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveIndex((current) => Math.min(current + 1, suggestions.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex((current) => Math.max(current - 1, 0));
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const selected = activeIndex >= 0 ? suggestions[activeIndex] : query;
      setQuery(selected);
      handleSearch(undefined, selected);
    }
  };

  const hasSuggestions = showSuggestions && suggestions.length > 0;

  return (
    <div ref={containerRef} className={`relative w-full ${className}`}>
      <form onSubmit={(event) => handleSearch(event)} className="relative z-[60]">
        <div className={`relative flex w-full items-center border border-slate-200 bg-white px-4 py-3 transition-all duration-200 ${
          hasSuggestions
            ? 'rounded-t-2xl border-b-0 shadow-[0_18px_38px_-24px_rgba(15,23,42,0.42)]'
            : 'rounded-2xl shadow-sm hover:border-slate-300 hover:shadow-md focus-within:border-[#006a4e] focus-within:ring-4 focus-within:ring-emerald-50'
        }`}>
          <Search className="mr-3 h-5 w-5 shrink-0 text-[#006a4e]" aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setActiveIndex(-1);
            }}
            onKeyDown={handleKeyDown}
            onFocus={() => {
              isFocusedRef.current = true;
              if (query.length > 1) setShowSuggestions(true);
            }}
            onBlur={() => {
              setTimeout(() => {
                isFocusedRef.current = false;
                setShowSuggestions(false);
              }, 200);
            }}
            placeholder="বাংলা, Banglish বা English-এ খুঁজুন"
            className="min-w-0 flex-grow bg-transparent text-base text-slate-900 outline-none placeholder:text-slate-400 sm:text-[17px]"
            autoFocus={autoFocus}
            aria-label="খোঁজো সার্চ"
          />
          {query && (
            <button type="button" onClick={() => setQuery('')} className="ml-3 rounded-full border-l border-slate-200 pl-3 text-slate-400 transition-colors hover:text-slate-700" aria-label="খোঁজ মুছুন">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {hasSuggestions && (
          <div className="absolute left-0 right-0 top-full z-50 overflow-hidden rounded-b-2xl border border-slate-200 border-t-0 bg-white pb-3 pt-1 shadow-[0_18px_38px_-24px_rgba(15,23,42,0.42)]">
            <div className="mx-4 mb-1 h-px bg-slate-100" />
            {suggestions.map((suggestion, index) => (
              <button
                key={suggestion}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  setQuery(suggestion);
                  handleSearch(undefined, suggestion);
                }}
                className={`relative flex w-full items-center px-5 py-2 text-left transition-colors ${index === activeIndex ? 'bg-emerald-50' : 'hover:bg-slate-50'}`}
              >
                {index === activeIndex && <span className="absolute bottom-1 left-0 top-1 w-1 rounded-r-md bg-[#006a4e]" />}
                <Search className="mr-3 h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
                <span className={`flex-grow truncate text-[15px] text-slate-800 ${index === activeIndex ? 'font-medium' : ''}`}>{suggestion}</span>
              </button>
            ))}
          </div>
        )}
      </form>
    </div>
  );
};

export default SearchBar;

import React, { useState, useEffect, useRef } from 'react';
import { Search, Mic, X, History } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface SearchBarProps {
  initialValue?: string;
  autoFocus?: boolean;
  className?: string;
}

const SearchBar: React.FC<SearchBarProps> = ({ initialValue = '', autoFocus = false, className = '' }) => {
  const [query, setQuery] = useState(initialValue);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isFocusedRef = useRef(false);

  useEffect(() => {
    const fetchSuggestions = async () => {
      // Only fetch if currently focused
      if (!isFocusedRef.current) return;

      if (query.trim().length > 1) {
        try {
          const response = await fetch(`http://localhost:8000/api/v1/suggestions?q=${encodeURIComponent(query.trim())}&limit=8`);
          if (response.ok) {
            const data = await response.json();
            // Re-check focus before updating state to avoid race conditions
            if (isFocusedRef.current) {
              setSuggestions(data);
              setShowSuggestions(true);
              setActiveIndex(-1);
            }
          }
        } catch (error) {
          console.warn('Suggestions API unavailable:', error);
          setSuggestions([]);
        }
      } else {
        setSuggestions([]);
        setShowSuggestions(false);
        setActiveIndex(-1);
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
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSearch = (e?: React.FormEvent, selectedQuery?: string) => {
    e?.preventDefault();
    const finalQuery = selectedQuery || query;
    if (finalQuery.trim()) {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
      isFocusedRef.current = false; // Mark as not focused to prevent new fetches
      setShowSuggestions(false);
      setSuggestions([]);
      setActiveIndex(-1);
      navigate(`/search?q=${encodeURIComponent(finalQuery)}`);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showSuggestions || suggestions.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex(prev => (prev < suggestions.length - 1 ? prev + 1 : prev));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex(prev => (prev > 0 ? prev - 1 : prev));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const selected = activeIndex >= 0 ? suggestions[activeIndex] : query;
      setQuery(selected);
      handleSearch(undefined, selected);
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
      setActiveIndex(-1);
    }
  };

  const hasSuggestions = showSuggestions && suggestions.length > 0;

  return (
    <div ref={containerRef} className={`relative w-full ${className}`}>
      <form onSubmit={(e) => handleSearch(e)} className="relative z-[60]">
        <div className={`relative flex items-center w-full bg-white border border-gray-200 transition-all duration-200 px-5 py-3 ${
          hasSuggestions 
            ? 'rounded-t-[24px] border-b-0 shadow-lg' 
            : 'rounded-full hover:shadow-md focus-within:shadow-md'
        }`}>
          <Search className="w-5 h-5 text-gray-400 mr-3" />
          <input
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActiveIndex(-1);
            }}
            onKeyDown={handleKeyDown}
            onFocus={() => {
              isFocusedRef.current = true;
              if (query.length > 1) setShowSuggestions(true);
            }}
            onBlur={() => {
              // Delay to allow suggestion clicks to register
              setTimeout(() => {
                isFocusedRef.current = false;
                setShowSuggestions(false);
              }, 200);
            }}
            placeholder="খুঁজুন..."
            className="flex-grow bg-transparent outline-none text-lg text-gray-800 placeholder-gray-400"
            autoFocus={autoFocus}
          />
          <div className="flex items-center space-x-3 ml-3 border-l border-gray-200 pl-3">
            {query && (
              <button type="button" onClick={() => setQuery('')} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            )}
            <button type="button" className="text-gray-400 hover:text-[#006a4e] transition-colors">
              <Mic className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Unified Dropdown Container */}
        {hasSuggestions && (
          <div className="absolute top-full left-0 right-0 bg-white border border-gray-200 border-t-0 rounded-b-[24px] shadow-lg z-50 overflow-hidden pb-4 pt-1">
            <div className="h-[1px] bg-gray-100 mx-5 mb-1" />
            {suggestions.map((suggestion, index) => (
              <button
                key={index}
                onClick={() => {
                  setQuery(suggestion);
                  handleSearch(undefined, suggestion);
                }}
                className={`w-full text-left px-5 py-2 flex items-center transition-all relative group ${
                  index === activeIndex ? 'bg-[#f1f3f4]' : 'hover:bg-[#f1f3f4]'
                }`}
              >
                {/* Vertical selector line - Only shown for active/focused index */}
                {index === activeIndex && (
                  <div className="absolute left-0 top-1 bottom-1 w-[4px] bg-[#006a4e] rounded-r-md" />
                )}
                
                <div className="flex items-center w-full ml-1">
                  {/* Alternating icon for aesthetic Variety, or we can just stick to search */}
                  {index % 3 === 2 ? (
                    <History className="w-5 h-5 mr-3 flex-shrink-0 text-gray-400" />
                  ) : (
                    <Search className="w-5 h-5 mr-3 flex-shrink-0 text-gray-400" />
                  )}
                  <span className={`text-[16px] text-gray-800 flex-grow truncate ${
                    index === activeIndex ? 'font-medium' : ''
                  }`}>
                    {suggestion}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}
      </form>
    </div>
  );
};

export default SearchBar;

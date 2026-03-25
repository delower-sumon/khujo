import React, { useState, useEffect, useRef } from 'react';
import { Search, Mic, X } from 'lucide-react';
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
          const response = await fetch(`http://localhost:8000/api/v1/suggestions?q=${encodeURIComponent(query.trim())}&limit=5`);
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
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      e.preventDefault();
      const selected = suggestions[activeIndex];
      setQuery(selected);
      handleSearch(undefined, selected);
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
      setActiveIndex(-1);
    }
  };

  return (
    <div ref={containerRef} className={`relative w-full ${className}`}>
      <form onSubmit={(e) => handleSearch(e)} className="relative group">
        <div className="relative flex items-center w-full bg-white border border-gray-200 rounded-full hover:shadow-md focus-within:shadow-md transition-shadow duration-200 px-5 py-3">
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
              // Small delay to allow click handlers on suggestions to fire
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
      </form>

      {/* Suggestions Dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-100 rounded-2xl shadow-xl z-50 overflow-hidden py-2">
          {suggestions.map((suggestion, index) => (
            <button
              key={index}
              onClick={() => {
                setQuery(suggestion);
                handleSearch(undefined, suggestion);
              }}
              className={`w-full text-left px-5 py-2.5 flex items-center space-x-3 transition-colors ${
                index === activeIndex ? 'bg-gray-100' : 'hover:bg-gray-50'
              }`}
            >
              <Search className={`w-4 h-4 ${index === activeIndex ? 'text-gray-400' : 'text-gray-300'}`} />
              <span className={`text-gray-700 ${index === activeIndex ? 'font-medium' : ''}`}>{suggestion}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default SearchBar;

"use client";

import React, { useEffect, useState } from 'react';
import { FeedItem } from '@/lib/types';
import { FeedCard } from '@/components/FeedCard';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { Filter, RefreshCw, AlertTriangle, Sparkles, Search } from 'lucide-react';

const CATEGORIES = [
  { id: 'all', label: 'All Updates' },
  { id: 'model', label: 'Models' },
  { id: 'paper', label: 'Papers' },
  { id: 'tool', label: 'Tools' },
  { id: 'news', label: 'News' },
  { id: 'api', label: 'APIs' },
  { id: 'company', label: 'Company' },
];

export default function FeedPage() {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [activeSearch, setActiveSearch] = useState<string>('');

  const fetchFeed = async () => {
    setLoading(true);
    setError(null);

    try {
      if (activeSearch.trim()) {
        const res = await fetch(`/api/search?q=${encodeURIComponent(activeSearch.trim())}`);
        if (!res.ok) throw new Error(`Search failed with status ${res.status}`);
        const data = await res.json();
        setItems(data);
      } else {
        const params = new URLSearchParams();
        if (category !== 'all') params.append('category', category);
        params.append('limit', '30');

        const res = await fetch(`/api/feed?${params.toString()}`);
        if (!res.ok) throw new Error(`Server returned status ${res.status}`);
        const data = await res.json();
        setItems(data);
      }
    } catch (err: any) {
      console.error('Failed to load items', err);
      setError(err.message || 'Failed to load intelligence feed.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFeed();
  }, [category, activeSearch]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setActiveSearch(searchQuery.trim());
  };

  const handleClearSearch = () => {
    setSearchQuery('');
    setActiveSearch('');
  };

  const handleSaveToggle = (itemId: number, nextSaved: boolean) => {
    setItems((prev) =>
      prev.map((item) => (item.id === itemId ? { ...item, saved: nextSaved } : item))
    );
  };

  return (
    <div className="space-y-6">
      {/* Header section */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
            <span>AI Intelligence Feed</span>
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Curated, de-duplicated, scored AI releases & papers with 5-minute practical lessons.
          </p>
        </div>

        <button
          onClick={fetchFeed}
          disabled={loading}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-700 transition-colors self-start sm:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Hybrid Search Bar */}
      <form onSubmit={handleSearchSubmit} className="relative flex items-center">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search feed with hybrid FTS5 keyword & vector similarity (e.g. 'FastAPI RAG', 'reasoning')..."
          className="w-full pl-10 pr-24 py-2.5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
        />
        <Search className="w-4 h-4 text-slate-400 absolute left-3.5 pointer-events-none" />
        {searchQuery && (
          <button
            type="button"
            onClick={handleClearSearch}
            className="absolute right-20 text-xs font-medium text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
          >
            Clear
          </button>
        )}
        <button
          type="submit"
          className="absolute right-2 px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold transition-colors shadow-sm"
        >
          Search
        </button>
      </form>

      {/* Active Search Indicator */}
      {activeSearch && (
        <div className="flex items-center justify-between bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-xl px-4 py-2 text-xs text-blue-800 dark:text-blue-200">
          <span>
            Hybrid search results for: <strong>"{activeSearch}"</strong>
          </span>
          <button
            onClick={handleClearSearch}
            className="font-semibold underline hover:no-underline ml-2"
          >
            Back to standard feed
          </button>
        </div>
      )}

      {/* Category Filter Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none">
        <Filter className="w-4 h-4 text-slate-400 shrink-0 mr-1" />
        {CATEGORIES.map((cat) => (
          <button
            key={cat.id}
            onClick={() => setCategory(cat.id)}
            className={`px-3.5 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
              category === cat.id
                ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/20'
                : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Error State */}
      {error && (
        <div className="rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 p-5 flex items-start gap-3 text-rose-700 dark:text-rose-300">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-sm">Unable to load feed</h3>
            <p className="text-xs mt-1 opacity-90">{error}</p>
            <button
              onClick={fetchFeed}
              className="mt-3 text-xs font-semibold underline hover:no-underline"
            >
              Try again
            </button>
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && <LoadingSkeleton />}

      {/* Empty Feed State */}
      {!loading && !error && items.length === 0 && (
        <div className="text-center py-16 bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-8 space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-blue-50 dark:bg-blue-950/50 text-blue-600 dark:text-blue-400 flex items-center justify-center mx-auto">
            <Sparkles className="w-6 h-6" />
          </div>
          <h3 className="text-lg font-bold text-slate-900 dark:text-white">No items found</h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 max-w-md mx-auto">
            No updates match your selected category filter right now. Run a pipeline cycle to fetch fresh updates.
          </p>
        </div>
      )}

      {/* Items Feed Grid */}
      {!loading && !error && items.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {items.map((item) => (
            <FeedCard key={item.id} item={item} onSaveToggle={handleSaveToggle} />
          ))}
        </div>
      )}
    </div>
  );
}

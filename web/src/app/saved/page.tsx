"use client";

import React, { useEffect, useState } from 'react';
import { FeedItem } from '@/lib/types';
import { FeedCard } from '@/components/FeedCard';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { Bookmark, Sparkles, AlertTriangle } from 'lucide-react';

export default function SavedPage() {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSaved = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/saved');
      if (!res.ok) throw new Error('Failed to load saved items');
      const data = await res.json();
      setItems(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load saved items');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSaved();
  }, []);

  const handleSaveToggle = (itemId: number, nextSaved: boolean) => {
    if (!nextSaved) {
      setItems((prev) => prev.filter((item) => item.id !== itemId));
    }
  };

  return (
    <div className="space-y-6">
      <div className="pb-4 border-b border-slate-200 dark:border-slate-800">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
          <Bookmark className="w-6 h-6 text-amber-500 fill-current" />
          <span>Saved Articles & Lessons</span>
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Your personal library of bookmarked AI intelligence updates and practice challenges.
        </p>
      </div>

      {error && (
        <div className="rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 p-5 flex items-start gap-3 text-rose-700 dark:text-rose-300">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-sm">Error loading saved items</h3>
            <p className="text-xs mt-1 opacity-90">{error}</p>
          </div>
        </div>
      )}

      {loading && <LoadingSkeleton />}

      {!loading && !error && items.length === 0 && (
        <div className="text-center py-16 bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-8 space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400 flex items-center justify-center mx-auto">
            <Bookmark className="w-6 h-6" />
          </div>
          <h3 className="text-lg font-bold text-slate-900 dark:text-white">No saved items yet</h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 max-w-md mx-auto">
            Click the bookmark icon on any feed item to save it here for offline reading or practice.
          </p>
        </div>
      )}

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

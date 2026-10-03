"use client";

import React, { useState } from 'react';
import Link from 'next/link';
import { Bookmark, ExternalLink, ArrowRight, Layers, User } from 'lucide-react';
import { FeedItem } from '@/lib/types';
import { ImportanceBadge } from './ImportanceBadge';

interface FeedCardProps {
  item: FeedItem;
  onSaveToggle?: (itemId: number, nextState: boolean) => void;
}

const CATEGORY_COLORS: Record<string, string> = {
  news: 'bg-purple-100 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800',
  model: 'bg-blue-100 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800',
  tool: 'bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800',
  api: 'bg-teal-100 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 border-teal-200 dark:border-teal-800',
  paper: 'bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800',
  company: 'bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800',
};

export const FeedCard: React.FC<FeedCardProps> = ({ item, onSaveToggle }) => {
  const [saved, setSaved] = useState<boolean>(item.saved);
  const [isSaving, setIsSaving] = useState<boolean>(false);

  const handleSaveClick = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsSaving(true);
    const nextSaved = !saved;

    try {
      const endpoint = `/api/items/${item.id}/save`;
      const res = await fetch(endpoint, {
        method: nextSaved ? 'POST' : 'DELETE',
      });

      if (res.ok) {
        setSaved(nextSaved);
        if (onSaveToggle) onSaveToggle(item.id, nextSaved);
      }
    } catch (err) {
      console.error('Failed to update save status', err);
    } finally {
      setIsSaving(false);
    }
  };

  const formattedDate = item.published_at
    ? new Date(item.published_at).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : null;

  return (
    <article className="group bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800/80 p-5 sm:p-6 shadow-sm hover:shadow-md hover:border-slate-300 dark:hover:border-slate-700 transition-all duration-200 flex flex-col justify-between">
      <div>
        {/* Header badges */}
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider border ${
                CATEGORY_COLORS[item.category] || CATEGORY_COLORS.news
              }`}
            >
              {item.category}
            </span>

            {item.source_name && (
              <span className="text-xs font-medium text-slate-500 dark:text-slate-400 flex items-center gap-1">
                <Layers className="w-3 h-3" />
                {item.source_name}
              </span>
            )}

            {item.match_type && (
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                {item.match_type} match
              </span>
            )}

            <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
              AI-generated • verify with source
            </span>
          </div>

          <div className="flex items-center gap-2">
            {item.feed_score !== undefined && (
              <span className="text-xs font-mono font-medium text-slate-400 dark:text-slate-500" title="Composite feed score">
                Score: {item.feed_score.toFixed(2)}
              </span>
            )}
            <ImportanceBadge score={item.importance_score} />

            <button
              onClick={handleSaveClick}
              disabled={isSaving}
              className={`p-1.5 rounded-lg transition-colors ${
                saved
                  ? 'text-amber-500 bg-amber-50 dark:bg-amber-950/40'
                  : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
              title={saved ? 'Remove from saved' : 'Save for later'}
            >
              <Bookmark className={`w-4 h-4 ${saved ? 'fill-current' : ''}`} />
            </button>
          </div>
        </div>

        {/* Matched Interest Keywords */}
        {item.matched_keywords && item.matched_keywords.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 mb-3">
            <span className="text-[11px] font-medium text-slate-400 dark:text-slate-500">Matched interests:</span>
            {item.matched_keywords.map((kw) => (
              <span
                key={kw}
                className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/80"
              >
                #{kw}
              </span>
            ))}
          </div>
        )}

        {/* Title */}
        <h2 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white leading-snug group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors mb-2">
          <Link href={`/items/${item.id}`}>{item.title}</Link>
        </h2>

        {/* Author / Date */}
        {(item.author || formattedDate) && (
          <div className="flex items-center gap-3 text-xs text-slate-400 dark:text-slate-500 mb-4">
            {item.author && (
              <span className="flex items-center gap-1">
                <User className="w-3 h-3" />
                {item.author}
              </span>
            )}
            {formattedDate && <span>{formattedDate}</span>}
          </div>
        )}

        {/* Summaries: what_is_new & why_it_matters */}
        <div className="space-y-3 mb-5 text-sm">
          {item.what_is_new && (
            <div className="bg-slate-50 dark:bg-slate-800/50 rounded-xl p-3.5 border border-slate-100 dark:border-slate-800">
              <span className="font-semibold text-slate-900 dark:text-slate-200 block mb-1 text-xs uppercase tracking-wider text-blue-600 dark:text-blue-400">
                What's New
              </span>
              <p className="text-slate-700 dark:text-slate-300 leading-relaxed">
                {item.what_is_new}
              </p>
            </div>
          )}

          {item.why_it_matters && (
            <div className="bg-slate-50 dark:bg-slate-800/50 rounded-xl p-3.5 border border-slate-100 dark:border-slate-800">
              <span className="font-semibold text-slate-900 dark:text-slate-200 block mb-1 text-xs uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
                Why It Matters
              </span>
              <p className="text-slate-700 dark:text-slate-300 leading-relaxed">
                {item.why_it_matters}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Footer actions */}
      <div className="flex items-center justify-between pt-4 border-t border-slate-100 dark:border-slate-800 text-xs">
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 font-medium text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white transition-colors"
        >
          <ExternalLink className="w-3.5 h-3.5" />
          <span>Original Source</span>
        </a>

        <Link
          href={`/items/${item.id}`}
          className="inline-flex items-center gap-1.5 font-semibold text-blue-600 dark:text-blue-400 hover:gap-2 transition-all"
        >
          <span>5-Min Lesson & Details</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </article>
  );
};

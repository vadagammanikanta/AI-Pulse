"use client";

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ItemDetail } from '@/lib/types';
import { ImportanceBadge } from '@/components/ImportanceBadge';
import {
  ArrowLeft,
  Bookmark,
  ExternalLink,
  BookOpen,
  CheckCircle2,
  Trophy,
  Target,
  Zap,
  Lightbulb,
  AlertTriangle,
} from 'lucide-react';

export default function ItemDetailPage() {
  const params = useParams();
  const id = params?.id as string;

  const [item, setItem] = useState<ItemDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<boolean>(false);

  useEffect(() => {
    if (!id) return;
    const fetchItem = async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/items/${id}`);
        if (!res.ok) throw new Error('Item not found');
        const data: ItemDetail = await res.json();
        setItem(data);
        setSaved(data.saved);
      } catch (err: any) {
        setError(err.message || 'Failed to load item detail');
      } finally {
        setLoading(false);
      }
    };
    fetchItem();
  }, [id]);

  const toggleSave = async () => {
    if (!item) return;
    const nextSaved = !saved;
    setSaved(nextSaved);
    try {
      await fetch(`/api/items/${item.id}/save`, {
        method: nextSaved ? 'POST' : 'DELETE',
      });
    } catch (err) {
      console.error('Failed to save', err);
      setSaved(!nextSaved);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto space-y-6 animate-pulse">
        <div className="h-6 bg-slate-200 dark:bg-slate-800 rounded w-24"></div>
        <div className="h-10 bg-slate-200 dark:bg-slate-800 rounded-lg w-3/4"></div>
        <div className="h-32 bg-slate-100 dark:bg-slate-900 rounded-2xl"></div>
        <div className="h-64 bg-slate-100 dark:bg-slate-900 rounded-2xl"></div>
      </div>
    );
  }

  if (error || !item) {
    return (
      <div className="max-w-md mx-auto text-center py-16 space-y-4">
        <AlertTriangle className="w-12 h-12 text-rose-500 mx-auto" />
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">Item Not Found</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">{error}</p>
        <Link
          href="/feed"
          className="inline-flex items-center gap-2 text-sm font-semibold text-blue-600 dark:text-blue-400"
        >
          <ArrowLeft className="w-4 h-4" />
          Return to Feed
        </Link>
      </div>
    );
  }

  const { learning_module } = item;

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Back button & top bar */}
      <div className="flex items-center justify-between">
        <Link
          href="/feed"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Feed</span>
        </Link>

        <div className="flex items-center gap-3">
          <ImportanceBadge score={item.importance_score} />
          <button
            onClick={toggleSave}
            className={`p-2 rounded-xl border transition-colors ${
              saved
                ? 'bg-amber-50 dark:bg-amber-950/50 border-amber-300 dark:border-amber-700 text-amber-600 dark:text-amber-400'
                : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200'
            }`}
          >
            <Bookmark className={`w-5 h-5 ${saved ? 'fill-current' : ''}`} />
          </button>
        </div>
      </div>

      {/* Main Title & Metadata */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <span className="px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
            {item.category}
          </span>
          {item.source_name && (
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
              via {item.source_name}
            </span>
          )}
          <span className="px-2.5 py-0.5 rounded text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
            AI-generated • verify with source
          </span>
        </div>

        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white leading-tight">
          {item.title}
        </h1>

        <div className="flex items-center justify-between pt-2">
          <div className="text-xs text-slate-500 dark:text-slate-400">
            {item.author && <span className="mr-3">By {item.author}</span>}
            {item.published_at && (
              <span>Published {new Date(item.published_at).toLocaleDateString()}</span>
            )}
          </div>

          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline"
          >
            <span>Original Source</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>

      {/* AI Intelligence Summary Card */}
      <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-6 sm:p-8 space-y-6 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-4">
          <Zap className="w-5 h-5 text-blue-600 dark:text-blue-400" />
          <span>Executive Intelligence Summary</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {item.what_is_new && (
            <div className="space-y-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-blue-600 dark:text-blue-400">
                What's New
              </h3>
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                {item.what_is_new}
              </p>
            </div>
          )}

          {item.why_it_matters && (
            <div className="space-y-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
                Why It Matters
              </h3>
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                {item.why_it_matters}
              </p>
            </div>
          )}
        </div>

        {item.how_to_use && (
          <div className="space-y-2 pt-4 border-t border-slate-100 dark:border-slate-800">
            <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
              How To Use It
            </h3>
            <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
              {item.how_to_use}
            </p>
          </div>
        )}

        {item.pro_tip && (
          <div className="bg-amber-50 dark:bg-amber-950/40 rounded-2xl p-4 border border-amber-200 dark:border-amber-900 flex items-start gap-3 text-amber-900 dark:text-amber-200">
            <Lightbulb className="w-5 h-5 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
            <div>
              <span className="font-bold text-xs uppercase tracking-wider block mb-0.5">
                Pro Tip
              </span>
              <p className="text-sm leading-relaxed">{item.pro_tip}</p>
            </div>
          </div>
        )}
      </div>

      {/* 5-Minute Practical Learning Module Card */}
      {learning_module && Object.keys(learning_module).length > 0 && (
        <div className="bg-gradient-to-br from-slate-900 to-slate-950 text-white rounded-3xl p-6 sm:p-8 space-y-6 shadow-xl border border-slate-800">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-blue-400">
                {(learning_module as any).module_type === 'paper' ? 'Paper Reading Guide' : 'Personal AI Coach'}
              </span>
              <h2 className="text-xl font-bold text-white flex items-center gap-2 mt-0.5">
                <BookOpen className="w-5 h-5 text-blue-400" />
                <span>{(learning_module as any).module_type === 'paper' ? 'How to Read This Paper' : '5-Minute Skill Module'}</span>
              </h2>
            </div>

            {(learning_module as any).skill_gained && (
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30 flex items-center gap-1.5">
                <Trophy className="w-3.5 h-3.5 text-blue-400" />
                <span>Skill: {(learning_module as any).skill_gained}</span>
              </span>
            )}
          </div>

          {/* Paper module: key_idea + read_for + prerequisite_concepts */}
          {(learning_module as any).module_type === 'paper' ? (
            <div className="space-y-5">
              {(learning_module as any).key_idea && (
                <div className="space-y-2">
                  <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                    <Zap className="w-4 h-4 text-blue-400" />
                    <span>Core Contribution</span>
                  </h3>
                  <div className="bg-slate-900/80 rounded-2xl p-5 border border-slate-800 text-sm leading-relaxed text-slate-300">
                    {(learning_module as any).key_idea}
                  </div>
                </div>
              )}

              {(learning_module as any).read_for && (
                <div className="space-y-2">
                  <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                    <BookOpen className="w-4 h-4 text-emerald-400" />
                    <span>What to Read For</span>
                  </h3>
                  <div className="bg-slate-900/80 rounded-2xl p-5 border border-slate-800 text-sm leading-relaxed text-slate-300">
                    {(learning_module as any).read_for}
                  </div>
                </div>
              )}

              {(learning_module as any).prerequisite_concepts?.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                    <Target className="w-4 h-4 text-amber-400" />
                    <span>Prerequisites</span>
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {(learning_module as any).prerequisite_concepts.map((c: string, i: number) => (
                      <span key={i} className="px-3 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Tutorial module: tutorial_5min + practice_task + challenge */
            <div className="space-y-5">
              {(learning_module as any).tutorial_5min && (
                <div className="space-y-3">
                  <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>5-Minute Interactive Tutorial</span>
                  </h3>
                  <div className="bg-slate-900/80 rounded-2xl p-5 border border-slate-800 text-sm leading-relaxed text-slate-300 whitespace-pre-line">
                    {(learning_module as any).tutorial_5min}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
                {(learning_module as any).practice_task && (
                  <div className="bg-slate-900/80 rounded-2xl p-5 border border-slate-800 space-y-2">
                    <h4 className="text-xs font-bold text-blue-400 uppercase tracking-wider flex items-center gap-1.5">
                      <Target className="w-4 h-4" />
                      <span>Practice Task</span>
                    </h4>
                    <p className="text-sm text-slate-300 leading-relaxed">
                      {(learning_module as any).practice_task}
                    </p>
                  </div>
                )}

                {(learning_module as any).challenge && (
                  <div className="bg-slate-900/80 rounded-2xl p-5 border border-slate-800 space-y-2">
                    <h4 className="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                      <Trophy className="w-4 h-4" />
                      <span>Challenge Extension</span>
                    </h4>
                    <p className="text-sm text-slate-300 leading-relaxed">
                      {(learning_module as any).challenge}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Next Topic — shared between both types */}
          {(learning_module as any).next_topic && (
            <div className="pt-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
              <span>Next Recommended Learning Topic:</span>
              <span className="font-semibold text-blue-400">{(learning_module as any).next_topic}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

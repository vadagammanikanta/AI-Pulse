import React from 'react';

export const LoadingSkeleton: React.FC = () => {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 animate-pulse space-y-4"
        >
          <div className="flex justify-between items-center">
            <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded-full w-24"></div>
            <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded-full w-20"></div>
          </div>
          <div className="h-6 bg-slate-200 dark:bg-slate-800 rounded-lg w-3/4"></div>
          <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-1/3"></div>
          <div className="h-16 bg-slate-100 dark:bg-slate-800/50 rounded-xl"></div>
          <div className="h-16 bg-slate-100 dark:bg-slate-800/50 rounded-xl"></div>
        </div>
      ))}
    </div>
  );
};

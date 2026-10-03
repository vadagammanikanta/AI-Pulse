import React from 'react';

interface ImportanceBadgeProps {
  score: number;
}

export const ImportanceBadge: React.FC<ImportanceBadgeProps> = ({ score }) => {
  let bgColor = 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-300 dark:border-slate-700';
  let label = 'Low';

  if (score >= 85) {
    bgColor = 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-300 dark:border-emerald-700';
    label = 'Critical';
  } else if (score >= 70) {
    bgColor = 'bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 border-blue-300 dark:border-blue-700';
    label = 'High';
  } else if (score >= 50) {
    bgColor = 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-300 dark:border-amber-700';
    label = 'Medium';
  }

  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${bgColor}`}
      title={`Importance score: ${score}/100`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
      {score} / 100 • {label}
    </span>
  );
};

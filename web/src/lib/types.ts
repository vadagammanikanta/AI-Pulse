export type Category = 'news' | 'model' | 'tool' | 'api' | 'paper' | 'company';

export interface FeedItem {
  id: number;
  title: string;
  url: string;
  author: string | null;
  published_at: string | null;
  category: Category;
  importance_score: number;
  importance_reason: string | null;
  what_is_new: string | null;
  why_it_matters: string | null;
  who_should_care: string[];
  saved: boolean;
  processed_at: string;
  source_name: string | null;
  feed_score?: number;
  matched_keywords?: string[];
  match_type?: 'keyword' | 'semantic' | 'hybrid';
}

/** Learning module for academic papers. No numbered steps, section refs, filenames. */
export interface PaperLearningModule {
  module_type: 'paper';
  key_idea?: string;
  read_for?: string;
  prerequisite_concepts?: string[];
  skill_gained?: string;
  next_topic?: string;
}

/** Learning module for non-paper items (tools, news, models, APIs). */
export interface TutorialLearningModule {
  module_type: 'tutorial';
  tutorial_5min?: string;
  practice_task?: string;
  challenge?: string;
  skill_gained?: string;
  next_topic?: string;
}

/** Discriminated union — use module_type to narrow. Legacy rows may lack module_type. */
export type LearningModule = PaperLearningModule | TutorialLearningModule | Record<string, unknown>;

export interface ItemDetail extends FeedItem {
  how_to_use: string | null;
  pro_tip: string | null;
  learning_module: LearningModule | null;
}

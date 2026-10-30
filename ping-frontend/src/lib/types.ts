// Shapes returned by ping-backend (/api/v1). Field names match the API.

export type BotStatus = "live" | "draft" | "paused";
export type ModelTier = "fast" | "balanced" | "best";
export type Tone = "friendly" | "professional" | "concise";
export type ReplyLanguage = "auto" | "en" | "hi" | "ta";
export type TimeRange = "24h" | "7d" | "30d" | "90d";
export type ConversationFilter = "all" | "live" | "unanswered" | "down" | "handoff" | "review" | "unhappy";
export type HandoffMode = "instant" | "offer" | "bot_first";
export type MemoryMode = "manual" | "review" | "auto";
export type AnswerStrictness = "strict" | "balanced" | "helpful";
export type AlertEvent = "wants_person" | "lead" | "disliked";
export type Weekday = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun";

export interface BusinessHours {
  enabled: boolean;
  timezone: string;
  /** Up to 3 ["HH:MM", "HH:MM"] ranges per day; a missing day is closed. */
  days: Partial<Record<Weekday, [string, string][]>>;
}

export interface SavedReply {
  id: string;
  title: string;
  body: string;
  updated_at: string;
}
export type MemoryStatus = "pending" | "learned" | "skipped";

export type ChatStatus = "bot" | "waiting" | "human" | "closed";
export type Outcome = "answered" | "partial" | "fallback";
export type MessageOutcome = Outcome | "smalltalk" | "lead" | "offline";
export type SourceType = "pdf" | "docx" | "text" | "url" | "sitemap" | "page";
export type SourceStatus = "queued" | "indexing" | "ready" | "failed";
export type DeltaTone = "up" | "down" | "flat";
export type Role = "owner" | "editor" | "viewer";
export type InviteRole = Exclude<Role, "owner">;

export interface User {
  id: string;
  email: string;
  email_verified: boolean;
  name: string;
  avatar_url: string;
}

export interface OrgUsage {
  messages_used: number;
  messages_limit: number;
  bots_used: number;
  bots_limit: number;
  sources_limit: number;
  members_limit: number;
  shares_limit: number;
  remove_branding: boolean;
  /** Paid plans: widget layouts, logo, shapes and fonts. */
  custom_design?: boolean;
}

export interface Org {
  id: string;
  name: string;
  slug: string;
  plan: string;
  plan_name: string;
  can_upgrade: boolean;
  allowed_model_tiers: ModelTier[];
  role: Role;
  initial: string;
  usage: OrgUsage;
}

export interface Plan {
  key: string;
  name: string;
  description: string;
  price_monthly: number | null;
  price_label: string;
  messages_limit: number;
  bots_limit: number;
  sources_limit: number;
  members_limit: number;
  remove_branding: boolean;
  model_tiers: ModelTier[];
  features: string[];
  highlighted: boolean;
  sort_order: number;
}

export interface BotSummary {
  id: string;
  name: string;
  initials: string;
  color: string;
  status: BotStatus;
  domain: string;
  conversations_30d: number;
  resolution_rate: number;
  sources: number;
  updated_at: string;
}

export interface WidgetAppearance {
  title: string;
  welcome: string;
  placeholder: string;
  accent: string;
  position: "right" | "left";
  launcher: "chat" | "spark" | "help";
  suggestions: string[];
  show_sources: boolean;
  show_branding: boolean;
  theme: "dark" | "light";
  /** Visitors can browse web pages and team answers in the widget. */
  help_center_enabled: boolean;
  // Custom design (paid plans only)
  layout: WidgetLayout;
  header_style: "solid" | "gradient" | "light";
  /** Second gradient colour; empty derives one from the accent. */
  accent_2: string;
  logo_url: string;
  corner: "rounded" | "soft" | "square";
  bubble: "filled" | "outline";
  size: "standard" | "large";
  font: "system" | "rounded" | "serif" | "mono";
}

export type WidgetLayout = "classic" | "welcome" | "compact";

/** Appearance fields only paid plans may change. */
export const DESIGN_FIELDS = ["layout", "header_style", "accent_2", "logo_url", "corner", "bubble", "size", "font"] as const;

export interface Bot {
  id: string;
  organization_id: string;
  organization_name: string;
  access_role: Role;
  access_via: "workspace" | "share";
  name: string;
  initials: string;
  color: string;
  status: BotStatus;
  domain: string;
  public_key: string;
  instructions: string;
  model_tier: ModelTier;
  tone: Tone;
  reply_language: ReplyLanguage;
  min_similarity: number;
  fallback_message: string;
  collect_email: boolean;
  handoff_email: string;
  offline_message: string;
  handoff_mode: HandoffMode;
  /** A teammate has Live on right now, so a handover can connect someone. */
  agents_online: boolean;
  memory_mode: MemoryMode;
  memory: { learned: number; pending: number };
  answer_strictness: AnswerStrictness;
  topic_guard: boolean;
  blocked_topics: string;
  off_topic_message: string;
  business_hours: Partial<BusinessHours>;
  /** Outside business hours right now, and when the team is back ("Monday 9:00 AM"). */
  outside_hours: boolean;
  next_opening: string | null;
  /** Empty for viewers: webhook URLs are credentials. */
  alert_slack_url: string;
  alert_webhook_url: string;
  alerts_configured: boolean;
  alert_events: AlertEvent[];
  allow_localhost: boolean;
  appearance: WidgetAppearance;
  counts: { conversations: number; sources: number; domains: number; live: number };
  created_at: string;
  updated_at: string;
}

export type BotUpdate = Partial<
  Pick<
    Bot,
    | "name"
    | "color"
    | "status"
    | "domain"
    | "instructions"
    | "model_tier"
    | "tone"
    | "reply_language"
    | "min_similarity"
    | "fallback_message"
    | "collect_email"
    | "handoff_email"
    | "offline_message"
    | "handoff_mode"
    | "memory_mode"
    | "answer_strictness"
    | "topic_guard"
    | "blocked_topics"
    | "off_topic_message"
    | "alert_slack_url"
    | "alert_webhook_url"
    | "alert_events"
    | "allow_localhost"
  >
> & { business_hours?: BusinessHours };

export interface Kpi {
  key: string;
  label: string;
  value: string;
  delta: string;
  tone: DeltaTone;
  sub: string;
}

export interface SeriesPoint {
  label: string;
  conversations: number;
  unanswered: number;
}

export interface Overview {
  range: TimeRange;
  kpis: Kpi[];
  series_total: number;
  series: SeriesPoint[];
  outcomes: { key: Outcome; label: string; pct: number }[];
  resolved_pct: number;
  messages_per_day: number[];
  messages_14d: number;
  top_pages: { path: string; value: number }[];
  knowledge_gaps: string[];
  /** Help Center articles visitors said didn't answer their question. */
  unhelpful_articles: { id: string; title: string; helpful: number; unhelpful: number }[];
  unanswered_count: number;
  top_questions: { text: string; count: number; rate: string; source: string | null }[];
}

export interface Citation {
  source_id?: string | null;
  source_name: string;
  location: string;
  chunk_id?: string | null;
  score?: number | null;
  article_id?: string | null;
}

export interface ChatMessage {
  id: string;
  role: "visitor" | "bot" | "agent" | "system";
  content: string;
  outcome: MessageOutcome | null;
  citations: Citation[];
  feedback: "up" | "down" | null;
  created_at: string;
  author_name: string | null;
}

export interface ConversationSummary {
  id: string;
  visitor: string;
  location: string;
  page: string;
  started_at: string;
  last_message_at: string;
  outcome: Outcome;
  message_count: number;
  preview: string;
  unread: boolean;
  handoff_email: string | null;
  status: ChatStatus;
  assigned_to: string | null;
  waiting_since: string | null;
  /** Asked for a person while nobody was online; cleared when someone joins. */
  wants_person: boolean;
  /** Learning from this chat; null when it hasn't been considered. */
  memory_status: MemoryStatus | null;
  /** The visitor's rating of the chat: 1 unhappy, 2 okay, 3 happy. */
  csat: 1 | 2 | 3 | null;
  csat_comment: string;
}

export interface ConversationUpdates {
  status: ChatStatus;
  agent: { name: string; avatar_url: string } | null;
  messages: ChatMessage[];
}

export interface LiveItem {
  conversation_id: string;
  bot_id: string;
  bot_name: string;
  visitor: string;
  status: ChatStatus;
  waiting_since: string | null;
  last_message_at: string;
  unread: boolean;
  wants_person?: boolean;
}

export interface LiveSummary {
  available: boolean;
  waiting: LiveItem[];
  mine: LiveItem[];
}

export interface TeamAnswer {
  id: string;
  question: string;
  answer: string;
  conversation_id: string | null;
  created_at: string;
  kind: "answer" | "summary" | "conversation";
  origin_bot_id: string | null;
  shared_with: number;
  in_help_center: boolean;
  helpful: number;
  unhelpful: number;
}

export interface KnowledgeDraftItem {
  question: string;
  answer: string;
}

export interface ConversationDetail extends ConversationSummary {
  duration_seconds: number;
  messages: ChatMessage[];
}

export interface Source {
  id: string;
  name: string;
  type: SourceType;
  status: SourceStatus;
  error: string | null;
  progress: number;
  chunks: number;
  size_bytes: number | null;
  page_count: number | null;
  url: string | null;
  updated_at: string;
  /** Visitors can read it in the widget's Help Center (web pages and text files). */
  readable: boolean;
  in_help_center: boolean;
  helpful: number;
  unhelpful: number;
}

export interface SourceList {
  items: Source[];
  summary: { total: number; ready: number; failed: number; indexing: number; chunks: number; last_sync: string | null };
}

export interface TestResult {
  query: string;
  standalone_query: string;
  threshold: number;
  chunks: {
    rank: number;
    source: string;
    location: string;
    score: number;
    rerank_score: number | null;
    above_threshold: boolean;
    text: string;
  }[];
  answer: string;
  outcome: MessageOutcome;
  citations: Citation[];
  retrieval_ms: number;
  generation_ms: number;
  chunks_in_context: number;
}

export interface Domain {
  id: string;
  host: string;
  receiving_traffic: boolean;
  last_seen_at: string | null;
  created_at: string;
}

export interface InstallInfo {
  bot_id: string;
  public_key: string;
  script_url: string;
  snippet_html: string;
  detected: boolean;
  detected_host: string | null;
  detected_at: string | null;
}

export interface Lead {
  id: string;
  email: string;
  question: string;
  conversation_id: string;
  created_at: string;
}

export interface SharedBot extends BotSummary {
  role: InviteRole;
  organization_name: string;
  shared_by: string | null;
}

export interface Invitation {
  id: string;
  email: string;
  kind: "workspace" | "bot";
  role: InviteRole;
  status: "pending" | "accepted" | "declined" | "revoked" | "expired";
  organization_id: string;
  organization_name: string;
  bot_id: string | null;
  bot_name: string | null;
  invited_by: string | null;
  expires_at: string;
  created_at: string;
  invite_url?: string;
  email_matches?: boolean;
}

export interface Person {
  user_id: string;
  email: string;
  name: string;
  avatar_url: string;
  role: Role;
  joined_at: string;
}

export interface PeopleList {
  people: Person[];
  invitations: Invitation[];
  seats_used: number;
  seats_limit: number;
}

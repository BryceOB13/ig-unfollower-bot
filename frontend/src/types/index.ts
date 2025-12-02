export interface Status {
  browser_connected: boolean;
  logged_in: boolean;
  last_operation: LastOperation | null;
}

export interface LastOperation {
  type: 'compare' | 'unfollow';
  timestamp: string;
  followers_count?: number;
  following_count?: number;
  successful_count?: number;
  failed_count?: number;
  dry_run?: boolean;
}

export interface Snapshot {
  timestamp: string;
  followers: string[];
  following: string[];
  followers_count: number;
  following_count: number;
}

export interface Comparison {
  unfollowers: string[];
  not_following_back: string[];
  new_followers: string[];
  timestamp: string;
}

export interface Operation {
  type: 'compare' | 'unfollow';
  status: 'running' | 'completed' | 'failed';
  progress: number;
  total: number;
  message: string;
  result?: {
    successful?: string[];
    failed?: string[];
    skipped?: string[];
  };
}

export interface Config {
  username: string;
  action_delay_min: number;
  action_delay_max: number;
  scroll_delay: number;
  element_timeout: number;
  max_retries: number;
}

export interface WSMessage {
  type: 'progress' | 'status_change' | 'operation_complete' | 'heartbeat';
  operation_id?: string;
  current?: number;
  total?: number;
  message?: string;
  browser?: boolean;
  logged_in?: boolean;
  result?: Record<string, unknown>;
  error?: string;
}

import React, { useEffect, useState } from 'react';
import { QueryClient, QueryClientProvider, useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Header } from './components/Header';
import { MetricsRow } from './components/MetricsRow';
import { QuickActions } from './components/QuickActions';
import { OperationStatus } from './components/OperationStatus';
import { DataTabs } from './components/DataTabs';
import { SettingsDrawer } from './components/SettingsDrawer';
import { useWebSocket } from './hooks/useWebSocket';
import { useAppStore } from './stores/appStore';
import { api } from './lib/api';
import type { Status, Snapshot, Comparison, Config } from './types';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function Dashboard() {
  const queryClient = useQueryClient();
  const { setActiveOperation, setBrowserConnected, setLoggedIn } = useAppStore();

  // WebSocket for real-time updates
  useWebSocket();

  // Queries
  const { data: status } = useQuery<Status>({
    queryKey: ['status'],
    queryFn: api.getStatus,
    refetchInterval: 5000,
  });

  const { data: snapshot } = useQuery<Snapshot | null>({
    queryKey: ['snapshot'],
    queryFn: api.getLatestSnapshot,
  });

  const { data: comparison } = useQuery<Comparison | null>({
    queryKey: ['comparison'],
    queryFn: api.getLatestComparison,
  });

  const { data: skipListData } = useQuery({
    queryKey: ['skipList'],
    queryFn: api.getSkipList,
  });

  const { data: config } = useQuery<Config>({
    queryKey: ['config'],
    queryFn: api.getConfig,
  });

  // Track active operation to refresh data when it completes
  const { activeOperation } = useAppStore();
  const prevOperationRef = React.useRef(activeOperation);

  // Update store from status
  useEffect(() => {
    if (status) {
      setBrowserConnected(status.browser_connected);
      setLoggedIn(status.logged_in);
    }
  }, [status, setBrowserConnected, setLoggedIn]);

  // Watch for username changes and refresh comparison data
  const prevUsernameRef = React.useRef(config?.username);
  useEffect(() => {
    if (config?.username && config.username !== prevUsernameRef.current) {
      // Username changed - refresh comparison and snapshot data
      queryClient.invalidateQueries({ queryKey: ['comparison'] });
      queryClient.invalidateQueries({ queryKey: ['snapshot'] });
      prevUsernameRef.current = config.username;
    }
  }, [config?.username, queryClient]);

  // Refresh comparison data when an operation completes
  useEffect(() => {
    // If operation just completed (was running, now null)
    if (prevOperationRef.current !== null && activeOperation === null) {
      // Refresh comparison and snapshot data
      queryClient.invalidateQueries({ queryKey: ['comparison'] });
      queryClient.invalidateQueries({ queryKey: ['snapshot'] });
      // Clear selection after unfollow
      useAppStore.getState().clearSelection();
    }
    prevOperationRef.current = activeOperation;
  }, [activeOperation, queryClient]);

  // Mutations
  const loginMutation = useMutation({
    mutationFn: () => api.login(true),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['status'] });
    },
  });

  const logoutMutation = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['status'] });
    },
  });

  const compareMutation = useMutation({
    mutationFn: api.startCompare,
    onSuccess: (data) => {
      setActiveOperation({
        id: data.operation_id,
        type: 'compare',
        status: 'running',
        progress: 0,
        total: 100,
        message: 'Starting...',
      });
    },
  });

  const unfollowMutation = useMutation({
    mutationFn: (opts: { targets: string[]; dry_run: boolean; max_unfollows: number }) =>
      api.startUnfollow(opts),
    onSuccess: (data, variables) => {
      setActiveOperation({
        id: data.operation_id,
        type: 'unfollow',
        status: 'running',
        progress: 0,
        total: Math.min(variables.targets.length, variables.max_unfollows),
        message: 'Starting...',
      });
    },
  });

  const addToSkipMutation = useMutation({
    mutationFn: api.addToSkipList,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['skipList'] });
    },
  });

  const removeFromSkipMutation = useMutation({
    mutationFn: api.removeFromSkipList,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['skipList'] });
    },
  });

  const handleCompareStart = () => {
    // Reset unfollowed count when starting a new comparison
    useAppStore.getState().resetUnfollowedCount();
    compareMutation.mutate();
  };

  const handleUnfollowStart = (targets: string[], dryRun: boolean, maxUnfollows: number) => {
    unfollowMutation.mutate({ targets, dry_run: dryRun, max_unfollows: maxUnfollows });
  };

  const handleAddToSkip = (username: string) => {
    addToSkipMutation.mutate(username);
  };

  const handleRemoveFromSkip = (username: string) => {
    removeFromSkipMutation.mutate(username);
  };

  const handleUnfollow = (username: string) => {
    unfollowMutation.mutate({ targets: [username], dry_run: false, max_unfollows: 1 });
  };

  return (
    <div className="min-h-screen bg-[#0a0a0b]">
      <Header
        username={config?.username}
        lastOperation={status?.last_operation}
      />

      <main className="p-6 space-y-6 max-w-7xl mx-auto">
        <MetricsRow snapshot={snapshot} comparison={comparison} />

        <div className="grid grid-cols-2 gap-6">
          <QuickActions
            notFollowingBackCount={comparison?.not_following_back.length ?? 0}
            onCompareStart={handleCompareStart}
            onUnfollowStart={handleUnfollowStart}
          />
          <OperationStatus lastOperation={status?.last_operation} />
        </div>

        <DataTabs
          comparison={comparison}
          skipList={skipListData?.usernames ?? []}
          onAddToSkip={handleAddToSkip}
          onRemoveFromSkip={handleRemoveFromSkip}
          onUnfollow={handleUnfollow}
        />
      </main>

      <SettingsDrawer
        config={config}
        onLogin={() => loginMutation.mutate()}
        onLogout={() => logoutMutation.mutate()}
      />
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Dashboard />
    </QueryClientProvider>
  );
}

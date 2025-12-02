import { X } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import { api } from '../lib/api';
import { useState } from 'react';

interface SettingsDrawerProps {
  config?: {
    username: string;
    action_delay_min: number;
    action_delay_max: number;
    element_timeout: number;
  };
  onLogin: () => void;
  onLogout: () => void;
}

export function SettingsDrawer({ config, onLogin, onLogout }: SettingsDrawerProps) {
  const { settingsOpen, setSettingsOpen, loggedIn, browserConnected } = useAppStore();
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!settingsOpen) return null;

  const handleLogin = async () => {
    setIsLoggingIn(true);
    setError(null);
    try {
      await onLogin();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Login failed');
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleVerify = async () => {
    setIsVerifying(true);
    setError(null);
    try {
      const res = await api.verifyLogin();
      if (!res.success) {
        setError('Not logged in yet. Complete login in browser first.');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Verification failed');
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={() => setSettingsOpen(false)}
      />

      {/* Drawer */}
      <div className="fixed right-0 top-0 bottom-0 w-80 bg-[#141416] border-l border-[#2a2a2d] z-50 overflow-y-auto">
        <div className="p-4 border-b border-[#2a2a2d] flex items-center justify-between">
          <h2 className="font-mono font-bold text-lg">Settings</h2>
          <button
            onClick={() => setSettingsOpen(false)}
            className="p-1 hover:bg-[#1c1c1f] rounded transition-colors"
          >
            <X className="w-5 h-5 text-zinc-400" />
          </button>
        </div>

        <div className="p-4 space-y-6">
          {/* Account Section */}
          <section className="space-y-3">
            <h3 className="text-xs text-zinc-500 uppercase tracking-wider font-mono">
              Account
            </h3>

            {config?.username && (
              <div className="text-sm">
                <span className="text-zinc-500">Username: </span>
                <span className="font-mono text-zinc-200">@{config.username}</span>
              </div>
            )}

            <div className="flex gap-2">
              {!loggedIn ? (
                <>
                  <button
                    onClick={handleLogin}
                    disabled={isLoggingIn}
                    className="flex-1 px-3 py-2 text-sm font-mono bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/20 disabled:opacity-50 transition-colors"
                  >
                    {isLoggingIn ? 'Starting...' : 'Open Browser'}
                  </button>
                  <button
                    onClick={handleVerify}
                    disabled={isVerifying}
                    className="flex-1 px-3 py-2 text-sm font-mono bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-50 transition-colors"
                  >
                    {isVerifying ? 'Checking...' : 'Verify Login'}
                  </button>
                </>
              ) : (
                <button
                  onClick={onLogout}
                  className="flex-1 px-3 py-2 text-sm font-mono bg-rose-500/10 border border-rose-500/30 text-rose-400 hover:bg-rose-500/20 transition-colors"
                >
                  Logout
                </button>
              )}
            </div>

            {error && (
              <p className="text-xs text-rose-400">{error}</p>
            )}

            {!loggedIn && (
              <p className="text-xs text-zinc-500">
                1. Click "Open Browser" to launch Chrome<br />
                2. Log into Instagram in the browser<br />
                3. Click "Verify Login" to confirm
              </p>
            )}
          </section>

          {/* Timing Section */}
          <section className="space-y-3">
            <h3 className="text-xs text-zinc-500 uppercase tracking-wider font-mono">
              Timing
            </h3>

            <div className="space-y-2">
              <label className="block text-sm text-zinc-400">
                Action Delay (min): {config?.action_delay_min ?? 3}s
              </label>
              <input
                type="range"
                min="1"
                max="10"
                defaultValue={config?.action_delay_min ?? 3}
                className="w-full"
              />
            </div>

            <div className="space-y-2">
              <label className="block text-sm text-zinc-400">
                Action Delay (max): {config?.action_delay_max ?? 10}s
              </label>
              <input
                type="range"
                min="5"
                max="30"
                defaultValue={config?.action_delay_max ?? 10}
                className="w-full"
              />
            </div>

            <div className="space-y-2">
              <label className="block text-sm text-zinc-400">
                Element Timeout: {config?.element_timeout ?? 10}s
              </label>
              <input
                type="range"
                min="5"
                max="30"
                defaultValue={config?.element_timeout ?? 10}
                className="w-full"
              />
            </div>
          </section>

          {/* Info */}
          <section className="pt-4 border-t border-[#2a2a2d]">
            <p className="text-xs text-zinc-600 font-mono">
              IG Unfollower v1.0.0
            </p>
          </section>
        </div>
      </div>
    </>
  );
}

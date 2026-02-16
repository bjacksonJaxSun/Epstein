import { Link } from 'react-router';
import { useAuthStore } from '@/stores/useAuthStore';
import { getTierName } from '@/types/auth';

export function UnauthorizedPage() {
  const user = useAuthStore((state) => state.user);
  const tierName = user ? getTierName(user.maxTierLevel) : 'unknown';

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 px-4">
      <div className="text-center max-w-md">
        <div className="mb-6">
          <div className="w-20 h-20 mx-auto bg-red-500/10 rounded-full flex items-center justify-center">
            <svg
              className="w-10 h-10 text-red-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
        </div>

        <h1 className="text-2xl font-bold text-white mb-3">Access Denied</h1>

        <p className="text-zinc-400 mb-6">
          Your current subscription tier ({tierName}) does not include access to this
          feature. Please upgrade your subscription to unlock this content.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            to="/"
            className="px-6 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg transition"
          >
            Go to Dashboard
          </Link>
          <Link
            to="/settings"
            className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition"
          >
            View Subscription Options
          </Link>
        </div>

        {user && (
          <p className="mt-8 text-xs text-zinc-500">
            Logged in as {user.username} ({user.email})
          </p>
        )}
      </div>
    </div>
  );
}

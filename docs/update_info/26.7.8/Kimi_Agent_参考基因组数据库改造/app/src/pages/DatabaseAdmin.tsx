import { motion } from 'framer-motion';
import { Settings, FileCode, Terminal, Shield } from 'lucide-react';

export default function DatabaseAdmin() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
    >
      {/* Header */}
      <div className="border-b border-space-700/50 bg-space-800/50">
        <div className="mx-auto max-w-[1400px] px-6 py-6 lg:px-12">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-nebula-500/10 border border-nebula-500/20">
              <Shield className="h-6 w-6 text-nebula-400" />
            </div>
            <div>
              <h1 className="font-display text-2xl font-bold text-space-100">
                Database Administration
              </h1>
              <p className="text-sm text-space-500">
                Manage database connections, YAML configuration, and build logs
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Content stub */}
      <div className="mx-auto max-w-[1400px] px-6 py-12 lg:px-12">
        <div className="grid gap-6 md:grid-cols-3">
          {/* Config Card */}
          <div className="rounded-2xl border border-space-700/50 bg-space-800/50 p-8 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-nebula-500/10 mx-auto mb-5">
              <FileCode className="h-7 w-7 text-nebula-400" />
            </div>
            <h3 className="font-display text-lg font-semibold text-space-200 mb-2">
              YAML Configuration
            </h3>
            <p className="text-sm text-space-500 mb-4">
              Edit database connection settings via Monaco editor
            </p>
            <span className="inline-flex items-center rounded-full bg-space-700/50 px-3 py-1 font-mono text-xs text-space-500">
              @monaco-editor/react
            </span>
          </div>

          {/* Logs Card */}
          <div className="rounded-2xl border border-space-700/50 bg-space-800/50 p-8 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-cyan-500/10 mx-auto mb-5">
              <Terminal className="h-7 w-7 text-cyan-400" />
            </div>
            <h3 className="font-display text-lg font-semibold text-space-200 mb-2">
              Build Logs
            </h3>
            <p className="text-sm text-space-500 mb-4">
              View database build and sync logs in real-time
            </p>
            <span className="inline-flex items-center rounded-full bg-space-700/50 px-3 py-1 font-mono text-xs text-space-500">
              WebSocket Stream
            </span>
          </div>

          {/* Settings Card */}
          <div className="rounded-2xl border border-space-700/50 bg-space-800/50 p-8 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-success-500/10 mx-auto mb-5">
              <Settings className="h-7 w-7 text-success-400" />
            </div>
            <h3 className="font-display text-lg font-semibold text-space-200 mb-2">
              System Settings
            </h3>
            <p className="text-sm text-space-500 mb-4">
              Global database module preferences
            </p>
            <span className="inline-flex items-center rounded-full bg-space-700/50 px-3 py-1 font-mono text-xs text-space-500">
              Admin Only
            </span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

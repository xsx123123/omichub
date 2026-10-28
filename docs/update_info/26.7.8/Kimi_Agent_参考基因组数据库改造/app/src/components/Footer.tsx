import { Dna, Github, Mail, ExternalLink } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="border-t border-space-700/50 bg-space-900">
      <div className="mx-auto max-w-[1400px] px-6 py-12 lg:px-12">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {/* Brand */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-nebula-500 to-aurora-500">
                <Dna className="h-4 w-4 text-white" />
              </div>
              <span className="font-display text-base font-bold text-space-100">
                OmicHub
              </span>
            </div>
            <p className="text-sm leading-relaxed text-space-500">
              Gene-centric database browser for plant genomics. Browse, search,
              and explore gene annotations across multiple species and genome
              versions.
            </p>
          </div>

          {/* Quick Links */}
          <div>
            <h4 className="mb-4 font-display text-sm font-semibold text-space-300">
              Quick Links
            </h4>
            <ul className="space-y-2">
              {['Database Hub', 'Browse Genes', 'Admin Panel'].map(item => (
                <li key={item}>
                  <span className="flex items-center gap-1.5 text-sm text-space-500 transition-colors hover:text-nebula-400 cursor-pointer">
                    <ExternalLink className="h-3 w-3" />
                    {item}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          {/* Resources */}
          <div>
            <h4 className="mb-4 font-display text-sm font-semibold text-space-300">
              Resources
            </h4>
            <ul className="space-y-2">
              {['Documentation', 'API Reference', 'Release Notes'].map(item => (
                <li key={item}>
                  <span className="flex items-center gap-1.5 text-sm text-space-500 transition-colors hover:text-nebula-400 cursor-pointer">
                    <ExternalLink className="h-3 w-3" />
                    {item}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          {/* Contact */}
          <div>
            <h4 className="mb-4 font-display text-sm font-semibold text-space-300">
              Contact
            </h4>
            <ul className="space-y-2">
              <li className="flex items-center gap-2 text-sm text-space-500">
                <Mail className="h-3.5 w-3.5" />
                support@omichub.org
              </li>
              <li className="flex items-center gap-2 text-sm text-space-500">
                <Github className="h-3.5 w-3.5" />
                github.com/omichub
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="mt-10 flex flex-col items-center justify-between gap-4 border-t border-space-700/50 pt-6 sm:flex-row">
          <p className="text-xs text-space-600">
            &copy; {new Date().getFullYear()} OmicHub. All rights reserved.
          </p>
          <p className="font-mono text-xs text-space-600">
            v2.1.0 &middot; Database Module
          </p>
        </div>
      </div>
    </footer>
  );
}

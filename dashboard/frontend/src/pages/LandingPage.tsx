import { useState } from 'react';
import { Link, Navigate } from 'react-router';
import { useAuthStore } from '@/stores/useAuthStore';
import { useLogin } from '@/hooks';
import {
  FileText,
  Image,
  Video,
  Users,
  Search,
  Brain,
  Network,
  Map,
  Calendar,
  DollarSign,
  Eye,
  Shield,
  Lock,
  ChevronRight,
  Check,
  Building,
  Scale,
  Newspaper,
} from 'lucide-react';

// Data statistics from the actual database
const STATS = {
  totalDocuments: 623072,
  totalPdfs: 63890,
  totalImages: 503152,
  totalPages: 1500000, // Estimated based on documents
  totalPeople: 2847,
  totalOrganizations: 412,
  totalLocations: 156,
  totalEvents: 3241,
  totalFinancialRecords: 8923,
  videoHours: 47,
  faceDetections: 125000,
  searchableText: '2.3GB',
};

function formatNumber(num: number): string {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M';
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(0) + 'K';
  }
  return num.toString();
}

function StatCard({ icon: Icon, value, label, color }: {
  icon: React.ElementType;
  value: string | number;
  label: string;
  color: string;
}) {
  return (
    <div className="bg-surface-raised border border-border-subtle rounded-xl p-6 text-center hover:border-border-default transition-colors">
      <div className={`inline-flex items-center justify-center w-12 h-12 rounded-lg mb-4 ${color}`}>
        <Icon className="w-6 h-6" />
      </div>
      <div className="text-3xl font-bold text-text-primary mb-1">
        {typeof value === 'number' ? formatNumber(value) : value}
      </div>
      <div className="text-sm text-text-secondary">{label}</div>
    </div>
  );
}

function FeatureCard({ icon: Icon, title, description, color }: {
  icon: React.ElementType;
  title: string;
  description: string;
  color: string;
}) {
  return (
    <div className="bg-surface-raised border border-border-subtle rounded-xl p-6 hover:border-border-default transition-colors">
      <div className={`inline-flex items-center justify-center w-10 h-10 rounded-lg mb-4 ${color}`}>
        <Icon className="w-5 h-5" />
      </div>
      <h3 className="text-lg font-semibold text-text-primary mb-2">{title}</h3>
      <p className="text-sm text-text-secondary leading-relaxed">{description}</p>
    </div>
  );
}

function PricingCard({ tier, price, description, features, highlighted, cta, icon: Icon }: {
  tier: string;
  price: string;
  description: string;
  features: string[];
  highlighted?: boolean;
  cta: string;
  icon: React.ElementType;
}) {
  return (
    <div className={`rounded-xl p-6 ${highlighted
      ? 'bg-gradient-to-b from-accent-blue/20 to-surface-raised border-2 border-accent-blue'
      : 'bg-surface-raised border border-border-subtle'
    }`}>
      <div className="flex items-center gap-3 mb-4">
        <div className={`p-2 rounded-lg ${highlighted ? 'bg-accent-blue/20 text-accent-blue' : 'bg-surface-overlay text-text-secondary'}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-text-primary">{tier}</h3>
          <p className="text-xs text-text-tertiary">{description}</p>
        </div>
      </div>
      <div className="mb-6">
        <span className="text-3xl font-bold text-text-primary">{price}</span>
        {price !== 'Free' && <span className="text-text-tertiary text-sm">/month</span>}
      </div>
      <ul className="space-y-3 mb-6">
        {features.map((feature, i) => (
          <li key={i} className="flex items-start gap-2 text-sm">
            <Check className={`w-4 h-4 mt-0.5 flex-shrink-0 ${highlighted ? 'text-accent-blue' : 'text-accent-green'}`} />
            <span className="text-text-secondary">{feature}</span>
          </li>
        ))}
      </ul>
      <Link
        to="/login"
        className={`block w-full py-2.5 px-4 rounded-lg text-center font-medium transition ${
          highlighted
            ? 'bg-accent-blue hover:bg-accent-blue/90 text-white'
            : 'bg-surface-overlay hover:bg-surface-elevated text-text-primary border border-border-subtle'
        }`}
      >
        {cta}
      </Link>
    </div>
  );
}

function LoginModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const { mutate: login, isPending, error } = useLogin();

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    login({ username, password });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md bg-surface-raised border border-border-subtle rounded-xl p-8 shadow-2xl">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-text-tertiary hover:text-text-primary transition"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-accent-blue/20 rounded-xl mb-4">
            <Lock className="w-6 h-6 text-accent-blue" />
          </div>
          <h2 className="text-xl font-bold text-text-primary">Sign In</h2>
          <p className="text-sm text-text-secondary mt-1">Access the investigation platform</p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-accent-red/10 border border-accent-red/20 rounded-lg">
            <p className="text-accent-red text-sm text-center">
              {error.message || 'Invalid credentials'}
            </p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1.5">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
              autoFocus
              className="w-full px-4 py-2.5 bg-surface-overlay border border-border-subtle rounded-lg text-text-primary placeholder-text-tertiary focus:outline-none focus:ring-2 focus:ring-accent-blue focus:border-transparent transition"
              placeholder="Enter username"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1.5">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="w-full px-4 py-2.5 bg-surface-overlay border border-border-subtle rounded-lg text-text-primary placeholder-text-tertiary focus:outline-none focus:ring-2 focus:ring-accent-blue focus:border-transparent transition"
              placeholder="Enter password"
            />
          </div>
          <button
            type="submit"
            disabled={isPending || !username || !password}
            className="w-full py-2.5 px-4 bg-accent-blue hover:bg-accent-blue/90 disabled:bg-accent-blue/50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition focus:outline-none focus:ring-2 focus:ring-accent-blue focus:ring-offset-2 focus:ring-offset-surface-raised"
          >
            {isPending ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <p className="mt-6 text-xs text-text-tertiary text-center">
          Contact your administrator for access credentials
        </p>
      </div>
    </div>
  );
}

export function LandingPage() {
  const [showLogin, setShowLogin] = useState(false);
  const accessToken = useAuthStore((state) => state.accessToken);

  // If already logged in, redirect to dashboard
  if (accessToken) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="min-h-screen bg-surface-base">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-40 bg-surface-base/80 backdrop-blur-xl border-b border-border-subtle">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-accent-blue to-accent-purple rounded-lg flex items-center justify-center">
              <FileText className="w-4 h-4 text-white" />
            </div>
            <span className="text-lg font-semibold text-text-primary">Epstein Files</span>
          </div>
          <div className="flex items-center gap-4">
            <a href="#features" className="text-sm text-text-secondary hover:text-text-primary transition">Features</a>
            <a href="#data" className="text-sm text-text-secondary hover:text-text-primary transition">Data</a>
            <a href="#access" className="text-sm text-text-secondary hover:text-text-primary transition">Access</a>
            <button
              onClick={() => setShowLogin(true)}
              className="px-4 py-2 bg-accent-blue hover:bg-accent-blue/90 text-white text-sm font-medium rounded-lg transition"
            >
              Sign In
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-32 pb-20 px-6 overflow-hidden">
        {/* Background gradient */}
        <div className="absolute inset-0 bg-gradient-to-b from-accent-blue/5 via-transparent to-transparent" />
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-accent-blue/10 rounded-full blur-3xl" />
        <div className="absolute top-1/3 right-1/4 w-64 h-64 bg-accent-purple/10 rounded-full blur-3xl" />

        <div className="relative max-w-5xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-accent-blue/10 border border-accent-blue/20 rounded-full text-accent-blue text-sm mb-8">
            <Shield className="w-4 h-4" />
            <span>Investigative Research Platform</span>
          </div>

          <h1 className="text-5xl md:text-6xl font-bold text-text-primary mb-6 leading-tight">
            The Most Comprehensive
            <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-blue to-accent-cyan">
              Epstein Document Archive
            </span>
          </h1>

          <p className="text-xl text-text-secondary max-w-3xl mx-auto mb-10 leading-relaxed">
            Over 600,000 documents, images, and media files from court records, FBI evidence,
            and declassified materials. Fully searchable with AI-powered analysis,
            relationship mapping, and advanced investigation tools.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4">
            <button
              onClick={() => setShowLogin(true)}
              className="px-8 py-3 bg-accent-blue hover:bg-accent-blue/90 text-white font-medium rounded-lg transition flex items-center gap-2"
            >
              Access the Archive
              <ChevronRight className="w-4 h-4" />
            </button>
            <a
              href="#data"
              className="px-8 py-3 bg-surface-raised hover:bg-surface-overlay text-text-primary font-medium rounded-lg border border-border-subtle transition"
            >
              Explore the Data
            </a>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section id="data" className="py-20 px-6 bg-surface-sunken">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-text-primary mb-4">Archive at a Glance</h2>
            <p className="text-text-secondary max-w-2xl mx-auto">
              The largest digitized collection of Epstein-related documents ever assembled,
              fully indexed and searchable.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            <StatCard icon={FileText} value={STATS.totalDocuments} label="Total Documents" color="bg-accent-blue/20 text-accent-blue" />
            <StatCard icon={FileText} value={STATS.totalPdfs} label="PDF Files" color="bg-accent-purple/20 text-accent-purple" />
            <StatCard icon={Image} value={STATS.totalImages} label="Images" color="bg-accent-green/20 text-accent-green" />
            <StatCard icon={Users} value={STATS.totalPeople} label="Named Individuals" color="bg-accent-cyan/20 text-accent-cyan" />
            <StatCard icon={Building} value={STATS.totalOrganizations} label="Organizations" color="bg-accent-orange/20 text-accent-orange" />
            <StatCard icon={DollarSign} value={STATS.totalFinancialRecords} label="Financial Records" color="bg-accent-amber/20 text-accent-amber" />
          </div>

          <div className="mt-12 grid md:grid-cols-3 gap-6">
            <div className="bg-surface-raised border border-border-subtle rounded-xl p-6">
              <h3 className="text-lg font-semibold text-text-primary mb-4">Data Sources</h3>
              <ul className="space-y-3 text-sm text-text-secondary">
                <li className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-accent-blue" />
                  Court filings and legal documents
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-accent-purple" />
                  FBI evidence photos and materials
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-accent-green" />
                  Flight logs and travel records
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-accent-amber" />
                  Financial transaction records
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-accent-cyan" />
                  Declassified government documents
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-accent-orange" />
                  Media and surveillance footage
                </li>
              </ul>
            </div>

            <div className="bg-surface-raised border border-border-subtle rounded-xl p-6">
              <h3 className="text-lg font-semibold text-text-primary mb-4">Processing Pipeline</h3>
              <ul className="space-y-3 text-sm text-text-secondary">
                <li className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-accent-green" />
                  OCR text extraction from all documents
                </li>
                <li className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-accent-green" />
                  AI-powered entity recognition
                </li>
                <li className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-accent-green" />
                  Video transcription with timestamps
                </li>
                <li className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-accent-green" />
                  Face detection and clustering
                </li>
                <li className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-accent-green" />
                  Semantic vector embeddings
                </li>
                <li className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-accent-green" />
                  Relationship graph construction
                </li>
              </ul>
            </div>

            <div className="bg-surface-raised border border-border-subtle rounded-xl p-6">
              <h3 className="text-lg font-semibold text-text-primary mb-4">Unique Capabilities</h3>
              <ul className="space-y-3 text-sm text-text-secondary">
                <li className="flex items-center gap-2">
                  <Brain className="w-4 h-4 text-accent-purple" />
                  Ask questions in natural language
                </li>
                <li className="flex items-center gap-2">
                  <Network className="w-4 h-4 text-accent-blue" />
                  Visualize connection networks
                </li>
                <li className="flex items-center gap-2">
                  <Eye className="w-4 h-4 text-accent-cyan" />
                  Cross-reference faces across images
                </li>
                <li className="flex items-center gap-2">
                  <Map className="w-4 h-4 text-accent-green" />
                  Geographic activity mapping
                </li>
                <li className="flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-accent-amber" />
                  Timeline reconstruction
                </li>
                <li className="flex items-center gap-2">
                  <DollarSign className="w-4 h-4 text-accent-orange" />
                  Financial flow analysis
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-text-primary mb-4">Investigation Tools</h2>
            <p className="text-text-secondary max-w-2xl mx-auto">
              Purpose-built tools for investigative journalists, researchers, and law enforcement
              to uncover connections and patterns in the data.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            <FeatureCard
              icon={Search}
              title="Semantic Search"
              description="Go beyond keyword matching. Ask questions like 'Who visited the island in 1999?' and get relevant results from across all documents."
              color="bg-accent-blue/20 text-accent-blue"
            />
            <FeatureCard
              icon={Brain}
              title="AI Chat Assistant"
              description="Conversational AI that understands the entire archive. Get answers, summaries, and insights with source citations."
              color="bg-accent-purple/20 text-accent-purple"
            />
            <FeatureCard
              icon={Network}
              title="Relationship Mapping"
              description="Interactive network graphs showing connections between people, organizations, and events. Find hidden relationships."
              color="bg-accent-cyan/20 text-accent-cyan"
            />
            <FeatureCard
              icon={Eye}
              title="Face Recognition"
              description="Computer vision identifies and clusters faces across 500,000+ images. Find every photo of a specific individual."
              color="bg-accent-green/20 text-accent-green"
            />
            <FeatureCard
              icon={Calendar}
              title="Timeline Analysis"
              description="Reconstruct events chronologically. See who was where, when, and correlate with document evidence."
              color="bg-accent-amber/20 text-accent-amber"
            />
            <FeatureCard
              icon={DollarSign}
              title="Financial Forensics"
              description="Sankey diagrams and flow analysis for tracking money movement between entities and accounts."
              color="bg-accent-orange/20 text-accent-orange"
            />
            <FeatureCard
              icon={Map}
              title="Geographic Intelligence"
              description="Map all locations mentioned in documents. Visualize travel patterns, property holdings, and activity clusters."
              color="bg-entity-location/20 text-entity-location"
            />
            <FeatureCard
              icon={Video}
              title="Video Transcription"
              description="All video content transcribed and searchable. Jump to specific moments based on spoken content."
              color="bg-accent-pink/20 text-accent-pink"
            />
            <FeatureCard
              icon={FileText}
              title="Document Analysis"
              description="Full-text OCR, document classification, handwriting detection, and metadata extraction for every file."
              color="bg-text-tertiary/20 text-text-tertiary"
            />
          </div>
        </div>
      </section>

      {/* Use Cases Section */}
      <section className="py-20 px-6 bg-surface-sunken">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-text-primary mb-4">Who This Is For</h2>
            <p className="text-text-secondary max-w-2xl mx-auto">
              Built for professionals who need to investigate, research, and report on this case
              with rigor and precision.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-accent-blue/20 rounded-2xl mb-6">
                <Scale className="w-8 h-8 text-accent-blue" />
              </div>
              <h3 className="text-xl font-semibold text-text-primary mb-3">Law Enforcement</h3>
              <p className="text-text-secondary text-sm leading-relaxed">
                Federal investigators and prosecutors pursuing ongoing cases related to trafficking
                networks. Cross-reference evidence, identify witnesses, and build timelines.
              </p>
            </div>

            <div className="text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-accent-purple/20 rounded-2xl mb-6">
                <Newspaper className="w-8 h-8 text-accent-purple" />
              </div>
              <h3 className="text-xl font-semibold text-text-primary mb-3">Investigative Journalists</h3>
              <p className="text-text-secondary text-sm leading-relaxed">
                Reporters working on in-depth coverage. Search thousands of documents in seconds,
                discover new connections, and verify sources with primary evidence.
              </p>
            </div>

            <div className="text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-accent-cyan/20 rounded-2xl mb-6">
                <Users className="w-8 h-8 text-accent-cyan" />
              </div>
              <h3 className="text-xl font-semibold text-text-primary mb-3">Academic Researchers</h3>
              <p className="text-text-secondary text-sm leading-relaxed">
                Scholars studying criminal networks, institutional failures, and power structures.
                Access primary sources with full citation support.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Access Tiers Section */}
      <section id="access" className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-text-primary mb-4">Access Levels</h2>
            <p className="text-text-secondary max-w-2xl mx-auto">
              Free access for government officials conducting official investigations.
              Subscription access for journalists and researchers.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            <PricingCard
              tier="Government"
              price="Free"
              description="For official investigations"
              icon={Shield}
              features={[
                'Full archive access',
                'All investigation tools',
                'AI-powered search & chat',
                'Face recognition',
                'Export capabilities',
                'Priority support',
              ]}
              cta="Request Access"
            />

            <PricingCard
              tier="Professional"
              price="$49"
              description="For journalists & researchers"
              icon={Newspaper}
              highlighted
              features={[
                'Full archive access',
                'All investigation tools',
                'AI-powered search & chat',
                'Face recognition',
                'Export to CSV/JSON',
                'Email support',
              ]}
              cta="Get Started"
            />

            <PricingCard
              tier="Basic"
              price="$19"
              description="For curious individuals"
              icon={Users}
              features={[
                'Full archive browsing',
                'Keyword search',
                'Document viewing',
                'People & org directories',
                'Timeline & map views',
                'Community support',
              ]}
              cta="Subscribe"
            />
          </div>

          <p className="text-center text-text-tertiary text-sm mt-8">
            Government officials: Contact us with your official credentials to receive complimentary access.
          </p>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-6 bg-gradient-to-b from-surface-base to-surface-sunken">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl font-bold text-text-primary mb-4">
            Start Your Investigation
          </h2>
          <p className="text-text-secondary mb-8">
            The truth is in the documents. Access the most complete, searchable archive
            of Epstein-related materials ever assembled.
          </p>
          <button
            onClick={() => setShowLogin(true)}
            className="px-8 py-3 bg-accent-blue hover:bg-accent-blue/90 text-white font-medium rounded-lg transition inline-flex items-center gap-2"
          >
            Sign In to Access
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-6 border-t border-border-subtle">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-gradient-to-br from-accent-blue to-accent-purple rounded-lg flex items-center justify-center">
                <FileText className="w-4 h-4 text-white" />
              </div>
              <span className="text-text-primary font-semibold">Epstein Files</span>
            </div>

            <p className="text-sm text-text-tertiary text-center">
              This platform provides access to publicly released documents for research and investigative purposes.
            </p>

            <div className="flex items-center gap-6 text-sm text-text-tertiary">
              <a href="#" className="hover:text-text-secondary transition">Privacy</a>
              <a href="#" className="hover:text-text-secondary transition">Terms</a>
              <a href="#" className="hover:text-text-secondary transition">Contact</a>
            </div>
          </div>
        </div>
      </footer>

      {/* Login Modal */}
      <LoginModal isOpen={showLogin} onClose={() => setShowLogin(false)} />
    </div>
  );
}

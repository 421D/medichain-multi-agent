import { Component, Suspense, lazy, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import AppLayout from "@/components/AppLayout";
import SessionDetail from "@/pages/SessionDetail";
import NotFound from "@/pages/NotFound";

// L22 fix: lazy load heavier pages
const Dashboard = lazy(() => import("@/pages/Dashboard"));
const Consultations = lazy(() => import("@/pages/Consultations"));
const Workflow = lazy(() => import("@/pages/Workflow"));
const Evaluation = lazy(() => import("@/pages/Evaluation"));
const Tools = lazy(() => import("@/pages/Tools"));
const History = lazy(() => import("@/pages/History"));

const LazyFallback = (
  <div className="flex items-center justify-center h-full text-muted-foreground">Loading...</div>
);

class ErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  // M19 fix: log errors via componentDidCatch
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center min-h-screen bg-background text-foreground">
          <div className="text-center space-y-4 p-8 max-w-md">
            <h1 className="text-lg font-semibold">Something went wrong</h1>
            <p className="text-sm text-muted-foreground">
              {this.state.error?.message || "An unexpected error occurred."}
            </p>
            <div className="flex items-center justify-center gap-3">
              {/* M19 fix: Go to Dashboard button that resets error state */}
              <button
                onClick={() => {
                  this.setState({ hasError: false, error: null });
                  window.location.href = '/';
                }}
                className="px-4 py-2 text-sm rounded-lg border border-border text-foreground hover:bg-muted transition-colors"
              >
                Go to Dashboard
              </button>
              <button
                onClick={() => window.location.reload()}
                className="px-4 py-2 text-sm rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition-opacity"
              >
                Reload page
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// L14 fix: wrapper that provides location-based key to reset ErrorBoundary on navigation
function ErrorBoundaryWithReset({ children }: { children: ReactNode }) {
  const location = useLocation();
  return <ErrorBoundary key={location.pathname}>{children}</ErrorBoundary>;
}

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ErrorBoundaryWithReset>
          <Suspense fallback={LazyFallback}>
            <Routes>
              <Route element={<AppLayout />}>
                <Route path="/" element={<Dashboard />} />
                <Route path="/consultations" element={<Consultations />} />
                <Route path="/session/:sessionId" element={<SessionDetail />} />
                <Route path="/flow" element={<Workflow />} />
                <Route path="/evaluation" element={<Evaluation />} />
                <Route path="/tools" element={<Tools />} />
                <Route path="/history" element={<History />} />
              </Route>
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </ErrorBoundaryWithReset>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;

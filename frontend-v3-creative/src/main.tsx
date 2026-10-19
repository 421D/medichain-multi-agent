import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";
// MediChain design-system styles — defines .card, .btn, .agent-pill, .chat-*,
// .flow-*, .timeline, .safety-* etc. Imported AFTER index.css so the design
// classes take precedence over the baseline shadcn utilities where they overlap.
import "./styles/medichain.css";

createRoot(document.getElementById("root")!).render(<App />);

import { BrowserRouter, Routes, Route } from "react-router-dom";
import { TopBar } from "@/components/layout/TopBar";
import { ProgressBar } from "@/components/layout/ProgressBar";
import { Landing } from "@/pages/Landing";
import { Session } from "@/pages/Session";
import { Completion } from "@/pages/Completion";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-[#0A0A0A] text-[#E8E8E8]">
        <TopBar />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/session/:id" element={<Session />} />
          <Route path="/complete" element={<Completion />} />
        </Routes>
        <ProgressBar />
      </div>
    </BrowserRouter>
  );
}

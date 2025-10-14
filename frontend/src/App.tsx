import { useState, useRef } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { Header } from "./components/Header";
import { ChatInterface } from "./components/ChatInterface";
import { PDFPanel } from "./components/PDFPanel";
import { KnowledgeBaseManagement } from "./components/KnowledgeBaseManagement";
import MinimalMedicalChat from "./components/MinimalMedicalChat";
import { Toaster } from "./components/ui/sonner";

export default function App() {
  const [chatKey, setChatKey] = useState(0);
  const [currentFileId, setCurrentFileId] = useState<string>('');
  const [currentFileName, setCurrentFileName] = useState<string>('');
  const [currentTotalPages, setCurrentTotalPages] = useState<number>(0);
  const refreshStatsRef = useRef<(() => void) | undefined>(undefined);

  const handleClearChat = () => {
    setChatKey((prev) => prev + 1);
  };

  const handleFileReady = (fileId: string, fileName: string, totalPages: number) => {
    setCurrentFileId(fileId);
    setCurrentFileName(fileName);  
    setCurrentTotalPages(totalPages);
    // 刷新统计数据
    if (refreshStatsRef.current) {
      refreshStatsRef.current();
    }
  };

  return (
    <Router>
      <div className="dark min-h-screen bg-background text-foreground relative overflow-hidden">
        {/* Enhanced background system */}
        <div className="background-system">
          {/* Floating orbs */}
          <div className="floating-elements">
            <div className="floating-orb floating-orb-1"></div>
            <div className="floating-orb floating-orb-2"></div>
            <div className="floating-orb floating-orb-3"></div>
            <div className="floating-orb floating-orb-4"></div>
          </div>

          {/* Geometric decorations */}
          <div className="geometric-decorations">
            <div className="geometric-line geometric-line-1"></div>
            <div className="geometric-line geometric-line-2"></div>
            <div className="geometric-line geometric-line-3"></div>
            <div className="geometric-polygon geometric-polygon-1"></div>
            <div className="geometric-polygon geometric-polygon-2"></div>
            <div className="geometric-circle geometric-circle-1"></div>
            <div className="geometric-circle geometric-circle-2"></div>
          </div>

          {/* Particle system */}
          <div className="particle-system">
            {Array.from({ length: 15 }).map((_, i) => (
              <div key={i} className={`particle particle-${i + 1}`}></div>
            ))}
          </div>

          {/* Light beams */}
          <div className="light-beams">
            <div className="light-beam light-beam-1"></div>
            <div className="light-beam light-beam-2"></div>
            <div className="light-beam light-beam-3"></div>
          </div>

          {/* Grid overlay */}
          <div className="grid-overlay"></div>
        </div>

        <div className="relative z-10">
          <div className="h-screen flex flex-col">
            {/* Header with reduced bottom margin */}
            <div className="max-w-7xl mx-auto w-full">
              <Header refreshStatsRef={refreshStatsRef} />
            </div>

            {/* Main Content - Routes */}
            <div className="flex-1 min-h-0 px-6 pb-6">
              <Routes>
                {/* 主页 - 聊天和PDF面板 */}
                <Route path="/" element={
                  <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-6 h-full">
                    {/* Left Column - Chat Interface (larger) */}
                    <div className="flex flex-col min-h-0">
                      <ChatInterface
                        key={chatKey}
                        onClearChat={handleClearChat}
                        fileId={currentFileId}
                        fileName={currentFileName}
                      />
                    </div>

                    {/* Right Column - PDF Panel (smaller, aligned to right edge) */}
                    <div className="flex flex-col min-h-0">
                      <PDFPanel 
                        onFileReady={handleFileReady}
                      />
                    </div>
                  </div>
                } />
                
                {/* 知识库管理页面 */}
                <Route path="/knowledge-base" element={
                  <div className="max-w-7xl mx-auto">
                    <KnowledgeBaseManagement />
                  </div>
                } />

                {/* 最简流式对接示例 */}
                <Route path="/minimal" element={<MinimalMedicalChat />} />
              </Routes>
            </div>
          </div>
        </div>

        {/* Toast notifications */}
        <Toaster 
          position="top-right"
          expand={false}
          richColors
          closeButton
          theme="dark"
        />
      </div>
    </Router>
  );
}
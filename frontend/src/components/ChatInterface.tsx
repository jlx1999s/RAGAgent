import { useState, useRef, useEffect, useMemo } from "react";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { ScrollArea } from "./ui/scroll-area";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { Send, User, Bot, Sparkles, Stethoscope } from "lucide-react";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { processChatStream, clearSession, createMedicalChatStream, processMedicalChatStream, clearMedicalSession, analyzeSymptoms } from "../services/api";
import { toast } from "sonner";

type Reference = {
  id: number;
  text: string;
  page: number;
  citationId?: string;
  rank?: number;
  snippet?: string;
};

type Message = {
  id: string;
  type: "user" | "assistant";
  content: string;
  timestamp: Date;
  references?: Reference[];
};

type ChatMode = "general" | "medical";

type ChatInterfaceProps = {
  onClearChat: () => void;
  fileId?: string;
  fileName?: string;
  threadId?: string; // 可选：传给后端存历史（默认 "default"）
};

export function ChatInterface({
  onClearChat,
  fileId,
  fileName,
  threadId = "default",
}: ChatInterfaceProps) {
  const [chatMode, setChatMode] = useState<ChatMode>("general");
  
  const initialAssistant = chatMode === "medical" 
    ? "您好！我是您的医疗AI助手。我可以帮助您分析症状、提供医疗建议，并基于上传的医疗文档回答问题。请注意，我的建议仅供参考，不能替代专业医疗诊断。"
    : "Hello! I'm your AI assistant. You can chat directly, and if you upload a PDF I can answer with document-grounded citations.";

  const [messages, setMessages] = useState<Message[]>([
    { id: "welcome", type: "assistant", content: initialAssistant, timestamp: new Date() },
  ]);

  // 监控 chatMode 状态变化
  useEffect(() => {
    console.log("🔄 chatMode state changed to:", chatMode);
  }, [chatMode]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);

  // 当前流式生成中的内容与引用
  const [currentResponse, setCurrentResponse] = useState("");
  const [currentReferences, setCurrentReferences] = useState<Reference[]>([]);

  // refs 用于避免闭包 & 在 onDone 时拿到最新值
  const currentResponseRef = useRef("");
  const currentReferencesRef = useRef<Reference[]>([]);
  const citationIdsRef = useRef<Set<string>>(new Set());

  // 终止当前 SSE 的控制器（由 processChatStream 内部使用）
  const abortRef = useRef<AbortController | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const canSend = useMemo(() => input.trim().length > 0 && !isTyping, [input, isTyping]);

  // 自动滚动到底
  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping, currentResponse, currentReferences]);

  // 输入框自动高度
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + "px";
    }
  }, [input]);

  // 卸载时中断流
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const handleSend = async () => {
    if (!canSend) return;

    // 若有进行中的流，先中断
    abortRef.current?.abort();

    // 先落地用户消息
    const userMessage: Message = {
      id: Date.now().toString(),
      type: "user",
      content: input,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);

    // 准备流式状态
    const userText = input;
    setInput("");
    setIsTyping(true);
    setCurrentResponse("");
    setCurrentReferences([]);
    currentResponseRef.current = "";
    currentReferencesRef.current = [];
    citationIdsRef.current = new Set();

    try {
      if (chatMode === "medical") {
        // 使用医疗聊天API
        await processMedicalChatStream(
          userText,
          // onToken
          (token: string) => {
            setCurrentResponse((prev) => prev + token);
            currentResponseRef.current += token;
          },
          // onCitation
          (c: {
            citation_id: string;
            fileId: string;
            rank: number;
            page: number;
            previewUrl: string;
            snippet?: string;
          }) => {
            // 去重：按 citation_id
            if (!c.citation_id || citationIdsRef.current.has(c.citation_id)) return;
            citationIdsRef.current.add(c.citation_id);

            const newRef: Reference = {
              id: currentReferencesRef.current.length + 1,
              text: `第 ${c.page ?? "?"} 页相关内容`,
              page: c.page ?? 0,
              citationId: c.citation_id,
              rank: c.rank,
              snippet: c.snippet,
            };

            // 更新 state & ref
            setCurrentReferences((prev) => [...prev, newRef]);
            currentReferencesRef.current = [...currentReferencesRef.current, newRef];
          },
          // onDone
          (meta: { used_retrieval: boolean; medical_analysis?: any }) => {
            const finalResponse = currentResponseRef.current;
            const finalRefs = [...currentReferencesRef.current];

            const assistantMessage: Message = {
              id: (Date.now() + 1).toString(),
              type: "assistant",
              content: finalResponse || "_（空响应）_",
              timestamp: new Date(),
              references: finalRefs.length ? finalRefs : undefined,
            };

            setMessages((prev) => [...prev, assistantMessage]);
            setIsTyping(false);
            setCurrentResponse("");
            setCurrentReferences([]);
            currentResponseRef.current = "";
            currentReferencesRef.current = [];
            citationIdsRef.current.clear();

            if (meta?.used_retrieval) {
              toast.success("基于医疗文档提供回答");
            }
            if (meta?.medical_analysis) {
              toast.info("已进行医疗安全分析");
            }
            // 重新聚焦输入框
            textareaRef.current?.focus();
          },
          // onError
          (errText: string) => {
            console.error("Medical chat error:", errText);
            setIsTyping(false);
            setCurrentResponse("");
            setCurrentReferences([]);
            currentResponseRef.current = "";
            currentReferencesRef.current = [];
            citationIdsRef.current.clear();

            const errorMessage: Message = {
              id: (Date.now() + 1).toString(),
              type: "assistant",
              content: `抱歉，处理您的医疗咨询时出现错误：${errText}`,
              timestamp: new Date(),
            };
            setMessages((prev) => [...prev, errorMessage]);
            toast.error("医疗咨询失败");
          },
          // sessionId
          threadId,
          // 医疗参数
          "内科",  // department
          "临床指南",  // documentType
          "内分泌、营养和代谢疾病",  // diseaseCategory
        );
      } else {
        // 使用普通聊天API
        await processChatStream(
          userText,
          // onToken
          (token: string) => {
            setCurrentResponse((prev) => prev + token);
            currentResponseRef.current += token;
          },
          // onCitation
          (c: {
            citation_id: string;
            fileId: string;
            rank: number;
            page: number;
            previewUrl: string;
            snippet?: string;
          }) => {
            // 去重：按 citation_id
            if (!c.citation_id || citationIdsRef.current.has(c.citation_id)) return;
            citationIdsRef.current.add(c.citation_id);

            const newRef: Reference = {
              id: currentReferencesRef.current.length + 1,
              text: `第 ${c.page ?? "?"} 页相关内容`,
              page: c.page ?? 0,
              citationId: c.citation_id,
              rank: c.rank,
              snippet: c.snippet,
            };

            // 更新 state & ref
            setCurrentReferences((prev) => [...prev, newRef]);
            currentReferencesRef.current = [...currentReferencesRef.current, newRef];
          },
          // onDone
          (meta: { used_retrieval: boolean }) => {
            const finalResponse = currentResponseRef.current;
            const finalRefs = [...currentReferencesRef.current];

            const assistantMessage: Message = {
              id: (Date.now() + 1).toString(),
              type: "assistant",
              content: finalResponse || "_（空响应）_",
              timestamp: new Date(),
              references: finalRefs.length ? finalRefs : undefined,
            };

            setMessages((prev) => [...prev, assistantMessage]);
            setIsTyping(false);
            setCurrentResponse("");
            setCurrentReferences([]);
            currentResponseRef.current = "";
            currentReferencesRef.current = [];
            citationIdsRef.current.clear();

            if (meta?.used_retrieval) {
              toast.success("Response grounded by document context");
            }
            // 重新聚焦输入框
            textareaRef.current?.focus();
          },
          // onError
          (errText: string) => {
            console.error("Chat error:", errText);
            setIsTyping(false);
            setCurrentResponse("");
            setCurrentReferences([]);
            currentResponseRef.current = "";
            currentReferencesRef.current = [];
            citationIdsRef.current.clear();

            const errorMessage: Message = {
              id: (Date.now() + 1).toString(),
              type: "assistant",
              content: `抱歉，处理你的请求时出现错误：${errText}`,
              timestamp: new Date(),
            };
            setMessages((prev) => [...prev, errorMessage]);
            toast.error("Failed to get response");
          },
          // 传递 fileId & threadId
          fileId,
          threadId,
        );
      }
    } catch (e) {
      console.error("Chat request failed:", e);
      setIsTyping(false);
      setCurrentResponse("");
      setCurrentReferences([]);
      currentResponseRef.current = "";
      currentReferencesRef.current = [];
      citationIdsRef.current.clear();
      toast.error("Failed to send message");
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearChat = async () => {
    try {
      abortRef.current?.abort();
      
      if (chatMode === "medical") {
        await clearMedicalSession(threadId);
      } else {
        await clearSession(threadId);
      }
      
      setMessages([
        {
          id: "welcome",
          type: "assistant",
          content: initialAssistant,
          timestamp: new Date(),
        },
      ]);
      onClearChat();
      toast.success("Chat history cleared");
    } catch (error) {
      // API 不可达时本地清空
      if (error instanceof TypeError && String(error).includes("Failed to fetch")) {
        setMessages([
          {
            id: "welcome",
            type: "assistant",
            content: initialAssistant,
            timestamp: new Date(),
          },
        ]);
        onClearChat();
        toast.success("Chat history cleared (Local)");
        return;
      }
      console.error("Failed to clear chat:", error);
      toast.error("Failed to clear chat history");
    } finally {
      textareaRef.current?.focus();
    }
  };

  // 切换聊天模式时重置聊天
  const handleModeChange = (mode: ChatMode) => {
    console.log("=== handleModeChange DEBUG ===");
    console.log("Called with mode:", mode);
    console.log("Current chatMode:", chatMode);
    console.log("Are they different?", mode !== chatMode);
    
    if (mode !== chatMode) {
      console.log("✅ Changing mode from", chatMode, "to", mode);
      setChatMode(mode);
      
      // 添加延迟检查状态更新
      setTimeout(() => {
        console.log("🔍 State check after 100ms - chatMode should be:", mode);
      }, 100);
      
      setMessages([
        {
          id: "welcome",
          type: "assistant",
          content: mode === "medical" 
            ? "您好！我是您的医疗AI助手。我可以帮助您分析症状、提供医疗建议，并基于上传的医疗文档回答问题。请注意，我的建议仅供参考，不能替代专业医疗诊断。"
            : "Hello! I'm your AI assistant. You can chat directly, and if you upload a PDF I can answer with document-grounded citations.",
          timestamp: new Date(),
        },
      ]);
      // 移除 onClearChat() 调用，因为它会重置整个组件
      // onClearChat();
      console.log("✅ Mode change completed");
    } else {
      console.log("⚠️ Mode is already", mode, "- no change needed");
    }
    console.log("=== END DEBUG ===");
  };

  return (
    <div className="glass-panel-bright h-full flex flex-col max-h-full relative overflow-hidden">
      {/* 背景装饰 */}
      <div className="absolute inset-0 opacity-5 pointer-events-none">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/20 via-transparent to-purple-500/20"></div>
      </div>

      {/* 头部 */}
      <div className="relative p-6 border-b border-border/80 flex-shrink-0 z-10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg border shadow-lg ${
              chatMode === "medical" 
                ? "bg-green-500/15 border-green-500/30" 
                : "bg-primary/15 border-primary/30"
            }`}>
              {chatMode === "medical" ? (
                <Stethoscope className="w-5 h-5 text-green-500" />
              ) : (
                <Sparkles className="w-5 h-5 text-primary" />
              )}
            </div>
            <div>
              <h2 className="elegant-title text-base">
                {chatMode === "medical" ? "医疗AI助手" : "AI Assistant"}
              </h2>
              <p className="text-xs text-muted-foreground/80 mt-1">
                {fileId && fileName ? `Analyzing: ${fileName}` : 
                 chatMode === "medical" ? "医疗知识库支持" : "Powered by RAG Technology"}
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            {/* 聊天模式选择器 */}
            <div className="flex items-center gap-2 p-1 bg-secondary/40 rounded-lg border border-border/40 relative z-20">
              <Button
                variant={chatMode === "general" ? "default" : "ghost"}
                size="sm"
                onClick={(e) => {
                  console.log("🔵 General button clicked", e);
                  console.log("Current chatMode before click:", chatMode);
                  handleModeChange("general");
                }}
                className={`text-xs px-3 py-1 h-7 transition-all duration-200 cursor-pointer ${
                  chatMode === "general" 
                    ? "bg-primary text-primary-foreground shadow-sm" 
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Sparkles className="w-3 h-3 mr-1" />
                普通
              </Button>
              <Button
                variant={chatMode === "medical" ? "default" : "ghost"}
                size="sm"
                onClick={(e) => {
                  console.log("🟢 Medical button clicked", e);
                  console.log("Current chatMode before click:", chatMode);
                  console.log("Button variant will be:", chatMode === "medical" ? "default" : "ghost");
                  console.log("Button className will include medical styles:", chatMode === "medical");
                  handleModeChange("medical");
                }}
                className={`text-xs px-3 py-1 h-7 transition-all duration-200 cursor-pointer ${
                  chatMode === "medical" 
                    ? "bg-green-500 text-white shadow-sm hover:bg-green-600" 
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Stethoscope className="w-3 h-3 mr-1" />
                医疗 {chatMode === "medical" ? "✅" : ""}
              </Button>
            </div>
            
            <Button
              variant="outline"
              size="sm"
              onClick={clearChat}
              className="text-muted-foreground hover:text-white hover:bg-destructive/90 hover:border-destructive hover:shadow-lg hover:shadow-destructive/25 border border-border/60 transition-all duration-300 hover:scale-105 cursor-pointer"
            >
              Clear
            </Button>
          </div>
        </div>
      </div>

      {/* 消息区 */}
      <div className="flex-1 min-h-0 overflow-hidden relative">
        <ScrollArea className="h-full">
          <div className="p-6">
            <div className="space-y-4">
              {messages.map((m) => (
                <div key={m.id} className={`flex gap-4 ${m.type === "user" ? "justify-end" : "justify-start"}`}>
                  {m.type === "assistant" && (
                    <Avatar className="w-9 h-9 border-2 border-primary/30 flex-shrink-0 shadow-lg">
                      <AvatarFallback className="bg-gradient-to-br from-primary/15 to-purple-500/15">
                        <Bot className="w-5 h-5 text-primary" />
                      </AvatarFallback>
                    </Avatar>
                  )}

                  <div className={`max-w-[80%] ${m.type === "user" ? "order-first" : ""}`}>
                    <div
                      className={`p-4 rounded-2xl shadow-xl ${
                        m.type === "user"
                          ? "bg-gradient-to-br from-primary to-primary/80 text-primary-foreground ml-auto border border-primary/30"
                          : "bg-secondary/40 border border-border/40 backdrop-blur-sm"
                      }`}
                    >
                      {m.type === "user" ? (
                        <p className="text-primary-foreground leading-relaxed text-base whitespace-pre-wrap">{m.content}</p>
                      ) : (
                        <MarkdownRenderer content={m.content} references={m.references} />
                      )}
                    </div>
                  </div>

                  {m.type === "user" && (
                    <Avatar className="w-9 h-9 border-2 border-border/40 flex-shrink-0 shadow-lg">
                      <AvatarFallback className="bg-gradient-to-br from-muted to-muted/80">
                        <User className="w-5 h-5" />
                      </AvatarFallback>
                    </Avatar>
                  )}
                </div>
              ))}

              {/* 正在生成中的一条 */}
              {isTyping && (
                <div className="flex gap-4">
                  <Avatar className="w-9 h-9 border-2 border-primary/30 flex-shrink-0 shadow-lg">
                    <AvatarFallback className="bg-gradient-to-br from-primary/15 to-purple-500/15">
                      <Bot className="w-5 h-5 text-primary" />
                    </AvatarFallback>
                  </Avatar>
                  <div className="max-w-[80%]">
                    <div className="bg-secondary/40 border border-border/40 backdrop-blur-sm rounded-2xl p-4 shadow-xl">
                      {currentResponse ? (
                        <MarkdownRenderer content={currentResponse} references={currentReferences} />
                      ) : (
                        <div className="flex space-x-2">
                          <div className="w-2 h-2 bg-primary/70 rounded-full animate-bounce"></div>
                          <div className="w-2 h-2 bg-primary/70 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }}></div>
                          <div className="w-2 h-2 bg-primary/70 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </div>
        </ScrollArea>
      </div>

      {/* 输入区 */}
      <div className="relative p-6 border-t border-border/60 flex-shrink-0 bg-card/40">
        <div className="flex gap-3 items-end">
          <div className="relative flex-1">
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder={fileId ? "Ask a question about your document..." : "Ask anything… (upload a PDF to enable RAG)"}
              className="flex-1 bg-input/60 border-border/40 focus:border-primary/60 glow-ring text-foreground placeholder:text-muted-foreground/70 rounded-xl px-4 py-3 backdrop-blur-sm resize-none min-h-[52px] max-h-[120px] text-base leading-relaxed flex items-center"
              disabled={isTyping}
              rows={1}
            />
          </div>
          <Button
            onClick={handleSend}
            disabled={!canSend}
            className="bg-gradient-to-r from-primary to-primary/80 hover:from-primary/90 hover:to-primary/70 text-primary-foreground h-[52px] w-[52px] p-0 rounded-xl shadow-lg transition-all duration-200 border border-primary/30 flex-shrink-0"
          >
            <Send className="w-5 h-5" />
          </Button>
        </div>
      </div>
    </div>
  );
}

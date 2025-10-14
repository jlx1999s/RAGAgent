import { useState } from "react";
import { processMedicalChatStream, clearMedicalSession } from "@/services/api";

export default function MinimalMedicalChat() {
  const [message, setMessage] = useState("患者长期血压维持在140/90，如何管理与用药？");
  const [sessionId, setSessionId] = useState("demo_minimal_session");
  const [output, setOutput] = useState("");
  const [status, setStatus] = useState<"idle" | "streaming" | "done" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [citationsCount, setCitationsCount] = useState(0);
  const [qualityInfo, setQualityInfo] = useState<string>("");

  const startStream = async () => {
    if (!message.trim()) return;
    setOutput("");
    setStatus("streaming");
    setErrorMsg("");
    setCitationsCount(0);
    setQualityInfo("");

    await processMedicalChatStream(
      message,
      // onToken
      (text) => {
        setOutput((prev) => prev + text);
      },
      // onCitation
      (_c) => {
        setCitationsCount((n) => n + 1);
      },
      // onMetadata
      (meta) => {
        if (meta?.quality_assessment) {
          const qa = meta.quality_assessment;
          const info = `质量: ${qa.quality_level}(${(qa.quality_score * 100).toFixed(0)}), 安全: ${qa.safety_level}(${(qa.safety_score * 100).toFixed(0)})`;
          setQualityInfo(info);
        }
      },
      // onDone
      (_done) => {
        setStatus("done");
      },
      // onError
      (err) => {
        setStatus("error");
        setErrorMsg(typeof err === "string" ? err : JSON.stringify(err));
      },
      // sessionId 与分类均可选，这里只传 sessionId，其他使用默认值
      sessionId
    );
  };

  const clearSession = async () => {
    try {
      await clearMedicalSession(sessionId);
      setOutput("");
      setStatus("idle");
      setErrorMsg("");
      setCitationsCount(0);
      setQualityInfo("");
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "清空失败");
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: "40px auto", padding: 16 }}>
      <h2 style={{ fontSize: 20, marginBottom: 12 }}>最简医疗流式对接示例</h2>

      <div style={{ display: "flex", gap: 12, marginBottom: 8 }}>
        <input
          style={{ flex: 1, padding: 8, border: "1px solid #ccc", borderRadius: 6 }}
          value={sessionId}
          onChange={(e) => setSessionId(e.target.value)}
          placeholder="sessionId，例如 userId:threadId"
        />
        <button onClick={clearSession} style={{ padding: "8px 12px" }}>清空会话</button>
      </div>

      <textarea
        style={{ width: "100%", height: 120, padding: 8, border: "1px solid #ccc", borderRadius: 6 }}
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="输入问题，例如：患者长期血压维持在140/90，如何管理与用药？"
      />

      <div style={{ display: "flex", gap: 12, marginTop: 10 }}>
        <button onClick={startStream} style={{ padding: "8px 12px" }}>开始流式</button>
      </div>

      <div style={{ marginTop: 20, fontSize: 14, color: "#555" }}>
        <div>状态：{status}</div>
        {qualityInfo && <div>质量评估：{qualityInfo}</div>}
        <div>引用条数：{citationsCount}</div>
      </div>

      <div style={{ marginTop: 12, whiteSpace: "pre-wrap", lineHeight: 1.6, border: "1px solid #eee", borderRadius: 6, padding: 12 }}>
        {output || "（等待输出…）"}
      </div>

      {errorMsg && (
        <div style={{ marginTop: 12, color: "#b00020" }}>错误：{errorMsg}</div>
      )}
    </div>
  );
}
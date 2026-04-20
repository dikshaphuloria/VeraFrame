"use client";

import { useCallback, useState } from "react";

interface DropZoneProps {
  onFileSelect: (file: File) => void;
  onUrlSubmit: (url: string) => void;
  isLoading: boolean;
}

const MAX_SIZE = 100 * 1024 * 1024; // 100MB

const checkFileSize = (file: File): boolean => {
  if (file.size > MAX_SIZE) {
    alert(`File too large — maximum is 100MB. Your file is ${(file.size / 1024 / 1024).toFixed(0)}MB`);
    return false;
  }
  return true;
};

export default function DropZone({ onFileSelect, onUrlSubmit, isLoading }: DropZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [url, setUrl] = useState("");
  const [tab, setTab] = useState<"file" | "url">("file");

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file && checkFileSize(file)) onFileSelect(file);
  }, [onFileSelect]);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && checkFileSize(file)) onFileSelect(file);
  };

  return (
    <div style={{
      background: "var(--bg2)",
      border: "1px solid var(--border)",
      borderRadius: "24px",
      overflow: "hidden",
    }}>

      {/* Tabs */}
      <div style={{
        display: "flex",
        borderBottom: "1px solid var(--border)",
        background: "var(--bg1)",
      }}>
        {(["file", "url"] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              flex: 1,
              padding: "14px",
              background: "transparent",
              border: "none",
              borderBottom: tab === t ? "1px solid rgba(255,255,255,0.5)" : "1px solid transparent",
              marginBottom: "-1px",
              color: tab === t ? "#fff" : "var(--text-muted)",
              fontSize: "12px",
              fontFamily: "'Instrument Sans', sans-serif",
              fontWeight: 600,
              cursor: "pointer",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              transition: "all 0.2s",
            }}
          >
            {t === "file" ? "📁  Upload File" : "🔗  URL"}
          </button>
        ))}
      </div>

      <div style={{ padding: "32px" }}>
        {tab === "file" ? (
          <div
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => !isLoading && document.getElementById("file-input")?.click()}
            className={!isDragging && !isLoading ? "dropzone-pulse" : ""}
            style={{
              border: `1px dashed ${isDragging ? "rgba(255,255,255,0.4)" : "rgba(255,255,255,0.1)"}`,
              borderRadius: "16px",
              padding: "56px 40px",
              textAlign: "center",
              cursor: isLoading ? "not-allowed" : "pointer",
              transition: "all 0.3s ease",
              background: isDragging
                ? "rgba(255,255,255,0.03)"
                : "radial-gradient(ellipse at center, rgba(255,255,255,0.02), transparent)",
              position: "relative",
              overflow: "hidden",
            }}
          >
            {/* Corner accents */}
            {!isLoading && (
              <>
                <div style={{ position: "absolute", top: 12, left: 12, width: 16, height: 16, borderTop: "1px solid rgba(255,255,255,0.2)", borderLeft: "1px solid rgba(255,255,255,0.2)", borderRadius: "2px 0 0 0" }} />
                <div style={{ position: "absolute", top: 12, right: 12, width: 16, height: 16, borderTop: "1px solid rgba(255,255,255,0.2)", borderRight: "1px solid rgba(255,255,255,0.2)", borderRadius: "0 2px 0 0" }} />
                <div style={{ position: "absolute", bottom: 12, left: 12, width: 16, height: 16, borderBottom: "1px solid rgba(255,255,255,0.2)", borderLeft: "1px solid rgba(255,255,255,0.2)", borderRadius: "0 0 0 2px" }} />
                <div style={{ position: "absolute", bottom: 12, right: 12, width: 16, height: 16, borderBottom: "1px solid rgba(255,255,255,0.2)", borderRight: "1px solid rgba(255,255,255,0.2)", borderRadius: "0 0 2px 0" }} />
              </>
            )}

            <input
              id="file-input"
              type="file"
              accept="video/*,image/*"
              style={{ display: "none" }}
              onChange={handleFileInput}
              disabled={isLoading}
            />

            {isLoading ? (
              <>
                <div style={{
                  width: "40px",
                  height: "40px",
                  border: "2px solid rgba(255,255,255,0.1)",
                  borderTop: "2px solid #fff",
                  borderRadius: "50%",
                  margin: "0 auto 20px",
                  animation: "spin 1s linear infinite",
                }} />
                <p style={{ fontSize: "16px", fontWeight: 600, marginBottom: "6px", fontFamily: "'Cabinet Grotesk', sans-serif" }}>
                  Analyzing...
                </p>
                <p style={{ fontSize: "12px", color: "var(--text-muted)", letterSpacing: "0.05em" }}>
                  This takes 15–30 seconds
                </p>
              </>
            ) : (
              <>
                <div style={{
                  fontSize: "32px",
                  marginBottom: "16px",
                  filter: "grayscale(0.3)",
                }}>
                  🎬
                </div>
                <p style={{
                  fontSize: "18px",
                  fontWeight: 800,
                  marginBottom: "8px",
                  fontFamily: "'Cabinet Grotesk', sans-serif",
                  letterSpacing: "-0.02em",
                }}>
                  Drop your video or image
                </p>
                <p style={{ fontSize: "12px", color: "var(--text-muted)", letterSpacing: "0.04em" }}>
                  mp4 · mov · avi · webm · jpg · png &nbsp;·&nbsp; max 100MB
                </p>
              </>
            )}
          </div>
        ) : (
          <div>
            <p style={{
              fontSize: "11px",
              color: "var(--text-muted)",
              marginBottom: "12px",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              fontWeight: 600,
            }}>
              YouTube or direct video URL
            </p>
            <div style={{ display: "flex", gap: "10px" }}>
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && url.trim() && onUrlSubmit(url.trim())}
                placeholder="https://youtube.com/watch?v=..."
                disabled={isLoading}
                style={{
                  flex: 1,
                  padding: "12px 16px",
                  background: "var(--bg3)",
                  border: "1px solid var(--border)",
                  borderRadius: "12px",
                  color: "#fff",
                  fontSize: "14px",
                  fontFamily: "'Instrument Sans', sans-serif",
                  outline: "none",
                  transition: "border-color 0.2s",
                }}
                onFocus={(e) => e.target.style.borderColor = "rgba(255,255,255,0.2)"}
                onBlur={(e) => e.target.style.borderColor = "rgba(255,255,255,0.06)"}
              />
              <button
                onClick={() => url.trim() && onUrlSubmit(url.trim())}
                disabled={isLoading || !url.trim()}
                style={{
                  padding: "12px 20px",
                  background: url.trim() && !isLoading ? "#fff" : "var(--bg4)",
                  color: url.trim() && !isLoading ? "#000" : "var(--text-muted)",
                  border: "1px solid var(--border)",
                  borderRadius: "12px",
                  fontSize: "13px",
                  fontWeight: 700,
                  cursor: isLoading || !url.trim() ? "not-allowed" : "pointer",
                  fontFamily: "'Instrument Sans', sans-serif",
                  transition: "all 0.2s",
                  letterSpacing: "0.02em",
                  whiteSpace: "nowrap",
                }}
              >
                Analyze →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
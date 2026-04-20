"use client";

import { AnalysisResult, TransitionResult } from "../lib/api";

interface ResultsProps {
  result: AnalysisResult;
  onReset: () => void;
}

const verdictConfig = {
  "AI Generated": {
    color: "#ff4444",
    colorDim: "rgba(255,68,68,0.6)",
    bg: "radial-gradient(ellipse at top left, rgba(255,68,68,0.08), transparent 60%)",
    border: "rgba(255,68,68,0.2)",
    glow: "0 0 60px rgba(255,68,68,0.06)",
    icon: "🤖",
    label: "AI Generated",
    message: "This content shows strong signs of AI generation",
  },
  "Possibly AI Generated": {
    color: "#ffaa00",
    colorDim: "rgba(255,170,0,0.6)",
    bg: "radial-gradient(ellipse at top left, rgba(255,170,0,0.08), transparent 60%)",
    border: "rgba(255,170,0,0.2)",
    glow: "0 0 60px rgba(255,170,0,0.06)",
    icon: "⚠️",
    label: "Possibly AI Generated",
    message: "This content has some suspicious characteristics",
  },
  "Likely Real": {
    color: "#00e676",
    colorDim: "rgba(0,230,118,0.6)",
    bg: "radial-gradient(ellipse at top left, rgba(0,230,118,0.08), transparent 60%)",
    border: "rgba(0,230,118,0.2)",
    glow: "0 0 60px rgba(0,230,118,0.06)",
    icon: "✅",
    label: "Likely Real",
    message: "This content appears to be authentic",
  },
  "Possibly Edited": {
    color: "#a78bfa",           
    colorDim: "rgba(167,139,250,0.6)",
    bg: "radial-gradient(ellipse at top left, rgba(167,139,250,0.08), transparent 60%)",
    border: "rgba(167,139,250,0.2)",
    glow: "0 0 60px rgba(167,139,250,0.06)",
    icon: "✂️",
    label: "Possibly Edited",
    message: "This content appears real but shows signs of manipulation",
  },
};

export default function Results({ result, onReset }: ResultsProps) {
  const config = verdictConfig[result.verdict];

  return (
    <div style={{ marginTop: "32px" }}>

      {/* Verdict card */}
      <div
        className="animate-fade-up-delay-1"
        style={{
          background: config.bg,
          border: `1px solid ${config.border}`,
          borderRadius: "24px",
          padding: "32px",
          marginBottom: "16px",
          boxShadow: config.glow,
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Top line accent */}
        <div style={{
          position: "absolute",
          top: 0, left: "10%", right: "10%",
          height: "1px",
          background: `linear-gradient(90deg, transparent, ${config.color}, transparent)`,
          opacity: 0.4,
        }} />

        {/* Header */}
        <div style={{ display: "flex", alignItems: "flex-start", gap: "16px", marginBottom: "28px" }}>
          <div style={{
            fontSize: "36px",
            lineHeight: 1,
            filter: "drop-shadow(0 0 12px currentColor)",
          }}>
            {config.icon}
          </div>
          <div>
            <h2 style={{
              fontSize: "26px",
              fontWeight: 900,
              color: config.color,
              fontFamily: "'Cabinet Grotesk', sans-serif",
              letterSpacing: "-0.02em",
              lineHeight: 1.1,
              marginBottom: "4px",
            }}>
              {config.label}
            </h2>
            <p style={{ fontSize: "14px", color: "var(--text-secondary)" }}>
              {config.message}
            </p>
          </div>
        </div>

        {/* Confidence bar */}
        <div style={{ marginBottom: "24px" }}>
          <div style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "10px",
          }}>
            <span style={{ fontSize: "11px", color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase", fontWeight: 600 }}>
              Confidence in verdict
            </span>
            <span style={{ fontSize: "20px", fontWeight: 900, color: config.color, fontFamily: "'Cabinet Grotesk', sans-serif" }}>
              {result.overall_confidence}%
            </span>
          </div>
          <div style={{
            height: "4px",
            background: "rgba(255,255,255,0.05)",
            borderRadius: "99px",
            overflow: "hidden",
          }}>
            <div style={{
              height: "100%",
              width: `${result.overall_confidence}%`,
              background: `linear-gradient(90deg, ${config.colorDim}, ${config.color})`,
              borderRadius: "99px",
              boxShadow: `0 0 12px ${config.color}44`,
              transition: "width 1.2s cubic-bezier(0.16, 1, 0.3, 1)",
            }} />
          </div>
        </div>

        {/* Stats */}
        <div style={{
          display: "flex",
          gap: "32px",
          paddingTop: "20px",
          borderTop: "1px solid rgba(255,255,255,0.05)",
        }}>
          {[
            { value: result.ai_frames, label: "AI frames" },
            { value: result.total_frames, label: "Total frames" },
            { value: result.artifacts_found.length, label: "Artifacts" },
          ].map(({ value, label }) => (
            <div key={label}>
              <p style={{
                fontSize: "28px",
                fontWeight: 900,
                fontFamily: "'Cabinet Grotesk', sans-serif",
                color: label === "AI frames" && value > 0 ? config.color : "#fff",
                letterSpacing: "-0.02em",
                lineHeight: 1,
                marginBottom: "4px",
              }}>
                {value}
              </p>
              <p style={{ fontSize: "11px", color: "var(--text-muted)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
                {label}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Proof frames */}
      <div className="animate-fade-up-delay-2" style={{ marginBottom: "16px" }}>
        <p style={{
          fontSize: "11px",
          fontWeight: 700,
          color: "var(--text-muted)",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          marginBottom: "12px",
          paddingLeft: "4px",
        }}>
          Proof Frames
        </p>
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gap: "12px",
        }}>
          {result.proof_frames.map((frame, i) => {
            const isAi = frame.analysis.is_ai_generated;
            return (
              <div key={i} style={{
                borderRadius: "16px",
                overflow: "hidden",
                border: `1px solid ${isAi ? "rgba(255,68,68,0.25)" : "rgba(255,255,255,0.06)"}`,
                background: "var(--bg2)",
                boxShadow: isAi ? "0 0 20px rgba(255,68,68,0.05)" : "none",
              }}>
                <div style={{ position: "relative" }}>
                  <img
                    src={`data:image/jpeg;base64,${frame.image}`}
                    alt={`Frame ${i + 1}`}
                    style={{ width: "100%", display: "block", aspectRatio: "16/10", objectFit: "cover" }}
                  />
                  {/* Badge overlay on image */}
                  <div style={{
                    position: "absolute",
                    bottom: "10px",
                    left: "10px",
                    padding: "4px 10px",
                    borderRadius: "99px",
                    fontSize: "11px",
                    fontWeight: 700,
                    fontFamily: "'Instrument Sans', sans-serif",
                    background: isAi ? "rgba(255,68,68,0.85)" : "rgba(0,230,118,0.85)",
                    color: "#fff",
                    backdropFilter: "blur(8px)",
                    letterSpacing: "0.04em",
                  }}>
                    {isAi ? "AI" : "Real"} · {frame.analysis.confidence}%
                  </div>
                </div>
                <div style={{ padding: "14px" }}>
                  <p style={{
                    fontSize: "12px",
                    color: "var(--text-secondary)",
                    lineHeight: 1.6,
                    fontStyle: "italic",
                  }}>
                    "{frame.analysis.reasoning}"
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Suspicious transitions */}
      {result.transitions && result.transitions.suspicious_count > 0 && (
        <div
          className="animate-fade-up-delay-3"
          style={{
            background: "radial-gradient(ellipse at top left, rgba(255,68,68,0.05), transparent)",
            border: "1px solid rgba(255,68,68,0.15)",
            borderRadius: "16px",
            padding: "20px",
            marginBottom: "16px",
          }}
        >
          <p style={{
            fontSize: "11px",
            fontWeight: 700,
            color: "var(--text-muted)",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            marginBottom: "14px",
          }}>
            Suspicious Transitions — {result.transitions.suspicious_count} of {result.transitions.total_analyzed} flagged
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {result.transitions.results
              .filter((t: TransitionResult) => t.is_suspicious_transition)
              .map((t: TransitionResult, i: number) => (
                <div key={i} style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                  <span style={{
                    fontSize: "10px",
                    padding: "3px 8px",
                    borderRadius: "6px",
                    background: "rgba(255,68,68,0.12)",
                    color: "#ff6b6b",
                    whiteSpace: "nowrap",
                    fontWeight: 700,
                    letterSpacing: "0.04em",
                    marginTop: "2px",
                    border: "1px solid rgba(255,68,68,0.2)",
                    flexShrink: 0,
                  }}>
                    {t.frame_pair}
                  </span>
                  <p style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                    {t.description}
                  </p>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Artifacts */}
      {result.artifacts_found.length > 0 && (
        <div
          className="animate-fade-up-delay-3"
          style={{
            background: "var(--bg2)",
            border: "1px solid var(--border)",
            borderRadius: "16px",
            padding: "20px",
            marginBottom: "16px",
          }}
        >
          <p style={{
            fontSize: "11px",
            fontWeight: 700,
            color: "var(--text-muted)",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            marginBottom: "14px",
          }}>
            Artifacts Detected
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {result.artifacts_found.map((artifact, i) => (
              <span key={i} style={{
                padding: "6px 14px",
                borderRadius: "99px",
                fontSize: "12px",
                fontFamily: "'Instrument Sans', sans-serif",
                background: "rgba(255,68,68,0.06)",
                border: "1px solid rgba(255,68,68,0.15)",
                color: "#ff8888",
                lineHeight: 1.4,
              }}>
                {artifact}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Reset button */}
      <div className="animate-fade-up-delay-4">
        <button
          onClick={onReset}
          style={{
            width: "100%",
            padding: "14px",
            borderRadius: "14px",
            border: "1px solid var(--border)",
            background: "transparent",
            color: "var(--text-secondary)",
            fontSize: "13px",
            cursor: "pointer",
            fontWeight: 600,
            fontFamily: "'Instrument Sans', sans-serif",
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            transition: "all 0.2s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = "rgba(255,255,255,0.15)";
            e.currentTarget.style.color = "#fff";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = "rgba(255,255,255,0.06)";
            e.currentTarget.style.color = "var(--text-secondary)";
          }}
        >
          Analyze Another →
        </button>
      </div>
    </div>
  );
}
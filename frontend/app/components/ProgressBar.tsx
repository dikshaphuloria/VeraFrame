"use client";

interface ProgressBarProps {
  step: string;
  message: string;
  progress: number;
}

const stepLabels: Record<string, string> = {
  uploading: "Upload",
  extracting: "Extract",
  analyzing_frame: "Frames",
  analyzing_transition: "Transitions",
  verdict: "Verdict",
  complete: "Done",
};

const steps = ["uploading", "extracting", "analyzing_frame", "analyzing_transition", "verdict"];

export default function ProgressBar({ step, message, progress }: ProgressBarProps) {
  const currentIndex = steps.indexOf(step);

  return (
    <div
      className="animate-fade-up"
      style={{
        background: "var(--bg2)",
        border: "1px solid var(--border)",
        borderRadius: "24px",
        padding: "28px 32px",
        marginTop: "16px",
      }}
    >
      {/* Step pills */}
      <div style={{
        display: "flex",
        gap: "6px",
        marginBottom: "24px",
        flexWrap: "wrap",
      }}>
        {steps.map((s, i) => {
          const isDone = i < currentIndex;
          const isActive = i === currentIndex;
          return (
            <div key={s} style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "5px 12px",
              borderRadius: "99px",
              fontSize: "11px",
              fontWeight: 600,
              letterSpacing: "0.06em",
              fontFamily: "'Instrument Sans', sans-serif",
              transition: "all 0.3s",
              background: isDone
                ? "rgba(255,255,255,0.08)"
                : isActive
                  ? "rgba(255,255,255,0.1)"
                  : "transparent",
              border: `1px solid ${isDone || isActive ? "rgba(255,255,255,0.15)" : "rgba(255,255,255,0.04)"}`,
              color: isDone
                ? "var(--text-secondary)"
                : isActive
                  ? "#fff"
                  : "var(--text-muted)",
            }}>
              {isDone ? (
                <span style={{ color: "var(--green)", fontSize: "10px" }}>✓</span>
              ) : isActive ? (
                <div style={{
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  background: "#fff",
                  animation: "ping 1s ease-in-out infinite",
                  flexShrink: 0,
                }} />
              ) : (
                <div style={{
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  background: "var(--text-muted)",
                  flexShrink: 0,
                }} />
              )}
              {stepLabels[s]}
            </div>
          );
        })}
      </div>

      {/* Progress bar */}
      <div style={{
        height: "2px",
        background: "rgba(255,255,255,0.05)",
        borderRadius: "99px",
        overflow: "hidden",
        marginBottom: "16px",
      }}>
        <div style={{
          height: "100%",
          width: `${progress}%`,
          background: "linear-gradient(90deg, rgba(255,255,255,0.4), #fff)",
          borderRadius: "99px",
          transition: "width 0.5s cubic-bezier(0.16, 1, 0.3, 1)",
          boxShadow: "0 0 12px rgba(255,255,255,0.3)",
        }} />
      </div>

      {/* Message + percentage */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <p style={{ fontSize: "13px", color: "var(--text-secondary)", fontFamily: "'Instrument Sans', sans-serif" }}>
          {message}
        </p>
        <p style={{
          fontSize: "13px",
          color: "#fff",
          fontWeight: 600,
          fontFamily: "'Cabinet Grotesk', sans-serif",
          letterSpacing: "0.02em",
        }}>
          {progress}%
        </p>
      </div>
    </div>
  );
}
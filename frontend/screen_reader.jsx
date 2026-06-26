// ============ Màn Đọc paper (PDF + Hỏi đáp) ============

// ---- mock PDF: dòng văn bản giả lập để gợi hình một trang paper ----
function TextLines({ count = 6, lead = false }) {
  const widths = ["100%", "97%", "99%", "94%", "100%", "96%", "92%", "98%", "88%"];
  return (
    <div style={{ display: "grid", gap: 7 }}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} style={{
          height: 6.5, borderRadius: 3,
          width: i === count - 1 ? "62%" : widths[(i + (lead ? 1 : 0)) % widths.length],
          background: "var(--surface-3)",
        }} />
      ))}
    </div>
  );
}

function PdfPage({ children, n, total }) {
  return (
    <div style={{
      width: 612, maxWidth: "100%", background: "white", margin: "0 auto",
      boxShadow: "0 1px 2px oklch(0.4 0.01 75 / .08), 0 10px 30px oklch(0.4 0.01 75 / .12)",
      border: "1px solid var(--border)", borderRadius: 3, position: "relative",
      padding: "52px 54px 60px",
    }}>
      {children}
      <div className="mono" style={{ position: "absolute", bottom: 18, left: 0, right: 0, textAlign: "center", fontSize: 10, color: "var(--ink-4)" }}>
        {n} / {total}
      </div>
    </div>
  );
}

function SectionHead({ children }) {
  return <div className="serif" style={{ fontSize: 12.5, fontWeight: 600, color: "var(--ink)", margin: "0 0 9px" }}>{children}</div>;
}

function PdfDocument({ paper }) {
  const TOTAL = 3;
  return (
    <div style={{ display: "grid", gap: 22, paddingBottom: 8 }}>
      {/* ---- trang 1 ---- */}
      <PdfPage n={1} total={TOTAL}>
        <div className="mono" style={{ fontSize: 9.5, color: "var(--ink-4)", letterSpacing: ".08em", textAlign: "center", marginBottom: 18, textTransform: "uppercase" }}>
          {window.CONFERENCES.find((c) => c.id === paper.conf)?.full || paper.conf} · {paper.year}
        </div>
        <h1 className="serif" style={{ fontSize: 19, lineHeight: 1.28, fontWeight: 600, textAlign: "center", margin: "0 0 13px", color: "var(--ink)", letterSpacing: "-.01em" }}>
          {paper.titleEn}
        </h1>
        <div style={{ fontSize: 10.5, color: "var(--ink-2)", textAlign: "center", margin: "0 0 26px", lineHeight: 1.6 }}>
          {paper.authors.join("   ·   ")}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 26 }}>
          <div>
            <SectionHead>Abstract</SectionHead>
            <p style={{ fontSize: 9.5, lineHeight: 1.62, color: "var(--ink)", margin: "0 0 14px", textAlign: "justify" }}>
              {paper.abstractEn}
            </p>
            <SectionHead>1.&nbsp;&nbsp;Introduction</SectionHead>
            <TextLines count={9} />
          </div>
          <div>
            <TextLines count={6} lead />
            <div style={{ height: 12 }} />
            <SectionHead>2.&nbsp;&nbsp;Related Work</SectionHead>
            <TextLines count={11} />
          </div>
        </div>
      </PdfPage>

      {/* ---- trang 2 ---- */}
      <PdfPage n={2} total={TOTAL}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 26 }}>
          <div>
            <SectionHead>3.&nbsp;&nbsp;Method</SectionHead>
            <TextLines count={7} />
            <div className="fig-ph" style={{ height: 120, margin: "14px 0", fontSize: 9.5 }}>
              Figure 1 · overview
            </div>
            <TextLines count={6} lead />
          </div>
          <div>
            <TextLines count={10} />
            <div style={{ height: 12 }} />
            <SectionHead>3.1&nbsp;&nbsp;Architecture</SectionHead>
            <TextLines count={8} lead />
          </div>
        </div>
      </PdfPage>

      {/* ---- trang 3 ---- */}
      <PdfPage n={3} total={TOTAL}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 26 }}>
          <div>
            <SectionHead>4.&nbsp;&nbsp;Experiments</SectionHead>
            <TextLines count={6} />
            <div style={{ height: 96, margin: "14px 0", border: "1px solid var(--border)", borderRadius: 4, display: "grid", gridTemplateRows: "auto 1fr", overflow: "hidden" }}>
              <div className="mono" style={{ fontSize: 8.5, color: "var(--ink-3)", borderBottom: "1px solid var(--border)", padding: "5px 8px", background: "var(--surface-2)" }}>Table 1 · Quantitative results</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 1, background: "var(--border)", padding: 1 }}>
                {Array.from({ length: 9 }).map((_, i) => (
                  <div key={i} style={{ background: "white", display: "grid", placeItems: "center" }}>
                    <div style={{ height: 5, width: "52%", borderRadius: 2, background: i < 3 ? "var(--ink-4)" : "var(--surface-3)" }} />
                  </div>
                ))}
              </div>
            </div>
            <TextLines count={5} lead />
          </div>
          <div>
            <SectionHead>5.&nbsp;&nbsp;Conclusion</SectionHead>
            <TextLines count={7} />
            <div style={{ height: 12 }} />
            <SectionHead>References</SectionHead>
            <TextLines count={12} lead />
          </div>
        </div>
      </PdfPage>
    </div>
  );
}

// ---- sinh câu trả lời mô phỏng từ nội dung paper ----
function splitSentences(t) {
  return (t || "").split(/(?<=[.。])\s+/).map((s) => s.trim()).filter(Boolean);
}
function pickResultSentence(sents) {
  return sents.find((s) => /\d|%|giảm|tăng|vượt|cải thiện|FID|PSNR|Dice|AUC/i.test(s)) || sents[sents.length - 1];
}

function answerFor(paper, q) {
  const s = splitSentences(paper.abstractVi);
  const t = q.toLowerCase();
  const kw = paper.keywords.slice(0, 3).join(", ");

  if (/đóng góp|contribution|mới|novel|chính là gì|điểm chính/.test(t))
    return { text: `Đóng góp chính: ${s[0]} Các khái niệm cốt lõi xoay quanh ${kw}.`, page: 1 };

  if (/phương pháp|method|cách|kiến trúc|architecture|hoạt động|làm thế nào/.test(t))
    return { text: `Về phương pháp: ${s[1] || s[0]} Chi tiết kỹ thuật được trình bày ở phần Method.`, page: 2 };

  if (/kết quả|result|hiệu quả|đánh giá|benchmark|số liệu|so sánh|sota|state.?of/.test(t))
    return { text: `Kết quả thực nghiệm: ${pickResultSentence(s)} Xem Bảng 1 và Mục Experiments để biết chi tiết.`, page: 3 };

  if (/hạn chế|limitation|nhược|yếu|future|hướng|tương lai|tiếp theo/.test(t))
    return { text: `Paper tập trung vào ${kw}. Các tác giả lưu ý hướng mở rộng tự nhiên là tổng quát hóa sang nhiều miền dữ liệu hơn và kiểm chứng trên quy mô lớn — phần này được nêu ở Mục Conclusion.`, page: 3 };

  if (/tóm tắt|summary|về gì|nói gì|tổng quan|overview/.test(t))
    return { text: `Tóm tắt nhanh: ${s[0]} ${s[1] || ""}`.trim(), page: 1 };

  if (/dữ liệu|dataset|tập|benchmark dùng/.test(t))
    return { text: `Bộ dữ liệu và thiết lập thực nghiệm được mô tả trong Mục Experiments. Tóm tắt liên quan: ${pickResultSentence(s)}`, page: 3 };

  // fallback
  return { text: `Dựa trên nội dung paper: ${s[0]} Bạn có thể hỏi cụ thể hơn về phương pháp, kết quả hoặc đóng góp của paper.`, page: 1 };
}

const SUGGESTED = [
  "Đóng góp chính của paper là gì?",
  "Phương pháp hoạt động như thế nào?",
  "Kết quả thực nghiệm ra sao?",
  "Hạn chế và hướng phát triển?",
];

function ChatPanel({ paper }) {
  const [messages, setMessages] = React.useState([]);
  const [input, setInput] = React.useState("");
  const [typing, setTyping] = React.useState(false);
  const scrollRef = React.useRef(null);
  const taRef = React.useRef(null);

  // reset hội thoại khi đổi paper
  React.useEffect(() => { setMessages([]); setTyping(false); setInput(""); }, [paper.id]);

  React.useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, typing]);

  const send = (text) => {
    const q = (text ?? input).trim();
    if (!q || typing) return;
    setMessages((m) => [...m, { role: "user", text: q }]);
    setInput("");
    if (taRef.current) taRef.current.style.height = "auto";
    setTyping(true);
    const a = answerFor(paper, q);
    setTimeout(() => {
      setTyping(false);
      setMessages((m) => [...m, { role: "ai", text: a.text, page: a.page }]);
    }, 650 + Math.random() * 500);
  };

  const empty = messages.length === 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "var(--surface)" }}>
      {/* header */}
      <div style={{ flex: "none", padding: "14px 18px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 11 }}>
        <span style={{ width: 30, height: 30, borderRadius: 8, background: "var(--accent-soft)", border: "1px solid var(--accent-border)", display: "grid", placeItems: "center", color: "var(--accent)", flex: "none" }}>
          <Icon name="spark" size={16} />
        </span>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)" }}>Hỏi đáp về paper</div>
          <div className="muted" style={{ fontSize: 11.5 }}>Trả lời dựa trên nội dung bài báo</div>
        </div>
      </div>

      {/* messages */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: "20px 18px", display: "flex", flexDirection: "column", gap: 16 }}>
        {empty && (
          <div style={{ margin: "auto 0", paddingBottom: 8 }}>
            <div className="serif" style={{ fontSize: 16.5, color: "var(--ink)", lineHeight: 1.35, marginBottom: 6 }}>
              Hỏi bất cứ điều gì về paper này
            </div>
            <p className="muted" style={{ fontSize: 13, margin: "0 0 18px", lineHeight: 1.5 }}>
              Trợ lý đọc tóm tắt, phương pháp và kết quả để trả lời. Thử một câu hỏi gợi ý:
            </p>
            <div style={{ display: "grid", gap: 8 }}>
              {SUGGESTED.map((s) => (
                <button key={s} onClick={() => send(s)} style={{
                  textAlign: "left", padding: "11px 13px", borderRadius: "var(--r)",
                  border: "1px solid var(--border-strong)", background: "var(--surface)",
                  fontSize: 13.5, color: "var(--ink)", display: "flex", alignItems: "center", gap: 10,
                  transition: "all .14s",
                }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--accent-border)"; e.currentTarget.style.background = "var(--accent-soft)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border-strong)"; e.currentTarget.style.background = "var(--surface)"; }}>
                  <Icon name="spark" size={14} style={{ color: "var(--accent)", flex: "none" }} />
                  <span style={{ flex: 1 }}>{s}</span>
                  <Icon name="arrowR" size={14} style={{ color: "var(--ink-4)", flex: "none" }} />
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} style={{ alignSelf: "flex-end", maxWidth: "86%", background: "var(--ink)", color: "var(--bg)", padding: "9px 13px", borderRadius: "13px 13px 4px 13px", fontSize: 13.5, lineHeight: 1.5 }}>
              {m.text}
            </div>
          ) : (
            <div key={i} style={{ alignSelf: "flex-start", maxWidth: "92%", display: "flex", gap: 9 }}>
              <span style={{ width: 24, height: 24, borderRadius: 6, background: "var(--accent-soft)", border: "1px solid var(--accent-border)", display: "grid", placeItems: "center", color: "var(--accent)", flex: "none", marginTop: 1 }}>
                <Icon name="spark" size={13} />
              </span>
              <div>
                <div style={{ background: "var(--surface-2)", border: "1px solid var(--border)", padding: "10px 13px", borderRadius: "4px 13px 13px 13px", fontSize: 13.5, lineHeight: 1.6, color: "var(--ink)" }}>
                  {m.text}
                </div>
                {m.page && (
                  <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 6, display: "inline-flex", alignItems: "center", gap: 5 }}>
                    <Icon name="doc" size={12} /> Nguồn · trang {m.page}
                  </div>
                )}
              </div>
            </div>
          )
        )}

        {typing && (
          <div style={{ alignSelf: "flex-start", display: "flex", gap: 9, alignItems: "center" }}>
            <span style={{ width: 24, height: 24, borderRadius: 6, background: "var(--accent-soft)", border: "1px solid var(--accent-border)", display: "grid", placeItems: "center", color: "var(--accent)", flex: "none" }}>
              <Icon name="spark" size={13} />
            </span>
            <div style={{ display: "flex", gap: 4, padding: "11px 13px", background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 13 }}>
              {[0, 1, 2].map((i) => (
                <span key={i} style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--ink-4)", animation: "dotPulse 1.1s infinite", animationDelay: `${i * 0.16}s` }} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* input */}
      <div style={{ flex: "none", padding: "12px 14px 14px", borderTop: "1px solid var(--border)", background: "var(--surface)" }}>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 8, border: "1px solid var(--border-strong)", borderRadius: 12, padding: "7px 8px 7px 13px", background: "var(--surface)", boxShadow: "var(--shadow-sm)" }}>
          <textarea
            ref={taRef}
            rows={1}
            value={input}
            placeholder="Nhập câu hỏi về paper…"
            onChange={(e) => { setInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 110) + "px"; }}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            style={{ flex: 1, border: 0, outline: "none", resize: "none", background: "transparent", fontSize: 13.5, lineHeight: 1.5, color: "var(--ink)", maxHeight: 110, padding: "4px 0" }}
          />
          <button
            onClick={() => send()}
            disabled={!input.trim() || typing}
            className="btn btn-accent btn-sm"
            style={{ width: 34, height: 34, padding: 0, borderRadius: 9, flex: "none", opacity: !input.trim() || typing ? 0.4 : 1 }}
            title="Gửi"
          >
            <Icon name="arrowR" size={16} />
          </button>
        </div>
        <div className="muted" style={{ fontSize: 10.5, textAlign: "center", marginTop: 7 }}>
          Câu trả lời do AI tạo dựa trên nội dung paper — hãy đối chiếu với bản gốc.
        </div>
      </div>
    </div>
  );
}

function ReaderScreen({ paper, onBack, saved, onToggleSave }) {
  const [zoom, setZoom] = React.useState(1);

  return (
    <div className="fade-in" style={{ flex: 1, display: "flex", flexDirection: "column", height: "calc(100vh - 60px)", minHeight: 0, overflow: "hidden" }}>
      {/* sub-header */}
      <div style={{ flex: "none", height: 50, borderBottom: "1px solid var(--border)", background: "var(--surface)", display: "flex", alignItems: "center", gap: 14, padding: "0 16px" }}>
        <button className="btn btn-ghost btn-sm" onClick={onBack} style={{ paddingLeft: 8, flex: "none" }}>
          <Icon name="arrowL" size={15} /> Chi tiết
        </button>
        <div style={{ width: 1, height: 22, background: "var(--border)", flex: "none" }} />
        <ConfTag conf={paper.conf} year={paper.year} />
        <span className="serif" style={{ fontSize: 14.5, fontWeight: 500, color: "var(--ink)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", minWidth: 0 }}>
          {paper.titleEn}
        </span>
        <div style={{ flex: 1 }} />
        <SaveBtn saved={saved} onClick={onToggleSave} />
        <button className="btn btn-accent btn-sm" style={{ flex: "none" }}>
          <Icon name="download" size={14} /> Tải PDF
        </button>
      </div>

      {/* split */}
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "minmax(0, 1.32fr) minmax(380px, 1fr)", minHeight: 0 }}>
        {/* left: PDF */}
        <div style={{ display: "flex", flexDirection: "column", minWidth: 0, minHeight: 0, borderRight: "1px solid var(--border)", background: "var(--surface-3)" }}>
          {/* pdf toolbar */}
          <div style={{ flex: "none", height: 42, borderBottom: "1px solid var(--border)", background: "var(--surface)", display: "flex", alignItems: "center", gap: 10, padding: "0 14px" }}>
            <Icon name="doc" size={14} style={{ color: "var(--ink-3)" }} />
            <span className="mono" style={{ fontSize: 11.5, color: "var(--ink-2)" }}>paper.pdf</span>
            <span className="muted mono" style={{ fontSize: 11.5 }}>· 3 trang</span>
            <div style={{ flex: 1 }} />
            <div style={{ display: "flex", alignItems: "center", gap: 2, border: "1px solid var(--border-strong)", borderRadius: 7, background: "var(--surface)", padding: 2 }}>
              <button className="btn btn-ghost btn-sm" style={{ width: 28, height: 26, padding: 0 }} onClick={() => setZoom((z) => Math.max(0.7, +(z - 0.1).toFixed(2)))} title="Thu nhỏ">
                <span style={{ fontSize: 16, lineHeight: 1 }}>−</span>
              </button>
              <span className="mono" style={{ fontSize: 11.5, color: "var(--ink-2)", minWidth: 38, textAlign: "center" }}>{Math.round(zoom * 100)}%</span>
              <button className="btn btn-ghost btn-sm" style={{ width: 28, height: 26, padding: 0 }} onClick={() => setZoom((z) => Math.min(1.6, +(z + 0.1).toFixed(2)))} title="Phóng to">
                <span style={{ fontSize: 15, lineHeight: 1 }}>+</span>
              </button>
            </div>
          </div>
          {/* pdf scroll */}
          <div style={{ flex: 1, overflowY: "auto", padding: "26px 20px", minHeight: 0 }}>
            <div style={{ transform: `scale(${zoom})`, transformOrigin: "top center", transition: "transform .15s" }}>
              <PdfDocument paper={paper} />
            </div>
          </div>
        </div>

        {/* right: chat */}
        <div style={{ minWidth: 0, minHeight: 0 }}>
          <ChatPanel paper={paper} />
        </div>
      </div>
    </div>
  );
}

// keyframes cho typing dots (chèn 1 lần)
if (!document.getElementById("reader-kf")) {
  const st = document.createElement("style");
  st.id = "reader-kf";
  st.textContent = "@keyframes dotPulse{0%,60%,100%{opacity:.25;transform:translateY(0)}30%{opacity:1;transform:translateY(-3px)}}";
  document.head.appendChild(st);
}

Object.assign(window, { ReaderScreen });

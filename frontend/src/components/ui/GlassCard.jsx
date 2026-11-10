// Painel de vidro fumê: base de todos os cards
export default function GlassCard({ as: Tag = "section", className = "", children, ...props }) {
  return (
    <Tag
      className={`rounded-2xl border border-kindra-borda/30 bg-kindra-painel/40 p-5
                  shadow-xl shadow-black/20 backdrop-blur-xl ${className}`}
      {...props}
    >
      {children}
    </Tag>
  );
}

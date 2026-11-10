import GlassCard from "../ui/GlassCard.jsx";

export default function KpiCard({ rotulo, valor, destaque = false }) {
  return (
    <GlassCard as="article" className={destaque ? "border-kindra-acento/60" : ""}>
      <p className="text-xs font-medium uppercase tracking-wider text-kindra-label">{rotulo}</p>
      <p
        className={`mt-2 text-2xl font-semibold ${destaque ? "text-kindra-acento" : "text-white"}`}
      >
        {valor}
      </p>
    </GlassCard>
  );
}

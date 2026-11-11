import Card from "./Card.jsx";

export default function Kpi({ rotulo, valor, detalhe, destaque = false }) {
  return (
    <Card as="article" className={`p-5 ${destaque ? "border-sandro-acento/50" : ""}`}>
      <p className="text-xs font-medium uppercase tracking-wider text-sandro-label">{rotulo}</p>
      <p className={`mt-2 text-2xl font-semibold tabular-nums ${destaque ? "text-sandro-acento" : "text-white"}`}>
        {valor}
      </p>
      {detalhe && <p className="mt-1 text-xs text-sandro-label">{detalhe}</p>}
    </Card>
  );
}

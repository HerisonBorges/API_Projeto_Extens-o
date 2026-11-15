import Card from "./Card.jsx";

/**
 * Indicador. Com `href`, o card inteiro vira um link para a tela com os dados
 * (navegável por teclado, com foco visível e "Ver detalhes" para quem lê a tela).
 */
export default function Kpi({ rotulo, valor, detalhe, destaque = false, href, acao = "Ver detalhes" }) {
  const conteudo = (
    <>
      <p className="text-xs font-medium uppercase tracking-wider text-sandro-label">{rotulo}</p>
      <p className={`mt-2 text-2xl font-semibold tabular-nums ${destaque ? "text-sandro-acento" : "text-white"}`}>
        {valor}
      </p>
      {detalhe && <p className="mt-1 text-xs text-sandro-label">{detalhe}</p>}
      {href && (
        <p className="mt-3 text-xs font-medium text-sandro-acento">
          {acao} <span aria-hidden="true" className="inline-block transition group-hover:translate-x-1">→</span>
        </p>
      )}
    </>
  );

  if (!href) {
    return <Card as="article" className={`p-5 ${destaque ? "border-sandro-acento/50" : ""}`}>{conteudo}</Card>;
  }

  return (
    <a
      href={href}
      className="group block rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sandro-acento
                 focus-visible:ring-offset-2 focus-visible:ring-offset-sandro-fundo"
    >
      <Card as="article"
            className={`h-full p-5 transition group-hover:-translate-y-0.5 group-hover:border-sandro-acento/70
                        group-hover:shadow-lg group-hover:shadow-sandro-acento/10
                        ${destaque ? "border-sandro-acento/50" : ""}`}>
        {conteudo}
      </Card>
    </a>
  );
}

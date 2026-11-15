"""PDF do relatório de faturamento com a identidade visual do SANDRO CRM.

Recebe o dicionário de routes.relatorios.calcular_relatorio, sem consultar o
banco: os números do PDF são os mesmos da tela.

Segurança: títulos de oportunidade e nomes de cliente vêm do usuário. O
Paragraph do reportlab interpreta marcação (<b>, <font>, <a href>...), então
TODO texto vindo do banco passa por escape() antes de entrar num Paragraph.
"""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as canvas_mod
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Paleta da marca
FUNDO = colors.HexColor("#05161A")
PAINEL = colors.HexColor("#072E33")
BORDA = colors.HexColor("#0C7075")
ACENTO = colors.HexColor("#0F969C")
ROTULO = colors.HexColor("#6DA5C0")
AZUL = colors.HexColor("#204C94")
AZUL_CLARO = colors.HexColor("#4A68D0")
# Corpo claro: o PDF é para imprimir e ler, não para tela escura
TEXTO = colors.HexColor("#0B2A30")
TEXTO_SUAVE = colors.HexColor("#4B6B78")
LINHA_ZEBRA = colors.HexColor("#EEF6F7")

LARGURA, ALTURA = A4
MARGEM = 16 * mm
ALTURA_CABECALHO = 34 * mm

NOME_PERIODO = {
    "mes": "Mês atual",
    "trimestre": "Trimestre atual",
    "ano": "Ano atual",
    "total": "Todo o histórico",
}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def moeda(valor):
    texto = f"{float(valor or 0):,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def percentual(valor):
    return f"{float(valor or 0):.1f}%".replace(".", ",")


def mes_curto(ano_mes):
    ano, mes = ano_mes.split("-")
    return f"{MESES[int(mes) - 1]}/{ano[2:]}"


# ---------------------------------------------------------------------------
# Marca
# ---------------------------------------------------------------------------

def desenhar_simbolo(c, x, y, tamanho):
    """Símbolo do SANDRO CRM a partir do viewBox 64x64 do Logo.jsx.

    (x, y) = canto inferior esquerdo. Usa coordenadas do SVG (y para baixo).
    """
    k = 0.5523 * 9  # constante da aproximação de arco por Bézier, raio 9
    c.saveState()
    c.translate(x, y + tamanho)
    escala = tamanho / 64
    c.scale(escala, -escala)
    c.setLineCap(1)
    c.setLineJoin(1)

    # Nós de conexão
    c.setStrokeColor(AZUL_CLARO)
    c.setLineWidth(1.6)
    for y0, x1 in ((21, 16), (29, 15), (37, 15)):
        c.line(7 if y0 != 29 else 4.5, y0, x1, y0)
    for cx, cy in ((5, 21), (2.6, 29), (5, 37)):
        c.circle(cx, cy, 1.9, stroke=1, fill=0)

    # "S"
    p = c.beginPath()
    p.moveTo(45, 14)
    p.lineTo(27, 14)
    p.curveTo(27 - k, 14, 18, 23 - k, 18, 23)
    p.curveTo(18, 23 + k, 27 - k, 32, 27, 32)
    p.lineTo(38, 32)
    p.curveTo(38 + k, 32, 47, 41 - k, 47, 41)
    p.curveTo(47, 41 + k, 38 + k, 50, 38, 50)
    p.lineTo(18, 50)
    c.setStrokeColor(AZUL_CLARO)
    c.setLineWidth(7)
    c.drawPath(p, stroke=1, fill=0)

    # Seta de crescimento
    c.setStrokeColor(ACENTO)
    c.setLineWidth(3.4)
    c.line(41, 24, 57, 8)
    seta = c.beginPath()
    seta.moveTo(48, 7.5)
    seta.lineTo(57.5, 7.5)
    seta.lineTo(57.5, 17)
    c.drawPath(seta, stroke=1, fill=0)

    # Barras
    c.setFillColor(ACENTO)
    for bx, by, bh in ((27, 41, 4.5), (32, 38.5, 7), (37, 36, 9.5)):
        c.roundRect(bx, by, 3, bh, 1, stroke=0, fill=1)

    c.restoreState()


def desenhar_cabecalho(c, dados_doc):
    c.saveState()
    c.setFillColor(FUNDO)
    c.rect(0, ALTURA - ALTURA_CABECALHO, LARGURA, ALTURA_CABECALHO, stroke=0, fill=1)
    c.setFillColor(ACENTO)
    c.rect(0, ALTURA - ALTURA_CABECALHO - 1.2 * mm, LARGURA, 1.2 * mm, stroke=0, fill=1)

    topo = ALTURA - ALTURA_CABECALHO
    desenhar_simbolo(c, MARGEM, topo + 6 * mm, 22 * mm)

    x_texto = MARGEM + 26 * mm
    c.setStrokeColor(BORDA)
    c.setLineWidth(0.6)
    c.line(x_texto - 2.5 * mm, topo + 7 * mm, x_texto - 2.5 * mm, topo + 27 * mm)

    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(colors.white)
    c.drawString(x_texto, topo + 17 * mm, "SANDRO ")
    c.setFillColor(ACENTO)
    c.drawString(x_texto + c.stringWidth("SANDRO ", "Helvetica-Bold", 22), topo + 17 * mm, "CRM")
    c.setFont("Helvetica", 7.5)
    c.setFillColor(ROTULO)
    c.drawString(x_texto, topo + 11 * mm, "O  P O D E R   D A   C O N E X Ã O")

    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.white)
    c.drawRightString(LARGURA - MARGEM, topo + 19 * mm, "Relatório de Faturamento")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(ROTULO)
    c.drawRightString(LARGURA - MARGEM, topo + 13 * mm, dados_doc["empresa"])
    c.restoreState()


class CanvasNumerado(canvas_mod.Canvas):
    """Canvas que desenha cabeçalho e rodapé com 'Página X de Y'."""

    dados_doc = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._paginas = []

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            desenhar_cabecalho(self, self.dados_doc)
            self._rodape(total)
            super().showPage()
        super().save()

    def _rodape(self, total):
        self.saveState()
        self.setStrokeColor(ACENTO)
        self.setLineWidth(0.8)
        self.line(MARGEM, 14 * mm, LARGURA - MARGEM, 14 * mm)
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(TEXTO)
        self.drawString(MARGEM, 9.5 * mm, "SANDRO CRM")
        self.setFont("Helvetica", 8)
        self.setFillColor(TEXTO_SUAVE)
        self.drawString(MARGEM + self.stringWidth("SANDRO CRM  ", "Helvetica-Bold", 8), 9.5 * mm,
                        "· O poder da conexão · Documento confidencial da empresa")
        self.drawRightString(LARGURA - MARGEM, 9.5 * mm, f"Página {self._pageNumber} de {total}")
        self.restoreState()


# ---------------------------------------------------------------------------
# Conteúdo
# ---------------------------------------------------------------------------

ESTILO_TEXTO = ParagraphStyle("texto", fontName="Helvetica", fontSize=9, leading=12, textColor=TEXTO)
ESTILO_SUAVE = ParagraphStyle("suave", parent=ESTILO_TEXTO, textColor=TEXTO_SUAVE, fontSize=8.5)
ESTILO_SECAO = ParagraphStyle("secao", fontName="Helvetica-Bold", fontSize=11.5, leading=15,
                              textColor=TEXTO, spaceBefore=4, spaceAfter=6)
ESTILO_CELULA = ParagraphStyle("celula", parent=ESTILO_TEXTO, fontSize=8.5, leading=11)
ESTILO_CELULA_DIR = ParagraphStyle("celula_dir", parent=ESTILO_CELULA, alignment=TA_RIGHT)


def _bloco_informacoes(dados_doc, relatorio):
    linhas = [
        ["Empresa", dados_doc["empresa"], "Gerado em", dados_doc["gerado_em"]],
        ["Período", dados_doc["periodo_texto"], "Gerado por", dados_doc["usuario"]],
    ]
    tabela = Table(
        [[Paragraph(escape(str(v)), ESTILO_SUAVE if i % 2 == 0 else ESTILO_TEXTO)
          for i, v in enumerate(linha)] for linha in linhas],
        colWidths=[22 * mm, 64 * mm, 24 * mm, None],
    )
    tabela.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return tabela


def _indicadores(relatorio):
    itens = [
        ("FATURAMENTO", moeda(relatorio["receita_total"]), True),
        ("NEGÓCIOS FECHADOS", str(relatorio["vendas_fechadas"]), False),
        ("TICKET MÉDIO", moeda(relatorio["ticket_medio"]), False),
        ("TAXA DE CONVERSÃO", percentual(relatorio["taxa_conversao"]), False),
    ]
    celulas = []
    for rotulo, valor, destaque in itens:
        celulas.append([
            Paragraph(rotulo, ParagraphStyle("k_rot", fontName="Helvetica-Bold", fontSize=7,
                                             leading=9, textColor=TEXTO_SUAVE)),
            Paragraph(escape(valor), ParagraphStyle("k_val", fontName="Helvetica-Bold", fontSize=14,
                                                    leading=18, textColor=ACENTO if destaque else TEXTO)),
        ])
    largura = (LARGURA - 2 * MARGEM - 3 * 4 * mm) / 4
    tabela = Table([celulas], colWidths=[largura] * 4, spaceBefore=6)
    estilo = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (0, 0), 1.2, ACENTO),
        ("LINEBEFORE", (1, 0), (-1, 0), 0, colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]
    for i in range(1, 4):
        estilo.append(("BOX", (i, 0), (i, 0), 0.6, colors.HexColor("#B9D7DC")))
    tabela.setStyle(TableStyle(estilo))
    return tabela


def _grafico_mensal(relatorio):
    serie = relatorio["serie_mensal"]
    valores = [m["receita"] for m in serie]
    largura, altura = LARGURA - 2 * MARGEM, 58 * mm

    desenho = Drawing(largura, altura)
    grafico = VerticalBarChart()
    grafico.x, grafico.y = 14 * mm, 8 * mm
    grafico.width, grafico.height = largura - 18 * mm, altura - 14 * mm
    grafico.data = [valores]
    grafico.barWidth = 6
    grafico.groupSpacing = 6
    grafico.bars[0].fillColor = ACENTO
    grafico.bars[0].strokeColor = None
    grafico.valueAxis.valueMin = 0
    grafico.valueAxis.valueMax = max(max(valores, default=0) * 1.15, 100)
    grafico.valueAxis.labels.fontName = "Helvetica"
    grafico.valueAxis.labels.fontSize = 6.5
    grafico.valueAxis.labels.fillColor = TEXTO_SUAVE
    grafico.valueAxis.labelTextFormat = lambda v: moeda(v).replace(",00", "")
    grafico.valueAxis.strokeColor = colors.HexColor("#B9D7DC")
    grafico.valueAxis.visibleGrid = True
    grafico.valueAxis.gridStrokeColor = colors.HexColor("#E3EEF0")
    grafico.categoryAxis.categoryNames = [mes_curto(m["mes"]) for m in serie]
    grafico.categoryAxis.labels.fontName = "Helvetica"
    grafico.categoryAxis.labels.fontSize = 6.5
    grafico.categoryAxis.labels.fillColor = TEXTO_SUAVE
    grafico.categoryAxis.strokeColor = colors.HexColor("#B9D7DC")
    desenho.add(grafico)

    if not any(valores):
        desenho.add(String(largura / 2, altura / 2, "Sem faturamento nos últimos 12 meses",
                           fontName="Helvetica", fontSize=8, fillColor=TEXTO_SUAVE, textAnchor="middle"))
    return desenho


def _tabela_vendas(relatorio):
    vendas = relatorio["vendas"]
    cabecalho = ["Data", "Oportunidade", "Cliente", "Valor"]
    cab = ParagraphStyle("cab", parent=ESTILO_CELULA, fontName="Helvetica-Bold", textColor=colors.white)
    cab_dir = ParagraphStyle("cab_dir", parent=cab, alignment=TA_RIGHT)
    linhas = [[Paragraph(t, cab_dir if t == "Valor" else cab) for t in cabecalho]]
    for v in vendas:
        linhas.append([
            Paragraph(escape(v.get("fechado_em_local") or "—"), ESTILO_CELULA),
            Paragraph(escape(v["titulo"] or "—"), ESTILO_CELULA),
            Paragraph(escape(v["cliente"] or "Cliente removido"), ESTILO_CELULA),
            Paragraph(escape(moeda(v["valor"])), ESTILO_CELULA_DIR),
        ])
    linhas.append([
        Paragraph("<b>Total</b>", ESTILO_CELULA), "",
        Paragraph(f"{len(vendas)} {'venda' if len(vendas) == 1 else 'vendas'}", ESTILO_CELULA),
        Paragraph(f"<b>{escape(moeda(relatorio['receita_total']))}</b>", ESTILO_CELULA_DIR),
    ])

    tabela = Table(linhas, colWidths=[22 * mm, None, 52 * mm, 30 * mm], repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), PAINEL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("LINEBELOW", (0, 0), (-1, 0), 1, ACENTO),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, ACENTO),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(linhas) - 1):
        if i % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), LINHA_ZEBRA))
    tabela.setStyle(TableStyle(estilo))
    return tabela


def gerar_pdf_faturamento(relatorio, empresa, usuario, gerado_em):
    """Retorna os bytes do PDF.

    relatorio: saída de calcular_relatorio. gerado_em: texto já no fuso da empresa.
    """
    inicio = relatorio.get("inicio_periodo_local")
    periodo_texto = NOME_PERIODO.get(relatorio["periodo"], relatorio["periodo"])
    if inicio:
        periodo_texto += f" (desde {inicio})"

    dados_doc = {"empresa": empresa or "Empresa", "usuario": usuario or "—",
                 "gerado_em": gerado_em, "periodo_texto": periodo_texto}

    class Canvas(CanvasNumerado):
        pass

    Canvas.dados_doc = dados_doc

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGEM, rightMargin=MARGEM,
        topMargin=ALTURA_CABECALHO + 9 * mm, bottomMargin=20 * mm,
        title=f"Relatório de Faturamento - {dados_doc['empresa']}",
        author="SANDRO CRM", subject=periodo_texto, creator="SANDRO CRM",
    )

    historia = [
        _bloco_informacoes(dados_doc, relatorio),
        _indicadores(relatorio),
        Spacer(1, 8 * mm),
        KeepTogether([Paragraph("Faturamento mensal (últimos 12 meses)", ESTILO_SECAO), _grafico_mensal(relatorio)]),
        Spacer(1, 6 * mm),
        Paragraph(f"Vendas fechadas · {escape(periodo_texto)}", ESTILO_SECAO),
    ]
    if relatorio["vendas"]:
        historia.append(_tabela_vendas(relatorio))
    else:
        historia.append(Paragraph("Nenhuma venda fechada neste período.", ESTILO_SUAVE))

    historia += [
        Spacer(1, 5 * mm),
        Paragraph(
            "Faturamento = soma das oportunidades em Fechado cuja última mudança de etapa ocorreu no período. "
            "Taxa de conversão = oportunidades criadas no período que já estão fechadas.",
            ESTILO_SUAVE,
        ),
    ]

    doc.build(historia, canvasmaker=Canvas)
    return buffer.getvalue()

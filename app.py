import os
import psycopg
from psycopg.rows import dict_row
import secrets
import qrcode
import io
import base64
from datetime import datetime
from functools import wraps
from flask import Flask, request, redirect, url_for, session, render_template_string, flash, send_from_directory, Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.pdfbase.pdfmetrics import stringWidth
from flask import send_file

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tatameone-2-troque-em-producao")
DATABASE_URL = os.environ.get("DATABASE_URL")

# Administração geral do TatameOne.
# As credenciais ficam nas variáveis de ambiente do Render,
# nunca gravadas diretamente no código.
SUPERADMIN_EMAIL = os.environ.get("SUPERADMIN_EMAIL", "").strip().lower()
SUPERADMIN_SENHA = os.environ.get("SUPERADMIN_SENHA", "")

def db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não configurada no Render.")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

@app.route("/manifest.json")
def manifest():
    return send_from_directory("public", "manifest.json", mimetype="application/manifest+json")

@app.route("/icon-192.png")
def icon_192():
    return send_from_directory("public", "icon-192.png", mimetype="image/png")

@app.route("/icon-512.png")
def icon_512():
    return send_from_directory("public", "icon-512.png", mimetype="image/png")

def agora():
    from zoneinfo import ZoneInfo
    return datetime.now(
        ZoneInfo("America/Sao_Paulo")
    ).strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    con=db()
    cur=con.cursor()
    comandos=[
"""CREATE TABLE IF NOT EXISTS academias(id BIGSERIAL PRIMARY KEY,nome TEXT NOT NULL,documento TEXT,telefone TEXT,endereco TEXT,logo TEXT,cor TEXT DEFAULT '#111827',plano TEXT DEFAULT 'GRATUITO',ativo INTEGER DEFAULT 1,criado_em TEXT NOT NULL)""",
"""CREATE TABLE IF NOT EXISTS usuarios(id BIGSERIAL PRIMARY KEY,academia_id BIGINT,nome TEXT NOT NULL,email TEXT UNIQUE NOT NULL,senha TEXT NOT NULL,perfil TEXT NOT NULL DEFAULT 'ADMIN',ativo INTEGER DEFAULT 1,criado_em TEXT NOT NULL)""",
"""CREATE TABLE IF NOT EXISTS modalidades(id BIGSERIAL PRIMARY KEY,academia_id BIGINT NOT NULL,nome TEXT NOT NULL,ativo INTEGER DEFAULT 1)""",
"""CREATE TABLE IF NOT EXISTS alunos(id BIGSERIAL PRIMARY KEY,academia_id BIGINT NOT NULL,nome TEXT NOT NULL,documento TEXT,nascimento TEXT,telefone TEXT,email TEXT,responsavel TEXT,telefone_responsavel TEXT,modalidade TEXT,graduacao TEXT,observacoes TEXT,qr_token TEXT UNIQUE,ativo INTEGER DEFAULT 1,criado_em TEXT NOT NULL,endereco TEXT,contato_emergencia TEXT,telefone_emergencia TEXT,foto TEXT)""",
"""CREATE TABLE IF NOT EXISTS planos(id BIGSERIAL PRIMARY KEY,academia_id BIGINT NOT NULL,nome TEXT NOT NULL,valor DOUBLE PRECISION DEFAULT 0,periodicidade TEXT DEFAULT 'MENSAL',descricao TEXT,ativo INTEGER DEFAULT 1)""",
"""CREATE TABLE IF NOT EXISTS matriculas(id BIGSERIAL PRIMARY KEY,academia_id BIGINT NOT NULL,aluno_id BIGINT NOT NULL,plano_id BIGINT,inicio TEXT,vencimento_dia INTEGER DEFAULT 10,valor DOUBLE PRECISION DEFAULT 0,status TEXT DEFAULT 'ATIVA')""",
"""CREATE TABLE IF NOT EXISTS pagamentos(id BIGSERIAL PRIMARY KEY,academia_id BIGINT NOT NULL,aluno_id BIGINT NOT NULL,referencia TEXT,valor DOUBLE PRECISION NOT NULL,forma TEXT DEFAULT 'PIX',status TEXT DEFAULT 'PAGO',pago_em TEXT)""",
"""CREATE TABLE IF NOT EXISTS checkins(id BIGSERIAL PRIMARY KEY,academia_id BIGINT NOT NULL,aluno_id BIGINT NOT NULL,entrada TEXT NOT NULL)""",
"""CREATE TABLE IF NOT EXISTS professores(id BIGSERIAL PRIMARY KEY,academia_id BIGINT NOT NULL,nome TEXT NOT NULL,telefone TEXT,email TEXT,especialidade TEXT,ativo INTEGER DEFAULT 1)""",
"""CREATE TABLE IF NOT EXISTS aulas(id BIGSERIAL PRIMARY KEY,academia_id BIGINT NOT NULL,modalidade TEXT NOT NULL,professor TEXT,dia TEXT,horario TEXT,capacidade INTEGER DEFAULT 20,ativo INTEGER DEFAULT 1)""",
"""CREATE TABLE IF NOT EXISTS avaliacoes(id BIGSERIAL PRIMARY KEY,academia_id BIGINT NOT NULL,aluno_id BIGINT NOT NULL,data TEXT NOT NULL,peso DOUBLE PRECISION,altura DOUBLE PRECISION,gordura DOUBLE PRECISION,cintura DOUBLE PRECISION,braco DOUBLE PRECISION,observacoes TEXT)""",
"""CREATE TABLE IF NOT EXISTS treinos(id BIGSERIAL PRIMARY KEY,academia_id BIGINT NOT NULL,aluno_id BIGINT NOT NULL,titulo TEXT NOT NULL,descricao TEXT,criado_em TEXT NOT NULL)""",
"""CREATE TABLE IF NOT EXISTS caixa(id BIGSERIAL PRIMARY KEY,academia_id BIGINT NOT NULL,tipo TEXT NOT NULL,descricao TEXT,valor DOUBLE PRECISION NOT NULL,forma TEXT,data TEXT NOT NULL)""",
"""CREATE TABLE IF NOT EXISTS avisos(id BIGSERIAL PRIMARY KEY,academia_id BIGINT NOT NULL,titulo TEXT NOT NULL,mensagem TEXT NOT NULL,criado_em TEXT NOT NULL)""",
"""CREATE TABLE IF NOT EXISTS avisos_gerais(id BIGSERIAL PRIMARY KEY,titulo TEXT NOT NULL,mensagem TEXT NOT NULL,criado_em TEXT NOT NULL)""",
"""CREATE TABLE IF NOT EXISTS pre_cadastros(id BIGSERIAL PRIMARY KEY,academia_id BIGINT NOT NULL,nome TEXT NOT NULL,documento TEXT,nascimento TEXT,telefone TEXT,email TEXT,responsavel TEXT,telefone_responsavel TEXT,modalidade TEXT,graduacao TEXT,observacoes TEXT,status TEXT DEFAULT 'PENDENTE',criado_em TEXT NOT NULL,endereco TEXT,contato_emergencia TEXT,telefone_emergencia TEXT,foto TEXT)"""
    ]
    for sql in comandos: cur.execute(sql)

    # Fotos persistentes dos alunos no PostgreSQL.
    # BYTEA evita depender do armazenamento temporário do Render.
    cur.execute("ALTER TABLE alunos ADD COLUMN IF NOT EXISTS foto_dados BYTEA")
    cur.execute("ALTER TABLE alunos ADD COLUMN IF NOT EXISTS foto_tipo TEXT")
    cur.execute("ALTER TABLE pre_cadastros ADD COLUMN IF NOT EXISTS foto_dados BYTEA")
    cur.execute("ALTER TABLE pre_cadastros ADD COLUMN IF NOT EXISTS foto_tipo TEXT")

    # Evolução internacional do módulo de avaliações físicas.
    # ADD COLUMN IF NOT EXISTS preserva avaliações já cadastradas.
    colunas_avaliacao = [
        ("pescoco", "DOUBLE PRECISION"),
        ("ombros", "DOUBLE PRECISION"),
        ("peito", "DOUBLE PRECISION"),
        ("abdomen", "DOUBLE PRECISION"),
        ("quadril", "DOUBLE PRECISION"),
        ("braco_direito", "DOUBLE PRECISION"),
        ("braco_esquerdo", "DOUBLE PRECISION"),
        ("antebraco_direito", "DOUBLE PRECISION"),
        ("antebraco_esquerdo", "DOUBLE PRECISION"),
        ("coxa_direita", "DOUBLE PRECISION"),
        ("coxa_esquerda", "DOUBLE PRECISION"),
        ("panturrilha_direita", "DOUBLE PRECISION"),
        ("panturrilha_esquerda", "DOUBLE PRECISION"),

        # Composição corporal
        ("massa_muscular", "DOUBLE PRECISION"),
        ("massa_ossea", "DOUBLE PRECISION"),
        ("agua_corporal", "DOUBLE PRECISION"),
        ("gordura_visceral", "DOUBLE PRECISION"),
        ("metabolismo_basal", "DOUBLE PRECISION"),

        # Dobras cutâneas
        ("dobra_peitoral", "DOUBLE PRECISION"),
        ("dobra_abdominal", "DOUBLE PRECISION"),
        ("dobra_coxa", "DOUBLE PRECISION"),
        ("dobra_triceps", "DOUBLE PRECISION"),
        ("dobra_subescapular", "DOUBLE PRECISION"),
        ("dobra_suprailiaca", "DOUBLE PRECISION"),
        ("dobra_axilar", "DOUBLE PRECISION"),

        # Performance
        ("flexibilidade", "DOUBLE PRECISION"),
        ("forca", "DOUBLE PRECISION"),
        ("resistencia", "DOUBLE PRECISION"),
        ("agilidade", "DOUBLE PRECISION"),

        # Sinais básicos
        ("pressao_sistolica", "DOUBLE PRECISION"),
        ("pressao_diastolica", "DOUBLE PRECISION"),
        ("frequencia_cardiaca", "DOUBLE PRECISION"),
        ("frequencia_repouso", "DOUBLE PRECISION"),

        # Objetivo e protocolo
        ("objetivo", "TEXT"),
        ("protocolo", "TEXT"),
        ("unidade", "TEXT DEFAULT 'METRICO'")
    ]

    for nome_coluna, tipo_coluna in colunas_avaliacao:
        cur.execute(
            f"ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS {nome_coluna} {tipo_coluna}"
        )


    # Configuração PIX individual de cada academia.
    colunas_pix = [
        ("pix_ativo", "INTEGER DEFAULT 0"),
        ("pix_tipo_chave", "TEXT"),
        ("pix_chave", "TEXT"),
        ("pix_nome", "TEXT"),
        ("pix_cidade", "TEXT")
    ]

    for nome_coluna, tipo_coluna in colunas_pix:
        cur.execute(
            f"ALTER TABLE academias ADD COLUMN IF NOT EXISTS {nome_coluna} {tipo_coluna}"
        )

    # Permissões individuais por usuário.
    # NULL = usar as permissões padrão do perfil.
    cur.execute("""
        ALTER TABLE usuarios
        ADD COLUMN IF NOT EXISTS permissoes_customizadas TEXT
    """)

    con.commit()
    con.close()

def login_required(fn):
    @wraps(fn)
    def wrap(*a, **kw):
        if not session.get("uid"):
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return wrap

def permissao_required(area):
    def decorator(fn):
        @wraps(fn)
        def wrap(*a, **kw):
            if not session.get("uid"):
                return redirect(url_for("login"))

            if not tem_permissao(area):
                flash("Você não tem permissão para acessar esta área.")
                return redirect("/")

            return fn(*a, **kw)
        return wrap
    return decorator

def superadmin_required(fn):
    @wraps(fn)
    def wrap(*a, **kw):
        if not session.get("superadmin"):
            return redirect("/gestao-tatameone/login")
        return fn(*a, **kw)
    return wrap


def aid():
    return session.get("academia_id")

# Perfis de acesso do TatameOne
PERMISSOES = {
    "DONO": {
        "painel", "alunos", "checkin", "planos",
        "financeiro", "aulas", "avaliacoes", "config"
    },
    "ADMIN": {
        "painel", "alunos", "checkin", "planos",
        "financeiro", "aulas", "avaliacoes"
    },
    "PROFESSOR": {
        "painel", "alunos", "checkin",
        "aulas", "avaliacoes"
    },
    "FUNCIONARIO": {
        "painel", "alunos", "checkin"
    }
}

def tem_permissao(area):
    perfil = str(session.get("perfil") or "").upper()

    # DONO sempre mantém acesso completo.
    if perfil == "DONO":
        return area in PERMISSOES["DONO"]

    # Permissões personalizadas já carregadas no login.
    personalizadas = session.get("permissoes_customizadas")

    if personalizadas is not None:
        return area in set(personalizadas)

    # Sem personalização: usa o padrão do perfil.
    return area in PERMISSOES.get(perfil, set())

BASE = """
<!doctype html><html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}} · TatameOne</title>
<link rel="manifest" href="/manifest.json">
<link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png">
<link rel="apple-touch-icon" sizes="192x192" href="/icon-192.png">
<meta name="theme-color" content="#e52e3d">
<style>
*{box-sizing:border-box} body{margin:0;font-family:Arial,sans-serif;background:#f3f4f6;color:#111827}
.top{background:#111827;color:white;padding:14px 18px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:1000}
.top-left{display:flex;align-items:center;gap:18px;min-width:0}
.top-clock{display:flex;align-items:center;gap:10px;border-left:1px solid rgba(255,255,255,.35);padding-left:18px;white-space:nowrap}
.clock-icon{font-size:32px}
.clock-time{font-size:24px;font-weight:900;line-height:1}
.clock-date{font-size:12px;margin-top:5px;color:#e5e7eb}
.top-user{font-size:18px;text-align:right}

@media(max-width:700px){
  .top{padding:10px 12px;gap:8px}
  .top-left{gap:8px;flex:1}
  .brand img{width:150px !important;height:58px !important;max-width:42vw !important}
  .top-clock{gap:5px;padding-left:8px}
  .clock-icon{font-size:21px}
  .clock-time{font-size:17px}
  .clock-date{font-size:9px}
  .top-user{font-size:13px;max-width:90px;overflow:hidden;text-overflow:ellipsis}
}
.brand{font-size:21px;font-weight:800}.brand b{color:#22c55e}
.wrap{max-width:1150px;margin:auto;padding:18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.card{background:white;border-radius:16px;padding:16px;box-shadow:0 2px 12px #00000010}
.big{font-size:28px;font-weight:800}.muted{color:#6b7280}
.nav-wrap{max-width:1150px;margin:auto;padding:28px 16px 0}
.nav{display:grid;grid-template-columns:1fr;gap:26px}
.nav a.btn{min-height:195px;border-radius:34px;padding:32px 34px;display:flex;align-items:center;gap:28px;text-align:left;box-shadow:0 4px 18px #00000018}
.nav-icon{font-size:82px;line-height:1;width:92px;text-align:center;flex:0 0 92px}
.nav-copy{display:flex;flex-direction:column;gap:4px;min-width:0;flex:1}
.nav-title{font-size:42px;font-weight:800;line-height:1.1}
.nav-desc{font-size:24px;color:#6b7280;font-weight:400;line-height:1.3}
.nav-arrow{font-size:48px;font-weight:800;color:#16a34a}
.nav a.danger .nav-desc,.nav a.danger .nav-arrow{color:#fee2e2}
a.btn,button{border:0;border-radius:10px;padding:11px 14px;background:#111827;color:white;text-decoration:none;cursor:pointer}
a.green,button.green{background:#16a34a} a.light{background:white;color:#111827;border:1px solid #ddd}
input,select,textarea{width:100%;padding:11px;border:1px solid #d1d5db;border-radius:10px;margin:5px 0 12px;font-size:24px}
label{font-size:26px;font-weight:700} table{width:100%;border-collapse:collapse;background:white;font-size:22px}
th,td{text-align:left;padding:10px;border-bottom:1px solid #eee}.pill{padding:5px 8px;border-radius:99px;background:#dcfce7;font-size:20px}
h1{margin-top:5px;font-size:38px}
h2{font-size:32px}
.wrap .muted{font-size:26px}

/* LETRAS GRANDES NAS ABAS INTERNAS */
.wrap{
    font-size:24px;
}

.wrap .card{
    font-size:24px;
    line-height:1.35;
}

.wrap a.btn,
.wrap button{
    font-size:22px;
    font-weight:700;
    padding:16px 20px;
    min-height:54px;
}

.wrap table{
    font-size:24px;
}

.wrap th,
.wrap td{
    font-size:24px;
}

.wrap .pill{
    font-size:21px;
}

.wrap p{
    font-size:24px;
    line-height:1.4;
}

/* NÃO ALTERAR O MENU PRINCIPAL */
.nav-wrap,
.nav-wrap .nav{
    font-size:initial;
}

/* AVALIAÇÕES CONTINUAM COM CSS PRÓPRIO */
.actions{display:flex;gap:8px;flex-wrap:wrap}.danger{background:#dc2626!important}
@media(max-width:760px){
  .wrap{padding:14px}.top{padding:14px 16px}.big{font-size:24px}

  /* MENU PRINCIPAL RESPONSIVO PARA CHROME E APK */
  .nav-wrap{
    width:100%;
    max-width:100%;
    padding:18px 10px 16px;
    overflow-x:hidden;
  }

  .nav{
    width:100%;
    max-width:100%;
    grid-template-columns:minmax(0,1fr);
    gap:16px;
  }

  .nav a.btn{
    width:100%;
    max-width:100%;
    min-width:0;
    min-height:170px;
    padding:26px 22px;
    border-radius:28px;
    gap:20px;
    overflow:hidden;
  }

  .nav-icon{
    font-size:68px;
    width:76px;
    flex:0 0 76px;
  }

  .nav-copy{
    min-width:0;
    overflow:hidden;
  }

  .nav-title{
    font-size:36px;
    max-width:100%;
  }

  /* SOMENTE TÍTULOS LONGOS */
  .nav-title.long-title{
    font-size:31px;
  }

  .nav-desc{
    font-size:21px;
    max-width:100%;
    overflow-wrap:anywhere;
  }

  .nav-arrow{
    font-size:42px;
    flex:0 0 auto;
  }

  th:nth-child(n+4),td:nth-child(n+4){display:none}
}

/* MOBILE INTERNO 1 COLUNA */
@media (max-width:700px){

    /* Nas páginas internas, grids passam para uma coluna */
    .wrap > .grid,
    .wrap .grid:not(.nav){
        grid-template-columns:1fr !important;
    }

    /* Cartões aproveitam a largura do celular */
    .wrap .card{
        width:auto !important;
        max-width:none !important;
    }

    /* Campos permanecem confortáveis */
    .wrap input,
    .wrap select,
    .wrap textarea{
        width:100% !important;
        box-sizing:border-box;
    }
}

</style></head><body>
<div class="top">
  <div class="top-left">

    <div class="brand">
      <img src="/static/img/logo_tatameone.png"
           alt="TatameOne"
           style="height:72px;width:clamp(230px,55vw,420px);max-width:65vw;object-fit:contain;object-position:left center;display:block">
    </div>

    <div class="top-clock">
      <div class="clock-icon">🕐</div>

      <div>
        <div id="tatameClock" class="clock-time">--:--:--</div>
        <div id="tatameDate" class="clock-date"></div>
      </div>
    </div>

  </div>

  <div class="top-user">
    {{session.get('nome','')}}
  </div>
</div>
{% if session.get('uid') and request.path == '/' %}
<div class="nav-wrap"><div class="nav">
{% if tem_permissao('painel') %}<a class="btn light" href="/painel"><span class="nav-icon">📊</span><span class="nav-copy"><span class="nav-title">Painel</span><span class="nav-desc">Visão geral da academia</span></span><span class="nav-arrow">›</span></a>{% endif %}
{% if tem_permissao('alunos') %}<a class="btn light" href="/alunos"><span class="nav-icon">👥</span><span class="nav-copy"><span class="nav-title">Alunos</span><span class="nav-desc">Cadastros e acompanhamento</span></span><span class="nav-arrow">›</span></a>{% endif %}
{% if tem_permissao('checkin') %}<a class="btn light" href="/checkin"><span class="nav-icon">✅</span><span class="nav-copy"><span class="nav-title">Check-in</span><span class="nav-desc">Registrar entrada dos alunos</span></span><span class="nav-arrow">›</span></a>{% endif %}
{% if tem_permissao('planos') %}<a class="btn light" href="/planos"><span class="nav-icon">💳</span><span class="nav-copy"><span class="nav-title">Planos</span><span class="nav-desc">Planos e mensalidades</span></span><span class="nav-arrow">›</span></a>{% endif %}
{% if tem_permissao('financeiro') %}<a class="btn light" href="/financeiro"><span class="nav-icon">💰</span><span class="nav-copy"><span class="nav-title">Financeiro</span><span class="nav-desc">Pagamentos e recebimentos</span></span><span class="nav-arrow">›</span></a>{% endif %}
{% if tem_permissao('aulas') %}<a class="btn light" href="/aulas"><span class="nav-icon">📅</span><span class="nav-copy"><span class="nav-title">Aulas</span><span class="nav-desc">Agenda, horários e professores</span></span><span class="nav-arrow">›</span></a>{% endif %}
{% if tem_permissao('avaliacoes') %}<a class="btn light" href="/avaliacoes"><span class="nav-icon">📈</span><span class="nav-copy"><span class="nav-title">Avaliações</span><span class="nav-desc">Avaliações e evolução</span></span><span class="nav-arrow">›</span></a>{% endif %}
{% if session.get('perfil','')|upper == 'DONO' %}<a class="btn light" href="/anuncios"><span class="nav-icon">📢</span><span class="nav-copy"><span class="nav-title">Anúncios</span><span class="nav-desc">Comunicados da academia</span></span><span class="nav-arrow">›</span></a>{% endif %}
{% if tem_permissao('config') %}<a class="btn light" href="/config"><span class="nav-icon">⚙️</span><span class="nav-copy"><span class="nav-title long-title">Configurações</span><span class="nav-desc">Dados e modalidades</span></span><span class="nav-arrow">›</span></a>{% endif %}
<a class="btn danger" href="/logout"><span class="nav-icon">🚪</span><span class="nav-copy"><span class="nav-title">Sair</span><span class="nav-desc">Encerrar sessão</span></span><span class="nav-arrow">›</span></a>
</div></div>
{% endif %}
{% if session.get('uid') and request.path != '/' %}
<div style="max-width:1150px;margin:14px auto 0;padding:0 18px">
<a href="/" style="display:inline-flex;align-items:center;gap:12px;background:#111827;color:white;text-decoration:none;padding:20px 28px;border-radius:16px;font-weight:800;font-size:26px;min-height:64px">← Voltar ao Painel</a>
</div>
{% endif %}
<div class="wrap">{{body|safe}}</div>

<script>
(function(){

  function atualizarRelogio(){

    const agora = new Date();

    const hora = new Intl.DateTimeFormat(
      'pt-BR',
      {
        timeZone:'America/Sao_Paulo',
        hour:'2-digit',
        minute:'2-digit',
        second:'2-digit',
        hour12:false
      }
    ).format(agora);

    const data = new Intl.DateTimeFormat(
      'pt-BR',
      {
        timeZone:'America/Sao_Paulo',
        weekday:'short',
        day:'2-digit',
        month:'2-digit',
        year:'numeric'
      }
    ).format(agora);

    const relogio =
      document.getElementById('tatameClock');

    const dataEl =
      document.getElementById('tatameDate');

    if(relogio) relogio.textContent = hora;
    if(dataEl) dataEl.textContent = data;
  }

  atualizarRelogio();
  setInterval(atualizarRelogio,1000);

})();
</script>



</body></html>
"""

def page(title, body, **ctx):
    inner = render_template_string(body, **ctx)
    return render_template_string(
        BASE,
        title=title,
        body=inner,
        tem_permissao=tem_permissao
    )

PUBLIC_BASE = """
<!doctype html><html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}} · TatameOne</title><style>
*{box-sizing:border-box}body{margin:0;font-family:Arial,sans-serif;background:#f3f4f6;color:#111827}
.pubtop{background:{{cor}};color:white;padding:20px;text-align:center}.pubtop b{font-size:25px}
.wrap-public{max-width:760px;margin:auto;padding:16px}.card{background:white;border-radius:18px;padding:20px;box-shadow:0 2px 14px #0001}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.muted{color:#6b7280}
input,select,textarea{width:100%;padding:12px;border:1px solid #d1d5db;border-radius:10px;margin:5px 0 12px}
label{font-size:13px;font-weight:700}button{width:100%;border:0;border-radius:11px;padding:15px;background:#16a34a;color:white;font-size:18px}
.ok{background:#ecfdf5;border:1px solid #bbf7d0;border-radius:12px;padding:13px;color:#166534}
@media(max-width:620px){.grid{grid-template-columns:1fr}.wrap-public{padding:12px}}
</style></head><body><div class="pubtop"><div>TATAMEONE</div><b>{{academia}}</b></div>
<div class="wrap-public">{{body|safe}}</div></body></html>"""

def public_page(title, body, ac, **ctx):
    inner=render_template_string(body, **ctx)
    return render_template_string(PUBLIC_BASE,title=title,body=inner,academia=ac["nome"],cor=ac["cor"] or "#111827")

@app.route("/primeiro-acesso", methods=["GET","POST"])
def primeiro_acesso():
    con = db()

    total = con.cursor().execute(
        "SELECT COUNT(*) AS n FROM academias"
    ).fetchone()["n"]

    # Primeiro acesso só existe enquanto não houver academia.
    if total > 0:
        con.close()
        return redirect("/login")

    erro = ""

    if request.method == "POST":
        academia = request.form.get("academia", "").strip()
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "").strip()
        confirmar = request.form.get("confirmar", "").strip()

        if not academia or not nome or not email or not senha:
            erro = "Preencha todos os campos."
        elif senha != confirmar:
            erro = "As senhas não conferem."
        elif len(senha) < 4:
            erro = "A senha deve possuir pelo menos 4 caracteres."
        else:
            try:
                cur = con.cursor()

                cur.execute(
                    """INSERT INTO academias(nome,plano,criado_em)
                       VALUES(%s,%s,%s) RETURNING id""",
                    (academia, "GRATUITO", agora())
                )

                academia_id = cur.fetchone()["id"]

                cur.execute(
                    """INSERT INTO usuarios
                       (academia_id,nome,email,senha,perfil,ativo,criado_em)
                       VALUES(%s,%s,%s,%s,%s,1,%s)""",
                    (academia_id,nome,email,senha,"DONO",agora())
                )

                for modalidade in (
                    "Musculação","Jiu-Jítsu","Muay Thai","Boxe",
                    "Funcional","Cross Training","Pilates","Yoga",
                    "Dança","Natação","Personal"
                ):
                    cur.execute(
                        "INSERT INTO modalidades(academia_id,nome) VALUES(%s,%s)",
                        (academia_id, modalidade)
                    )

                cur.execute(
                    """INSERT INTO planos
                       (academia_id,nome,valor,periodicidade,descricao)
                       VALUES(%s,%s,%s,%s,%s)""",
                    (
                        academia_id,
                        "Plano Gratuito",
                        0,
                        "MENSAL",
                        "Plano sem cobrança"
                    )
                )

                con.commit()
                con.close()

                return redirect("/login")

            except Exception:
                con.rollback()
                erro = "Não foi possível concluir o primeiro cadastro."

    con.close()

    return page("Primeiro acesso","""
    <div class="card"
         style="max-width:620px;width:92%;margin:5vh auto;padding:32px;border-radius:24px">

      <h1 style="font-size:42px;margin-bottom:10px">
        Primeiro acesso
      </h1>

      <p class="muted" style="font-size:24px;margin-bottom:26px">
        Cadastre a academia e o proprietário do TatameOne.
      </p>

      {% if erro %}
      <p style="color:#dc2626;font-size:22px">{{erro}}</p>
      {% endif %}

      <form method="post">

        <label>Nome da academia</label>
        <input name="academia" required>

        <label>Nome do proprietário</label>
        <input name="nome" required>

        <label>E-mail</label>
        <input name="email" type="email" required>

        <label>Senha</label>
        <input name="senha" type="password" required>

        <label>Confirmar senha</label>
        <input name="confirmar" type="password" required>

        <button class="green"
                style="width:100%;font-size:26px;font-weight:800;
                       min-height:68px;border-radius:14px">
          Criar academia
        </button>

      </form>
    </div>
    """, erro=erro)


@app.route("/gestao-tatameone/login", methods=["GET","POST"])
def superadmin_login():
    if session.get("superadmin"):
        return redirect("/gestao-tatameone")

    erro = ""

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        if not SUPERADMIN_EMAIL or not SUPERADMIN_SENHA:
            erro = "Administração geral ainda não configurada."
        elif email == SUPERADMIN_EMAIL and secrets.compare_digest(
            senha,
            SUPERADMIN_SENHA
        ):
            session.clear()
            session["superadmin"] = True
            session["nome"] = "Administração TatameOne"

            return redirect("/gestao-tatameone")
        else:
            erro = "E-mail ou senha inválidos."

    return page("Administração TatameOne","""
    <div class="card"
         style="max-width:650px;width:94%;margin:6vh auto;
                padding:32px;border-radius:24px">

      <h1>🛡️ Administração TatameOne</h1>

      <p class="muted">
        Acesso exclusivo da administração geral do sistema.
      </p>

      {% if erro %}
      <div style="color:#dc2626;font-size:23px;margin:18px 0">
        {{erro}}
      </div>
      {% endif %}

      <form method="post">

        <label>E-mail administrativo</label>
        <input name="email"
               type="email"
               autocomplete="username"
               required>

        <label>Senha</label>
        <input name="senha"
               type="password"
               autocomplete="current-password"
               required>

        <button class="green"
                style="width:100%;font-size:26px;
                       min-height:68px;font-weight:800">
          Entrar na administração
        </button>

      </form>
    </div>
    """, erro=erro)


@app.route("/gestao-tatameone/logout")
def superadmin_logout():
    session.clear()
    return redirect("/gestao-tatameone/login")


@app.route("/gestao-tatameone", methods=["GET","POST"])
@superadmin_required
def superadmin_painel():
    con = db()
    erro = ""
    sucesso = ""

    if request.method == "POST":
        academia = request.form.get("academia", "").strip()
        proprietario = request.form.get("proprietario", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "").strip()
        plano = request.form.get("plano", "GRATUITO").strip().upper()

        planos_validos = {
            "GRATUITO",
            "BASICO",
            "PRO",
            "PREMIUM"
        }

        if plano not in planos_validos:
            plano = "GRATUITO"

        if not academia or not proprietario or not email or not senha:
            erro = "Preencha academia, proprietário, e-mail e senha."

        elif len(senha) < 4:
            erro = "A senha inicial deve possuir pelo menos 4 caracteres."

        else:
            existente = con.cursor().execute(
                """SELECT id
                   FROM usuarios
                   WHERE lower(email)=lower(%s)""",
                (email,)
            ).fetchone()

            if existente:
                erro = "Este e-mail já está cadastrado no TatameOne."

            else:
                try:
                    cur = con.cursor()

                    cur.execute(
                        """INSERT INTO academias
                           (nome,plano,ativo,criado_em)
                           VALUES(%s,%s,1,%s)
                           RETURNING id""",
                        (academia, plano, agora())
                    )

                    academia_id = cur.fetchone()["id"]

                    cur.execute(
                        """INSERT INTO usuarios
                           (academia_id,nome,email,senha,
                            perfil,ativo,criado_em)
                           VALUES(%s,%s,%s,%s,'DONO',1,%s)""",
                        (
                            academia_id,
                            proprietario,
                            email,
                            senha,
                            agora()
                        )
                    )

                    for modalidade in (
                        "Musculação",
                        "Jiu-Jítsu",
                        "Muay Thai",
                        "Boxe",
                        "Funcional",
                        "Cross Training",
                        "Pilates",
                        "Yoga",
                        "Dança",
                        "Natação",
                        "Personal"
                    ):
                        cur.execute(
                            """INSERT INTO modalidades
                               (academia_id,nome)
                               VALUES(%s,%s)""",
                            (academia_id, modalidade)
                        )

                    cur.execute(
                        """INSERT INTO planos
                           (academia_id,nome,valor,
                            periodicidade,descricao)
                           VALUES(%s,%s,%s,%s,%s)""",
                        (
                            academia_id,
                            "Plano Gratuito",
                            0,
                            "MENSAL",
                            "Plano sem cobrança"
                        )
                    )

                    con.commit()
                    sucesso = "Academia criada com sucesso."

                except Exception:
                    con.rollback()
                    erro = "Não foi possível criar a academia."

    academias = con.cursor().execute(
        """SELECT
               a.id,
               a.nome,
               a.plano,
               a.ativo,
               a.criado_em,
               u.id AS dono_id,
               u.nome AS dono_nome,
               u.email AS dono_email,
               u.ativo AS dono_ativo
           FROM academias a
           LEFT JOIN usuarios u
             ON u.academia_id=a.id
            AND upper(u.perfil)='DONO'
           ORDER BY a.id DESC"""
    ).fetchall()

    con.close()

    return page("Gestão TatameOne","""
    <h1>🛡️ Administração Geral</h1>

    <p class="muted">
      Gerenciamento das empresas que utilizam o TatameOne.
    </p>

    {% if erro %}
    <div class="card"
         style="color:#dc2626;margin-bottom:20px">
      {{erro}}
    </div>
    {% endif %}

    {% if sucesso %}
    <div class="card"
         style="color:#16a34a;margin-bottom:20px">
      {{sucesso}}
    </div>
    {% endif %}

    <div class="grid">

      <div class="card">

        <h2>➕ Nova academia</h2>

        <form method="post">

          <label>Nome da academia</label>
          <input name="academia" required>

          <label>Nome do proprietário</label>
          <input name="proprietario" required>

          <label>E-mail do proprietário</label>
          <input name="email"
                 type="email"
                 autocomplete="off"
                 required>

          <label>Senha inicial</label>
          <input name="senha"
                 type="password"
                 autocomplete="new-password"
                 required>

          <label>Plano do sistema</label>
          <select name="plano">
            <option value="GRATUITO">Gratuito</option>
            <option value="BASICO">Básico</option>
            <option value="PRO">Pro</option>
            <option value="PREMIUM">Premium</option>
          </select>

          <button class="green"
                  style="width:100%;font-size:25px;
                         min-height:65px;font-weight:800">
            Criar academia
          </button>

        </form>

      </div>


      <div class="card">

        <h2>🏢 Academias cadastradas</h2>

        <p class="muted">
          Total: {{academias|length}}
        </p>

        {% for a in academias %}

        <div style="
             padding:20px 0;
             border-bottom:1px solid #ddd">

          <h2 style="margin-bottom:8px">
            {{a.nome}}
          </h2>

          <p>
            Plano:
            <b>{{a.plano}}</b>
          </p>

          {% if a.ativo %}
            <span class="pill">ACADEMIA ATIVA</span>
          {% else %}
            <span class="pill"
                  style="background:#fee2e2">
              ACADEMIA BLOQUEADA
            </span>
          {% endif %}

          <p style="margin-top:16px">
            <b>Proprietário:</b><br>
            {{a.dono_nome or 'Não localizado'}}<br>
            {{a.dono_email or '-'}}
          </p>

          <div class="actions"
               style="margin-top:16px">

            <a class="btn"
               href="/gestao-tatameone/academia/{{a.id}}">
              ⚙️ Gerenciar
            </a>

          </div>

        </div>

        {% else %}

        <p class="muted">
          Nenhuma academia cadastrada.
        </p>

        {% endfor %}

      </div>

    </div>

    <div style="margin-top:25px">

      <a class="btn"
         href="/gestao-tatameone/anuncios"
         style="margin-right:10px">
        🌐 Anúncios Gerais
      </a>

      <a class="btn danger"
         href="/gestao-tatameone/logout">
        🚪 Sair da administração
      </a>

    </div>
    """,
    academias=academias,
    erro=erro,
    sucesso=sucesso)



@app.route("/gestao-tatameone/anuncios", methods=["GET","POST"])
@superadmin_required
def superadmin_anuncios():
    con = db()
    erro = ""
    sucesso = ""

    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        mensagem = request.form.get("mensagem", "").strip()

        if not titulo or not mensagem:
            erro = "Preencha o título e a mensagem."
        else:
            con.cursor().execute(
                """INSERT INTO avisos_gerais
                   (titulo,mensagem,criado_em)
                   VALUES(%s,%s,%s)""",
                (titulo, mensagem, agora())
            )
            con.commit()
            sucesso = "Anúncio geral publicado para todas as academias."

    rows = con.cursor().execute(
        """SELECT *
           FROM avisos_gerais
           ORDER BY id DESC"""
    ).fetchall()

    con.close()

    return page("Anúncios Gerais", """
    <h1>🌐 Anúncios Gerais TatameOne</h1>

    <p class="muted">
      Estes anúncios aparecem para todas as academias,
      nos planos Gratuito, Básico, Pro e Premium.
    </p>

    {% if erro %}
    <div class="card" style="color:#dc2626;margin-bottom:18px">
      {{erro}}
    </div>
    {% endif %}

    {% if sucesso %}
    <div class="card" style="color:#16a34a;margin-bottom:18px">
      {{sucesso}}
    </div>
    {% endif %}

    <div class="card" style="margin-bottom:22px">
      <h2>📣 Publicar para todas as academias</h2>

      <form method="post">
        <label>Título</label>
        <input name="titulo"
               maxlength="150"
               required>

        <label>Mensagem</label>
        <textarea name="mensagem"
                  rows="6"
                  required></textarea>

        <button class="green"
                style="width:100%;font-size:24px;
                       min-height:62px;font-weight:800">
          🌐 Publicar anúncio geral
        </button>
      </form>
    </div>

    <h2>📋 Anúncios gerais publicados</h2>

    {% for a in rows %}
    <div class="card" style="margin-bottom:14px">
      <h2>{{a.titulo}}</h2>

      <div style="font-size:19px;white-space:pre-wrap">
        {{a.mensagem}}
      </div>

      <p class="muted">{{a.criado_em}}</p>

      <a class="btn danger"
         href="/gestao-tatameone/anuncios/{{a.id}}/excluir"
         onclick="return confirm('Excluir este anúncio geral?')">
        🗑️ Excluir
      </a>
    </div>
    {% else %}
    <div class="card">
      Nenhum anúncio geral publicado.
    </div>
    {% endfor %}

    <div style="margin-top:22px">
      <a class="btn" href="/gestao-tatameone">
        ← Voltar à Administração
      </a>
    </div>
    """, rows=rows, erro=erro, sucesso=sucesso)


@app.route("/gestao-tatameone/anuncios/<int:id>/excluir")
@superadmin_required
def superadmin_excluir_anuncio(id):
    con = db()

    con.cursor().execute(
        "DELETE FROM avisos_gerais WHERE id=%s",
        (id,)
    )

    con.commit()
    con.close()

    return redirect("/gestao-tatameone/anuncios")


@app.route(
    "/gestao-tatameone/academia/<int:id>",
    methods=["GET","POST"]
)
@superadmin_required
def superadmin_academia(id):
    con = db()
    erro = ""
    sucesso = ""

    academia = con.cursor().execute(
        """SELECT *
           FROM academias
           WHERE id=%s""",
        (id,)
    ).fetchone()

    if not academia:
        con.close()
        return redirect("/gestao-tatameone")

    dono = con.cursor().execute(
        """SELECT id,nome,email,ativo
           FROM usuarios
           WHERE academia_id=%s
             AND upper(perfil)='DONO'
           ORDER BY id
           LIMIT 1""",
        (id,)
    ).fetchone()

    if request.method == "POST":

        acao = request.form.get("acao", "")

        if acao == "salvar":

            nome_academia = request.form.get(
                "academia",
                ""
            ).strip()

            nome_dono = request.form.get(
                "proprietario",
                ""
            ).strip()

            email = request.form.get(
                "email",
                ""
            ).strip().lower()

            plano = request.form.get(
                "plano",
                "GRATUITO"
            ).strip().upper()

            nova_senha = request.form.get(
                "nova_senha",
                ""
            ).strip()

            if plano not in (
                "GRATUITO",
                "BASICO",
                "PRO",
                "PREMIUM"
            ):
                plano = "GRATUITO"

            if not nome_academia:
                erro = "Informe o nome da academia."

            elif dono and (not nome_dono or not email):
                erro = "Informe nome e e-mail do proprietário."

            else:

                email_em_uso = None

                if dono:
                    email_em_uso = con.cursor().execute(
                        """SELECT id
                           FROM usuarios
                           WHERE lower(email)=lower(%s)
                             AND id<>%s""",
                        (email, dono["id"])
                    ).fetchone()

                if email_em_uso:
                    erro = "Este e-mail já está sendo utilizado."

                else:
                    con.cursor().execute(
                        """UPDATE academias
                           SET nome=%s,
                               plano=%s
                           WHERE id=%s""",
                        (
                            nome_academia,
                            plano,
                            id
                        )
                    )

                    if dono:

                        if nova_senha:
                            con.cursor().execute(
                                """UPDATE usuarios
                                   SET nome=%s,
                                       email=%s,
                                       senha=%s
                                   WHERE id=%s
                                     AND academia_id=%s""",
                                (
                                    nome_dono,
                                    email,
                                    nova_senha,
                                    dono["id"],
                                    id
                                )
                            )

                        else:
                            con.cursor().execute(
                                """UPDATE usuarios
                                   SET nome=%s,
                                       email=%s
                                   WHERE id=%s
                                     AND academia_id=%s""",
                                (
                                    nome_dono,
                                    email,
                                    dono["id"],
                                    id
                                )
                            )

                    con.commit()
                    sucesso = "Dados atualizados com sucesso."

        elif acao == "status":

            novo_status = 0 if academia["ativo"] else 1

            con.cursor().execute(
                """UPDATE academias
                   SET ativo=%s
                   WHERE id=%s""",
                (novo_status, id)
            )

            con.commit()

            sucesso = (
                "Academia ativada."
                if novo_status
                else "Academia bloqueada."
            )

    academia = con.cursor().execute(
        """SELECT *
           FROM academias
           WHERE id=%s""",
        (id,)
    ).fetchone()

    dono = con.cursor().execute(
        """SELECT id,nome,email,ativo
           FROM usuarios
           WHERE academia_id=%s
             AND upper(perfil)='DONO'
           ORDER BY id
           LIMIT 1""",
        (id,)
    ).fetchone()

    con.close()

    return page("Gerenciar academia","""
    <h1>🏢 Gerenciar academia</h1>

    {% if erro %}
    <div class="card"
         style="color:#dc2626;margin-bottom:18px">
      {{erro}}
    </div>
    {% endif %}

    {% if sucesso %}
    <div class="card"
         style="color:#16a34a;margin-bottom:18px">
      {{sucesso}}
    </div>
    {% endif %}

    <div class="card">

      <form method="post">

        <input type="hidden"
               name="acao"
               value="salvar">

        <label>Nome da academia</label>
        <input name="academia"
               value="{{academia.nome}}"
               required>

        <label>Plano</label>
        <select name="plano">

          {% for plano in
             ['GRATUITO','BASICO','PRO','PREMIUM'] %}

          <option value="{{plano}}"
            {% if academia.plano == plano %}
              selected
            {% endif %}>
            {{plano}}
          </option>

          {% endfor %}

        </select>

        {% if dono %}

        <hr style="margin:28px 0">

        <h2>👤 Proprietário</h2>

        <label>Nome</label>
        <input name="proprietario"
               value="{{dono.nome}}"
               required>

        <label>E-mail</label>
        <input name="email"
               type="email"
               value="{{dono.email}}"
               required>

        <label>Nova senha</label>
        <input name="nova_senha"
               type="password"
               autocomplete="new-password">

        <p class="muted">
          Deixe a nova senha vazia para manter a atual.
        </p>

        {% else %}

        <div class="card"
             style="background:#fef2f2">
          Proprietário DONO não localizado.
        </div>

        {% endif %}

        <button class="green"
                style="width:100%;
                       min-height:65px;
                       font-size:25px">
          💾 Salvar alterações
        </button>

      </form>

    </div>

    <div class="card"
         style="margin-top:20px">

      <h2>Estado da academia</h2>

      {% if academia.ativo %}

      <p>
        🟢 Academia atualmente ativa.
      </p>

      <form method="post"
            onsubmit="return confirm(
              'Bloquear esta academia?'
            );">

        <input type="hidden"
               name="acao"
               value="status">

        <button class="danger"
                style="width:100%;
                       min-height:65px;
                       font-size:24px">
          ⛔ Bloquear academia
        </button>

      </form>

      {% else %}

      <p>
        🔴 Academia atualmente bloqueada.
      </p>

      <form method="post">

        <input type="hidden"
               name="acao"
               value="status">

        <button class="green"
                style="width:100%;
                       min-height:65px;
                       font-size:24px">
          ✅ Reativar academia
        </button>

      </form>

      {% endif %}

    </div>

    <div style="margin-top:22px">

      <a class="btn"
         href="/gestao-tatameone">
        ← Voltar para Administração Geral
      </a>

    </div>
    """,
    academia=academia,
    dono=dono,
    erro=erro,
    sucesso=sucesso)


@app.route("/login", methods=["GET","POST"])
def login():
    con = db()
    total = con.cursor().execute(
        "SELECT COUNT(*) AS n FROM academias"
    ).fetchone()["n"]
    con.close()

    if total == 0:
        return redirect("/primeiro-acesso")

    erro=""
    if request.method=="POST":
        con=db()
        u=con.cursor().execute("SELECT * FROM usuarios WHERE lower(email)=lower(%s) AND senha=%s AND ativo=1",
                      (request.form["email"].strip(),request.form["senha"])).fetchone()
        con.close()
        if u:
            permissoes_sessao = None

            if u["permissoes_customizadas"] is not None:
                permissoes_sessao = [
                    x.strip()
                    for x in str(u["permissoes_customizadas"]).split(",")
                    if x.strip()
                ]

            session.update(
                uid=u["id"],
                academia_id=u["academia_id"],
                nome=u["nome"],
                perfil=u["perfil"],
                permissoes_customizadas=permissoes_sessao
            )

            return redirect("/")
        erro="E-mail ou senha inválidos."
    return page("Entrar","""
    <div class="card" style="max-width:620px;width:92%;margin:7vh auto;padding:32px;border-radius:24px">
    <h1 style="font-size:46px;margin-bottom:22px">Entrar</h1>
    <p class="muted" style="font-size:27px;margin-bottom:28px">Gestão completa para academias.</p>
    {% if erro %}<p style="color:#dc2626;font-size:24px">{{erro}}</p>{% endif %}
    <form method="post">
    <label style="font-size:28px">E-mail</label>
    <input name="email" type="email" required
           style="font-size:27px;padding:18px;min-height:66px;margin-bottom:22px">
    <label style="font-size:28px">Senha</label>
    <input name="senha" type="password" required
           style="font-size:27px;padding:18px;min-height:66px;margin-bottom:26px">
    <button class="green" style="width:100%;font-size:28px;font-weight:800;min-height:70px;border-radius:14px">Entrar</button>
    </form></div>""", erro=erro)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
@login_required
def inicio():
    con = db()

    gerais = con.cursor().execute(
        """SELECT *
           FROM avisos_gerais
           ORDER BY id DESC
           LIMIT 5"""
    ).fetchall()

    locais = con.cursor().execute(
        """SELECT *
           FROM avisos
           WHERE academia_id=%s
           ORDER BY id DESC
           LIMIT 5""",
        (aid(),)
    ).fetchall()

    con.close()

    return page("Início", """
    {% if gerais or locais %}
    <div style="margin-top:28px">

      <h1>📢 Anúncios</h1>

      {% for a in gerais %}
      <div class="card"
           style="margin-bottom:14px;border-left:7px solid #e52e3d">
        <div class="pill">🌐 TATAMEONE</div>
        <h2 style="margin-bottom:8px">{{a.titulo}}</h2>
        <div style="font-size:20px;white-space:pre-wrap">
          {{a.mensagem}}
        </div>
        <p class="muted" style="margin-bottom:0">
          {{a.criado_em}}
        </p>
      </div>
      {% endfor %}

      {% for a in locais %}
      <div class="card"
           style="margin-bottom:14px;border-left:7px solid #2563eb">
        <div class="pill">🏢 ACADEMIA</div>
        <h2 style="margin-bottom:8px">{{a.titulo}}</h2>
        <div style="font-size:20px;white-space:pre-wrap">
          {{a.mensagem}}
        </div>
        <p class="muted" style="margin-bottom:0">
          {{a.criado_em}}
        </p>
      </div>
      {% endfor %}

    </div>
    {% endif %}

    
    """, gerais=gerais, locais=locais)

@app.route("/painel")
@login_required
@permissao_required("painel")
def dashboard():
    con=db()
    stats={
      "alunos":con.cursor().execute("SELECT COUNT(*) n FROM alunos WHERE academia_id=%s AND ativo=1",(aid(),)).fetchone()["n"],
      "checkins":con.cursor().execute("SELECT COUNT(*) n FROM checkins WHERE academia_id=%s AND date(entrada)=CURRENT_DATE",(aid(),)).fetchone()["n"],
      "receita":con.cursor().execute("SELECT COALESCE(SUM(valor),0) n FROM pagamentos WHERE academia_id=%s AND status='PAGO'",(aid(),)).fetchone()["n"],
      "aulas":con.cursor().execute("SELECT COUNT(*) n FROM aulas WHERE academia_id=%s AND ativo=1",(aid(),)).fetchone()["n"]
    }
    ac=con.cursor().execute("SELECT * FROM academias WHERE id=%s",(aid(),)).fetchone()
    con.close()
    return page("Painel","""
    <style>
.painel-area .muted{
    font-size:26px;
}
.painel-area .big{
    font-size:38px;
    font-weight:800;
}
.painel-area .card{
    padding:22px;
}
.painel-area a.btn{
    font-size:24px;
    font-weight:700;
    padding:18px 22px;
    min-height:62px;
    display:flex;
    align-items:center;
}
</style>

<div class="painel-area">
<h1>{{ac.nome}}</h1><p class="muted">Visão geral da academia · Plano {{ac.plano}}</p>
    <div class="grid">
      <div class="card"><div class="muted">Alunos ativos</div><div class="big">{{s.alunos}}</div></div>
      <div class="card"><div class="muted">Check-ins hoje</div><div class="big">{{s.checkins}}</div></div>
      <div class="card"><div class="muted">Receita registrada</div><div class="big">R$ {{'%.2f'|format(s.receita)}}</div></div>
      <div class="card"><div class="muted">Aulas cadastradas</div><div class="big">{{s.aulas}}</div></div>
    </div><br>
    <div class="grid"><a class="btn green" href="/alunos/novo">+ Novo aluno</a>
    <a class="btn" href="/checkin">✓ Fazer check-in</a><a class="btn" href="/financeiro">R$ Registrar pagamento</a></div>
</div>
    """,s=stats,ac=ac)


@app.route("/anuncios", methods=["GET","POST"])
@login_required
def anuncios():
    if str(session.get("perfil") or "").upper() != "DONO":
        flash("Somente o proprietário pode gerenciar anúncios.")
        return redirect("/")

    con = db()
    erro = ""
    sucesso = ""

    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        mensagem = request.form.get("mensagem", "").strip()

        if not titulo or not mensagem:
            erro = "Preencha o título e a mensagem."
        else:
            con.cursor().execute(
                """INSERT INTO avisos
                   (academia_id,titulo,mensagem,criado_em)
                   VALUES(%s,%s,%s,%s)""",
                (aid(), titulo, mensagem, agora())
            )
            con.commit()
            sucesso = "Anúncio publicado com sucesso."

    rows = con.cursor().execute(
        """SELECT *
           FROM avisos
           WHERE academia_id=%s
           ORDER BY id DESC""",
        (aid(),)
    ).fetchall()

    con.close()

    return page("Anúncios", """
    <h1>📢 Anúncios da Academia</h1>

    <p class="muted">
      Publique comunicados para os usuários desta academia.
      Disponível em todos os planos TatameOne.
    </p>

    {% if erro %}
    <div class="card" style="color:#dc2626;margin-bottom:18px">
      {{erro}}
    </div>
    {% endif %}

    {% if sucesso %}
    <div class="card" style="color:#16a34a;margin-bottom:18px">
      {{sucesso}}
    </div>
    {% endif %}

    <div class="card" style="margin-bottom:22px">
      <h2>➕ Novo anúncio</h2>

      <form method="post">
        <label>Título</label>
        <input name="titulo"
               maxlength="150"
               required
               placeholder="Ex.: Academia fechada no feriado">

        <label>Mensagem</label>
        <textarea name="mensagem"
                  rows="6"
                  required
                  placeholder="Digite o comunicado..."></textarea>

        <button class="green"
                style="width:100%;font-size:24px;
                       min-height:62px;font-weight:800">
          📢 Publicar anúncio
        </button>
      </form>
    </div>

    <h2>📋 Anúncios publicados</h2>

    {% for a in rows %}
    <div class="card" style="margin-bottom:14px">
      <h2>{{a.titulo}}</h2>

      <div style="font-size:19px;white-space:pre-wrap">
        {{a.mensagem}}
      </div>

      <p class="muted">{{a.criado_em}}</p>

      <a class="btn danger"
         href="/anuncios/{{a.id}}/excluir"
         onclick="return confirm('Excluir este anúncio?')">
        🗑️ Excluir
      </a>
    </div>
    {% else %}
    <div class="card">
      Nenhum anúncio publicado.
    </div>
    {% endfor %}
    """, rows=rows, erro=erro, sucesso=sucesso)


@app.route("/anuncios/<int:id>/excluir")
@login_required
def excluir_anuncio(id):
    if str(session.get("perfil") or "").upper() != "DONO":
        return redirect("/")

    con = db()

    con.cursor().execute(
        """DELETE FROM avisos
           WHERE id=%s
             AND academia_id=%s""",
        (id, aid())
    )

    con.commit()
    con.close()

    flash("Anúncio excluído.")
    return redirect("/anuncios")


@app.route("/alunos/foto/<int:id>")
@login_required
def aluno_foto(id):
    con=db()
    aluno=con.cursor().execute(
        """SELECT foto, foto_dados, foto_tipo
           FROM alunos
           WHERE id=%s AND academia_id=%s""",
        (id,aid())
    ).fetchone()
    con.close()

    if not aluno:
        return Response(status=404)

    if aluno["foto_dados"]:
        return Response(
            bytes(aluno["foto_dados"]),
            mimetype=aluno["foto_tipo"] or "image/jpeg",
            headers={"Cache-Control":"private, max-age=3600"}
        )

    # Compatibilidade temporaria com fotos antigas ainda existentes.
    if aluno["foto"]:
        caminho=os.path.join("static","alunos",aluno["foto"])
        if os.path.isfile(caminho):
            return send_from_directory(
                os.path.join("static","alunos"),
                aluno["foto"]
            )

    return Response(status=404)


@app.route("/alunos")
@login_required
@permissao_required("alunos")
def alunos():
    con=db()
    rows=con.cursor().execute("SELECT * FROM alunos WHERE academia_id=%s ORDER BY nome",(aid(),)).fetchall()
    pendentes=con.cursor().execute("SELECT * FROM pre_cadastros WHERE academia_id=%s AND status='PENDENTE' ORDER BY id DESC",(aid(),)).fetchall()
    con.close()
    link_publico=request.url_root.rstrip("/")+"/cadastro/"+str(aid())
    return page("Alunos","""
    <div class="actions">
<h1 style="flex:1">Alunos</h1>
{% if session.get('perfil','')|upper == 'DONO' %}
<a class="btn" href="/alunos/pdf">📄 PDF de Alunos</a>
{% endif %}
<a class="btn green" href="/alunos/novo">+ Novo aluno</a>
</div>
    <div class="card" style="margin:12px 0 18px">
      <h2>🔗 Cadastro do aluno em casa</h2>
      <p class="muted">O aluno pode preencher pelo navegador, sem instalar o aplicativo.</p>
      <input id="linkCadastro" readonly value="{{link_publico}}">
      <div class="actions">
        <button type="button" class="green" onclick="navigator.clipboard.writeText(document.getElementById('linkCadastro').value);this.innerText='✓ Link copiado'">Copiar link</button>
        <a class="btn" target="_blank" href="{{link_publico}}">Abrir formulário</a>
      </div>
    </div>
    {% if pendentes %}
    <div class="card" style="margin-bottom:18px"><h2>Cadastros aguardando aprovação</h2>
    {% for p in pendentes %}
      <div style="padding:14px 0;border-bottom:1px solid #eee">
        <b>{{p.nome}}</b><br><span class="muted">{{p.modalidade or 'Sem modalidade'}} · {{p.telefone or 'Sem telefone'}}</span>
        <div class="actions" style="margin-top:9px">
          <a class="btn green" href="/alunos/pre-cadastro/{{p.id}}/aprovar">✓ Aprovar</a>
          <a class="btn danger" href="/alunos/pre-cadastro/{{p.id}}/recusar">Recusar</a>
        </div>
      </div>
    {% endfor %}</div>
    {% endif %}
    <div style="overflow:auto"><table><tr><th>Nome</th><th>Modalidade</th><th>Telefone</th><th>Status</th><th>Ação</th></tr>
    {% for x in rows %}<tr>
    <td><a href="/alunos/{{x.id}}" style="color:inherit;text-decoration:none;display:block"><b>{{x.nome}}</b></a></td>
    <td>{{x.modalidade or '-'}}</td>
    <td>{{x.telefone or '-'}}</td>
    <td><span class="pill">{{'ATIVO' if x.ativo else 'INATIVO'}}</span></td>
    <td><a class="btn" href="/alunos/{{x.id}}">Abrir</a></td>
    </tr>{% endfor %}
    </table></div>""",rows=rows,pendentes=pendentes,link_publico=link_publico)


@app.route("/alunos/pdf")
@login_required
@permissao_required("alunos")
def alunos_pdf():
    if str(session.get("perfil") or "").upper() != "DONO":
        flash("Somente o proprietário pode gerar o relatório de alunos.")
        return redirect("/alunos")

    con = db()

    academia = con.cursor().execute(
        "SELECT id,nome,documento,telefone,endereco,logo FROM academias WHERE id=%s",
        (aid(),)
    ).fetchone()

    alunos_lista = con.cursor().execute(
        """SELECT nome,modalidade,telefone,ativo
           FROM alunos
           WHERE academia_id=%s
           ORDER BY nome""",
        (aid(),)
    ).fetchall()

    con.close()

    total = len(alunos_lista)
    ativos = sum(1 for x in alunos_lista if x["ativo"])
    inativos = total - ativos

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )

    styles = getSampleStyleSheet()

    titulo = ParagraphStyle(
        "TituloTatameOne",
        parent=styles["Heading1"],
        alignment=TA_CENTER,
        fontSize=18,
        leading=22,
        spaceAfter=5*mm
    )

    centro = ParagraphStyle(
        "CentroTatameOne",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=10,
        leading=14
    )

    elementos = []

    if academia and academia.get("logo"):
        logo_path = os.path.join("static", "logos", academia["logo"])
        if os.path.isfile(logo_path):
            try:
                img = Image(logo_path)
                img._restrictSize(35*mm, 22*mm)
                img.hAlign = "CENTER"
                elementos.append(img)
                elementos.append(Spacer(1, 3*mm))
            except Exception:
                pass

    nome_academia = academia["nome"] if academia else "Academia"

    elementos.append(Paragraph(nome_academia, titulo))
    elementos.append(Paragraph("<b>RELATÓRIO DE ALUNOS</b>", centro))
    elementos.append(Spacer(1, 3*mm))
    elementos.append(
        Paragraph(
            "Emitido em: " + datetime.now().strftime("%d/%m/%Y %H:%M"),
            centro
        )
    )
    elementos.append(Spacer(1, 6*mm))

    resumo = [
        ["TOTAL DE ALUNOS", "ATIVOS", "INATIVOS"],
        [str(total), str(ativos), str(inativos)]
    ]

    tabela_resumo = Table(
        resumo,
        colWidths=[55*mm, 55*mm, 55*mm]
    )

    tabela_resumo.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME", (0,1), (-1,1), "Helvetica-Bold"),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("TOPPADDING", (0,0), (-1,-1), 7),
    ]))

    elementos.append(tabela_resumo)
    elementos.append(Spacer(1, 7*mm))

    dados = [["Nº", "Aluno", "Modalidade", "Telefone", "Status"]]

    for numero, aluno in enumerate(alunos_lista, 1):
        dados.append([
            str(numero),
            str(aluno["nome"] or "-"),
            str(aluno["modalidade"] or "-"),
            str(aluno["telefone"] or "-"),
            "ATIVO" if aluno["ativo"] else "INATIVO"
        ])

    if not alunos_lista:
        dados.append(["-", "Nenhum aluno cadastrado", "-", "-", "-"])

    tabela = Table(
        dados,
        repeatRows=1,
        colWidths=[10*mm, 58*mm, 40*mm, 40*mm, 27*mm]
    )

    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("ALIGN", (0,0), (0,-1), "CENTER"),
        ("ALIGN", (-1,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("GRID", (0,0), (-1,-1), 0.35, colors.grey),
        ("ROWBACKGROUNDS", (0,1), (-1,-1),
         [colors.white, colors.HexColor("#f3f4f6")]),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))

    elementos.append(tabela)
    elementos.append(Spacer(1, 7*mm))
    elementos.append(
        Paragraph(
            "Documento gerado pelo sistema TatameOne.",
            centro
        )
    )

    doc.build(elementos)

    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="relatorio_alunos.pdf"
    )


@app.route("/cadastro/<int:academia_id>", methods=["GET","POST"])
def cadastro_publico(academia_id):
    con=db()
    ac=con.cursor().execute("SELECT * FROM academias WHERE id=%s AND ativo=1",(academia_id,)).fetchone()
    if not ac:
        con.close()
        return "Academia não encontrada.",404
    mods=con.cursor().execute("SELECT nome FROM modalidades WHERE academia_id=%s AND ativo=1 ORDER BY nome",(academia_id,)).fetchall()
    if request.method=="POST":
        f=request.form
        documento=(f.get("documento") or "").strip()

        # Se o CPF/Documento já pertence a um aluno, permite
        # atualizar somente a foto mediante confirmação dos dados.
        if documento:
            existente=con.cursor().execute(
                """SELECT id,nascimento,telefone FROM alunos
                   WHERE academia_id=%s
                     AND LOWER(TRIM(COALESCE(documento,'')))=LOWER(TRIM(%s))
                   LIMIT 1""",
                (academia_id,documento)
            ).fetchone()

            if existente:
                nascimento_informado=(f.get("nascimento") or "").strip()
                telefone_informado="".join(
                    c for c in (f.get("telefone") or "") if c.isdigit()
                )
                nascimento_salvo=(existente["nascimento"] or "").strip()
                telefone_salvo="".join(
                    c for c in (existente["telefone"] or "") if c.isdigit()
                )

                nascimento_ok=bool(
                    nascimento_salvo
                    and nascimento_informado
                    and nascimento_salvo == nascimento_informado
                )
                telefone_ok=bool(
                    telefone_salvo
                    and telefone_informado
                    and telefone_salvo == telefone_informado
                )

                if not (nascimento_ok or telefone_ok):
                    con.close()
                    return public_page("Confirmação necessária","""
                    <div class="card" style="max-width:620px;margin:7vh auto;text-align:center">
                      <div style="font-size:70px">🔒</div>
                      <h1>Não foi possível confirmar o cadastro</h1>
                      <p>O CPF/Documento já está cadastrado, mas a data de nascimento ou o telefone informado não corresponde ao cadastro existente.</p>
                      <div class="ok">Nenhum dado foi alterado.</div>
                    </div>""",ac)

                foto=request.files.get("foto_camera")
                if not foto or not foto.filename:
                    foto=request.files.get("foto")

                if not foto or not foto.filename:
                    con.close()
                    return public_page("Foto necessária","""
                    <div class="card" style="max-width:620px;margin:7vh auto;text-align:center">
                      <div style="font-size:70px">📷</div>
                      <h1>Envie uma nova foto</h1>
                      <p>Seu cadastro foi localizado. Volte ao formulário e tire uma foto ou escolha uma imagem da galeria.</p>
                      <div class="ok">Nenhum cadastro duplicado foi criado.</div>
                    </div>""",ac)

                ext=os.path.splitext(foto.filename)[1].lower()
                tipos={
                    ".jpg":"image/jpeg",
                    ".jpeg":"image/jpeg",
                    ".png":"image/png",
                    ".webp":"image/webp"
                }

                if ext not in tipos:
                    con.close()
                    return public_page("Foto inválida","""
                    <div class="card" style="max-width:620px;margin:7vh auto;text-align:center">
                      <div style="font-size:70px">⚠️</div>
                      <h1>Formato de foto não permitido</h1>
                      <p>Utilize uma imagem JPG, JPEG, PNG ou WEBP.</p>
                    </div>""",ac)

                foto_nome=secrets.token_hex(12)+ext
                foto_dados=foto.read()
                foto_tipo=tipos[ext]

                con.cursor().execute(
                    """UPDATE alunos
                       SET foto=%s, foto_dados=%s, foto_tipo=%s
                       WHERE id=%s AND academia_id=%s""",
                    (
                        foto_nome,
                        foto_dados,
                        foto_tipo,
                        existente["id"],
                        academia_id
                    )
                )
                con.commit()
                con.close()

                return public_page("Foto atualizada","""
                <div class="card" style="max-width:620px;margin:7vh auto;text-align:center">
                  <div style="font-size:70px">✅</div>
                  <h1>Foto atualizada com sucesso!</h1>
                  <p>Seu cadastro em <b>{{nome}}</b> foi localizado e sua nova foto foi salva.</p>
                  <div class="ok">Não foi criado um novo cadastro.</div>
                </div>""",ac,nome=ac["nome"])

        foto_nome=None
        foto_dados=None
        foto_tipo=None
        foto=request.files.get("foto_camera")
        if not foto or not foto.filename:
            foto=request.files.get("foto")

        if foto and foto.filename:
            ext=os.path.splitext(foto.filename)[1].lower()
            tipos={
                ".jpg":"image/jpeg",
                ".jpeg":"image/jpeg",
                ".png":"image/png",
                ".webp":"image/webp"
            }
            if ext in tipos:
                foto_nome=secrets.token_hex(12)+ext
                foto_dados=foto.read()
                foto_tipo=tipos[ext]

        con.cursor().execute("""INSERT INTO alunos(
            academia_id,nome,documento,nascimento,telefone,email,
            responsavel,telefone_responsavel,modalidade,graduacao,
            observacoes,qr_token,criado_em,endereco,
            contato_emergencia,telefone_emergencia,foto,foto_dados,foto_tipo,ativo)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)""",
            (
                academia_id,
                f["nome"],
                documento or None,
                f.get("nascimento"),
                f.get("telefone"),
                f.get("email"),
                f.get("responsavel"),
                f.get("telefone_responsavel"),
                f.get("modalidade"),
                f.get("graduacao"),
                f.get("observacoes"),
                secrets.token_hex(8),
                agora(),
                f.get("endereco"),
                f.get("contato_emergencia"),
                f.get("telefone_emergencia"),
                foto_nome,
                foto_dados,
                foto_tipo
            )
        )

        con.commit()
        con.close()

        return public_page("Cadastro concluído","""
        <div class="card" style="max-width:620px;margin:7vh auto;text-align:center">
          <div style="font-size:70px">✅</div>
          <h1>Cadastro realizado com sucesso!</h1>
          <p>Seu cadastro em <b>{{nome}}</b> foi concluído.</p>
          <div class="ok">Você já está cadastrado como aluno da academia.</div>
        </div>""",ac,nome=ac["nome"])

    con.close()
    return public_page("Cadastro de aluno","""
    <div class="card"><h1>Cadastro de aluno</h1>
    <p class="muted">Preencha seus dados. Não é necessário instalar o aplicativo.</p>
    <form method="post" enctype="multipart/form-data">
    <label>📷 Foto do aluno</label>
<div class="grid">
  <div>
    <label>📸 Tirar foto</label>
    <input type="file"
           name="foto_camera"
           accept="image/*"
           capture="environment">
  </div>
  <div>
    <label>🖼️ Escolher da galeria</label>
    <input type="file"
           name="foto"
           accept="image/jpeg,image/png,image/webp">
  </div>
</div>
    <label>Nome completo *</label><input name="nome" required>
    <div class="grid">
    <div><label>CPF/Documento</label><input name="documento"></div>
    <div><label>Data de nascimento</label><input type="date" name="nascimento"></div>
    <div><label>Telefone *</label><input name="telefone" required></div>
    <div><label>E-mail</label><input type="email" name="email"></div></div>
    <label>Endereço</label><input name="endereco" placeholder="Rua, número, bairro e cidade">
    <div class="grid">
    <div><label>Modalidade desejada</label><select name="modalidade"><option value="">Selecione</option>{% for m in mods %}<option>{{m.nome}}</option>{% endfor %}</select></div>
    <div><label>Graduação/Faixa</label><input name="graduacao"></div>
    <div><label>Responsável (se necessário)</label><input name="responsavel"></div>
    <div><label>Telefone do responsável</label><input name="telefone_responsavel"></div>
    <div><label>Contato de emergência</label><input name="contato_emergencia"></div>
    <div><label>Telefone de emergência</label><input name="telefone_emergencia"
               id="telefone_emergencia"
               placeholder="Telefone"></div></div>
    <label>Observações</label><textarea name="observacoes" rows="4"></textarea>
    <button type="submit">Enviar cadastro</button></form></div>""",ac,mods=mods)

@app.route("/alunos/pre-cadastro/<int:id>/aprovar")
@login_required
@permissao_required("alunos")
def aprovar_pre_cadastro(id):
    con=db()
    p=con.cursor().execute("SELECT * FROM pre_cadastros WHERE id=%s AND academia_id=%s AND status='PENDENTE'",(id,aid())).fetchone()
    if p:
        con.cursor().execute("""INSERT INTO alunos(academia_id,nome,documento,nascimento,telefone,email,responsavel,
        telefone_responsavel,modalidade,graduacao,observacoes,qr_token,criado_em,endereco,
        contato_emergencia,telefone_emergencia,foto,foto_dados,foto_tipo)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (aid(),p["nome"],p["documento"],p["nascimento"],p["telefone"],p["email"],p["responsavel"],
         p["telefone_responsavel"],p["modalidade"],p["graduacao"],p["observacoes"],secrets.token_hex(8),agora(),
         p["endereco"],p["contato_emergencia"],p["telefone_emergencia"],p["foto"],
         p["foto_dados"],p["foto_tipo"]))
        con.cursor().execute("UPDATE pre_cadastros SET status='APROVADO' WHERE id=%s",(id,))
        con.commit()
    con.close()
    return redirect("/alunos")

@app.route("/alunos/pre-cadastro/<int:id>/recusar")
@login_required
@permissao_required("alunos")
def recusar_pre_cadastro(id):
    con=db()
    con.cursor().execute("UPDATE pre_cadastros SET status='RECUSADO' WHERE id=%s AND academia_id=%s",(id,aid()))
    con.commit()
    con.close()
    return redirect("/alunos")

@app.route("/alunos/novo", methods=["GET","POST"])
@login_required
@permissao_required("alunos")
def aluno_novo():
    con=db()
    mods=con.cursor().execute("SELECT nome FROM modalidades WHERE academia_id=%s AND ativo=1 ORDER BY nome",(aid(),)).fetchall()

    if request.method=="POST":
        f=request.form

        foto_nome=None
        foto_dados=None
        foto_tipo=None
        foto=request.files.get("foto_camera")
        if not foto or not foto.filename:
            foto=request.files.get("foto")
        if foto and foto.filename:
            ext=os.path.splitext(foto.filename)[1].lower()
            tipos={
                ".jpg":"image/jpeg",
                ".jpeg":"image/jpeg",
                ".png":"image/png",
                ".webp":"image/webp"
            }
            if ext in tipos:
                foto_nome=secrets.token_hex(12)+ext
                foto_dados=foto.read()
                foto_tipo=tipos[ext]

        con.cursor().execute("""INSERT INTO alunos(
            academia_id,nome,documento,nascimento,telefone,email,
            responsavel,telefone_responsavel,modalidade,graduacao,
            observacoes,qr_token,criado_em,endereco,
            contato_emergencia,telefone_emergencia,foto,foto_dados,foto_tipo
        ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            aid(),
            f["nome"],
            f.get("documento"),
            f.get("nascimento"),
            f.get("telefone"),
            f.get("email"),
            f.get("responsavel"),
            f.get("telefone_responsavel"),
            f.get("modalidade"),
            f.get("graduacao"),
            f.get("observacoes"),
            secrets.token_hex(8),
            agora(),
            f.get("endereco"),
            f.get("contato_emergencia"),
            f.get("telefone_emergencia"),
            foto_nome,
            foto_dados,
            foto_tipo
        ))

        con.commit()
        con.close()
        return redirect("/alunos")

    con.close()

    return page("Novo aluno","""
    <h1>Novo aluno</h1>

    <div class="card">
    <form method="post" enctype="multipart/form-data">

    <label>📷 Foto do aluno</label>

    <div class="grid">
      <div>
        <label for="fotoCamera"
               class="btn green"
               style="display:block;text-align:center;padding:16px;cursor:pointer">
          📸 ABRIR CÂMERA
        </label>
        <input id="fotoCamera"
               type="file"
               name="foto_camera"
               accept="image/*"
               capture="environment"
               style="display:none"
               onchange="document.getElementById('statusCamera').innerText=this.files.length %s '✓ Foto tirada' : ''">
        <div id="statusCamera"
             style="margin-top:8px;color:#16a34a;font-weight:700"></div>
      </div>

      <div>
        <label for="fotoGaleria"
               class="btn"
               style="display:block;text-align:center;padding:16px;cursor:pointer">
          🖼️ ESCOLHER FOTO
        </label>
        <input id="fotoGaleria"
               type="file"
               name="foto"
               accept="image/jpeg,image/png,image/webp"
               style="display:none"
               onchange="document.getElementById('statusGaleria').innerText=this.files.length %s '✓ Foto selecionada' : ''">
        <div id="statusGaleria"
             style="margin-top:8px;color:#16a34a;font-weight:700"></div>
      </div>
    </div>

    <div class="grid">

      <div>
        <label>Nome completo *</label>
        <input name="nome" required>
      </div>

      <div>
        <label>CPF/Documento</label>
        <input name="documento">
      </div>

      <div>
        <label>Data de nascimento</label>
        <input type="date" name="nascimento">
      </div>

      <div>
        <label>Telefone / WhatsApp</label>
        <input name="telefone">
      </div>

      <div>
        <label>E-mail</label>
        <input type="email" name="email">
      </div>

      <div>
        <label>Modalidade</label>
        <select name="modalidade">
          <option value="">Selecione</option>
          {% for m in mods %}
          <option>{{m.nome}}</option>
          {% endfor %}
        </select>
      </div>

      <div>
        <label>Graduação / Faixa</label>
        <select name="graduacao" id="graduacao">
          <option value="">Selecione</option>
          <option value="Branca">⚪ Branca</option>
          <option value="Azul">🔵 Azul</option>
          <option value="Roxa">🟣 Roxa</option>
          <option value="Marrom">🟤 Marrom</option>
          <option value="Preta">⚫ Preta</option>
          <option value="Não se aplica">Não se aplica</option>
        </select>
      </div>

      <div>
        <label>Responsável</label>
        <input name="responsavel">
      </div>

      <div>
        <label>Telefone do responsável</label>
        <input name="telefone_responsavel">
      </div>

    </div>

    <label>Endereço</label>
    <input name="endereco"
           placeholder="Rua, número, bairro e cidade">

    <div class="grid">

      <div>
        <label>Contato de emergência</label>
        <select name="contato_emergencia"
                id="contato_emergencia"
                onchange="preencherEmergencia(this.value)">
          <option value="">Selecione</option>
          <option value="SAMU">🚑 SAMU — 192</option>
          <option value="Bombeiros">🚒 Bombeiros — 193</option>
          <option value="Polícia Militar">🚓 Polícia Militar — 190</option>
          <option value="Contato particular">👤 Contato particular</option>
        </select>
      </div>

      <div>
        <label>Telefone de emergência</label>
        <input name="telefone_emergencia" id="telefone_emergencia">
      </div>

    </div>

    <label>Observações</label>
    <textarea name="observacoes" rows="4"></textarea>

    <script>
function preencherEmergencia(tipo) {
    const telefone = document.getElementById("telefone_emergencia");

    const numeros = {
        "SAMU": "192",
        "Bombeiros": "193",
        "Polícia Militar": "190"
    };

    if (numeros[tipo]) {
        telefone.value = numeros[tipo];
    } else if (tipo === "Contato particular") {
        telefone.value = "";
        telefone.focus();
    }
}
</script>

    <button class="green">Salvar aluno</button>

    </form>
    </div>
    """,mods=mods)

@app.route("/alunos/<int:id>")
@login_required
@permissao_required("alunos")
def aluno(id):
    con=db()
    x=con.cursor().execute(
        "SELECT * FROM alunos WHERE id=%s AND academia_id=%s",
        (id,aid())
    ).fetchone()

    if not x:
        con.close()
        return "Aluno não encontrado",404

    pags=con.cursor().execute(
        "SELECT * FROM pagamentos WHERE aluno_id=%s AND academia_id=%s ORDER BY id DESC LIMIT 10",
        (id,aid())
    ).fetchall()

    checks=con.cursor().execute(
        "SELECT * FROM checkins WHERE aluno_id=%s AND academia_id=%s ORDER BY id DESC LIMIT 10",
        (id,aid())
    ).fetchall()

    con.close()

    # Gerar QR Code real do aluno
    qr_img = None
    if x.get("qr_token"):
        img = qrcode.make(x["qr_token"])
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_img = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()

    return page(x["nome"],"""
    <h1>{{x.nome}}</h1>

    <p>
      <span class="pill">
        {{x.modalidade or 'Sem modalidade'}}
      </span>
      {{x.graduacao or ''}}
    </p>

    <div class="card">
      <h2>👤 Dados do aluno</h2>

      {% if x.foto %}
      <div style="text-align:center;margin-bottom:20px">
        <img src="/alunos/foto/{{x.id}}"
             alt="Foto do aluno"
             style="width:150px;height:150px;
                    object-fit:cover;border-radius:18px;
                    border:3px solid #e5e7eb">
      </div>
      {% endif %}

      <div class="grid">

        <div>
          <b>Nome completo</b>
          <p>{{x.nome or '-'}}</p>
        </div>

        <div>
          <b>CPF/Documento</b>
          <p>{{x.documento or '-'}}</p>
        </div>

        <div>
          <b>Data de nascimento</b>
          <p>{{x.nascimento or '-'}}</p>
        </div>

        <div>
          <b>Telefone / WhatsApp</b>
          <p>{{x.telefone or '-'}}</p>
        </div>

        <div>
          <b>E-mail</b>
          <p>{{x.email or '-'}}</p>
        </div>

        <div>
          <b>Modalidade</b>
          <p>{{x.modalidade or '-'}}</p>
        </div>

        <div>
          <b>Graduação / Faixa</b>
          <p>{{x.graduacao or '-'}}</p>
        </div>

        <div>
          <b>Responsável</b>
          <p>{{x.responsavel or '-'}}</p>
        </div>

        <div>
          <b>Telefone do responsável</b>
          <p>{{x.telefone_responsavel or '-'}}</p>
        </div>

        <div>
          <b>Endereço</b>
          <p>{{x.endereco or '-'}}</p>
        </div>

        <div>
          <b>Contato de emergência</b>
          <p>{{x.contato_emergencia or '-'}}</p>
        </div>

        <div>
          <b>Telefone de emergência</b>
          <p>{{x.telefone_emergencia or '-'}}</p>
        </div>

      </div>

      <div style="margin-top:15px">
        <b>Observações</b>
        <p style="white-space:pre-wrap">
          {{x.observacoes or '-'}}
        </p>
      </div>
    </div>

    <br>

    <div class="card" style="text-align:center">
      <h2>📱 QR Code do aluno</h2>

      {% if qr_img %}
      <img src="{{qr_img}}"
           alt="QR Code do aluno"
           style="width:240px;max-width:80%;height:auto;margin:15px auto;display:block">

      <p class="muted">Apresente este QR Code no check-in</p>
      {% endif %}

      <p style="font-size:16px;word-break:break-all">
        <b>Token:</b> {{x.qr_token or '-'}}
      </p>
    </div>

    <br>

    <div class="card">
      <h2>Últimos check-ins</h2>

      {% for c in checks %}
        <p>{{c.entrada}}</p>
      {% else %}
        <p class="muted">Nenhum.</p>
      {% endfor %}
    </div>

    <br>

    <div class="card">
      <h2>Pagamentos</h2>

      {% for p in pags %}
        <p>
          {{p.referencia}} ·
          R$ {{'%.2f'|format(p.valor)}} ·
          {{p.forma}}
        </p>
      {% else %}
        <p class="muted">Nenhum.</p>
      {% endfor %}
    </div>

    <br>

    <div class="card">
      <h2>Gerenciar aluno</h2>

      <div class="actions">

        {% if x.ativo %}
        <form method="post"
              action="/alunos/{{x.id}}/desativar"
              onsubmit="return confirm('Deseja desativar este aluno? O histórico será preservado.')">
          <button type="submit" class="danger">
            🚫 Desativar aluno
          </button>
        </form>

        {% else %}

        <form method="post"
              action="/alunos/{{x.id}}/reativar"
              onsubmit="return confirm('Deseja reativar este aluno?')">
          <button type="submit" class="green">
            ✅ Reativar aluno
          </button>
        </form>

        {% endif %}

        <form method="post"
              action="/alunos/{{x.id}}/excluir"
              onsubmit="return confirm('ATENÇÃO: isto apagará definitivamente o aluno e seus dados relacionados. Deseja continuar?') && confirm('Última confirmação: excluir definitivamente {{x.nome}}?')">

          <button type="submit"
                  class="danger"
                  style="background:#7f1d1d!important">
            🗑️ Excluir definitivamente
          </button>

        </form>

      </div>

      <p class="muted" style="margin-bottom:0">
        Desativar preserva o histórico.
        Excluir definitivamente remove também os registros relacionados ao aluno.
      </p>
    </div>

    """,x=x,pags=pags,checks=checks,qr_img=qr_img)


@app.route("/alunos/<int:id>/desativar", methods=["POST"])
@login_required
@permissao_required("alunos")
def aluno_desativar(id):
    con=db()
    con.cursor().execute(
        "UPDATE alunos SET ativo=0 WHERE id=%s AND academia_id=%s",
        (id,aid())
    )
    con.commit()
    con.close()
    return redirect("/alunos/"+str(id))


@app.route("/alunos/<int:id>/reativar", methods=["POST"])
@login_required
@permissao_required("alunos")
def aluno_reativar(id):
    con=db()
    con.cursor().execute(
        "UPDATE alunos SET ativo=1 WHERE id=%s AND academia_id=%s",
        (id,aid())
    )
    con.commit()
    con.close()
    return redirect("/alunos/"+str(id))


@app.route("/alunos/<int:id>/excluir", methods=["POST"])
@login_required
@permissao_required("alunos")
def aluno_excluir(id):
    con=db()

    aluno=con.cursor().execute(
        "SELECT * FROM alunos WHERE id=%s AND academia_id=%s",
        (id,aid())
    ).fetchone()

    if not aluno:
        con.close()
        return "Aluno não encontrado",404

    # Remove somente dados pertencentes ao aluno
    # dentro da academia atualmente autenticada.
    for tabela in (
        "checkins",
        "pagamentos",
        "avaliacoes",
        "treinos",
        "matriculas"
    ):
        con.cursor().execute(
            f"DELETE FROM {tabela} WHERE aluno_id=%s AND academia_id=%s",
            (id,aid())
        )

    # Remove a foto armazenada, quando existir.
    foto=aluno["foto"] if "foto" in aluno.keys() else None

    con.cursor().execute(
        "DELETE FROM alunos WHERE id=%s AND academia_id=%s",
        (id,aid())
    )

    con.commit()
    con.close()

    if foto:
        caminho=os.path.join("static","alunos",foto)
        try:
            if os.path.isfile(caminho):
                os.remove(caminho)
        except OSError:
            pass

    return redirect("/alunos")


@app.route("/checkin", methods=["GET","POST"])
@login_required
@permissao_required("checkin")
def checkin():
    msg=""
    con=db()

    if request.method=="POST":
        busca=request.form["busca"].strip()

        x=con.cursor().execute("""
        SELECT * FROM alunos
        WHERE academia_id=%s
          AND ativo=1
          AND (qr_token=%s OR lower(nome) LIKE lower(%s))
        LIMIT 1
        """,(aid(),busca,"%"+busca+"%")).fetchone()

        if x:
            ultimo=con.cursor().execute("""
                SELECT entrada
                FROM checkins
                WHERE academia_id=%s AND aluno_id=%s
                ORDER BY id DESC
                LIMIT 1
            """,(aid(),x["id"])).fetchone()

            duplicado=False

            if ultimo and ultimo["entrada"]:
                try:
                    entrada_anterior=datetime.strptime(
                        ultimo["entrada"],
                        "%Y-%m-%d %H:%M:%S"
                    )
                    agora_dt=datetime.now()
                    segundos=(agora_dt-entrada_anterior).total_seconds()

                    if 0 <= segundos < 300:
                        duplicado=True
                except (ValueError, TypeError):
                    pass

            if duplicado:
                msg="⚠️ Check-in não registrado: "+x["nome"]+" já realizou check-in nos últimos 5 minutos."
            else:
                con.cursor().execute(
                    "INSERT INTO checkins(academia_id,aluno_id,entrada) VALUES(%s,%s,%s)",
                    (aid(),x["id"],agora())
                )
                con.commit()
                msg="✅ Check-in confirmado: "+x["nome"]
        else:
            msg="Aluno não encontrado ou inativo."

    recentes=con.cursor().execute("""
        SELECT c.id,c.entrada,a.nome
        FROM checkins c
        JOIN alunos a ON a.id=c.aluno_id
        WHERE c.academia_id=%s
        ORDER BY c.id DESC
        LIMIT 12
    """,(aid(),)).fetchall()

    con.close()

    return page("Check-in","""
    <h1>Check-in</h1>

    <div class="card">

      <form method="post" id="formCheckin">

        <label>Nome ou token do QR Code</label>

        <input
          id="buscaQR"
          name="busca"
          autofocus
          required
          placeholder="Digite o nome ou leia o QR">

        <div class="actions" style="margin-top:12px">

          <button class="green" type="submit">
            ✅ Confirmar entrada
          </button>

          <button
            id="btnCamera"
            type="button"
            onclick="abrirLeitorQR()">
            📷 Ler QR Code
          </button>

        </div>

      </form>

      {% if msg %}
        <h3>{{msg}}</h3>
      {% endif %}

      <div
        id="areaQR"
        style="display:none;margin-top:18px;text-align:center">

        <div
          id="reader"
          style="width:100%;max-width:450px;margin:auto">
        </div>

        <button
          type="button"
          class="danger"
          onclick="fecharLeitorQR()"
          style="margin-top:12px">
          ✕ Fechar câmera
        </button>

      </div>

    </div>

    <br>

    <div class="card">
      <h2>Recentes</h2>

      {% for r in recentes %}
        <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 0;border-bottom:1px solid #e5e7eb">

          <div>
            <b>{{r.nome}}</b><br>
            <span class="muted">{{r.entrada}}</span>
          </div>

          <form method="post"
                action="/checkin/{{r.id}}/excluir"
                onsubmit="return confirm('Excluir este check-in de {{r.nome}}?')">

            <button type="submit"
                    class="danger"
                    style="padding:9px 12px">
              🗑️ Excluir
            </button>

          </form>

        </div>
      {% else %}
        <p class="muted">Nenhum check-in recente.</p>
      {% endfor %}
    </div>

    <script src="https://unpkg.com/html5-qrcode"></script>

    <script>
    let leitorQR = null;
    let qrProcessado = false;

    async function abrirLeitorQR() {

        const area = document.getElementById("areaQR");
        const botao = document.getElementById("btnCamera");

        area.style.display = "block";
        botao.disabled = true;
        botao.innerText = "📷 Câmera aberta";
        qrProcessado = false;

        try {

            leitorQR = new Html5Qrcode("reader");

            await leitorQR.start(
                { facingMode: "environment" },
                {
                    fps: 10,
                    qrbox: { width: 250, height: 250 }
                },

                async function(texto) {

                    if (qrProcessado) return;
                    qrProcessado = true;

                    document.getElementById("buscaQR").value = texto;

                    try {
                        await leitorQR.stop();
                        leitorQR.clear();
                    } catch(e) {}

                    area.style.display = "none";

                    document.getElementById("formCheckin").submit();
                },

                function(erro) {
                }
            );

        } catch(e) {

            alert(
              "Não foi possível abrir a câmera. Verifique a permissão da câmera e se o site está usando HTTPS."
            );

            area.style.display = "none";
            botao.disabled = false;
            botao.innerText = "📷 Ler QR Code";
        }
    }

    async function fecharLeitorQR() {

        if (leitorQR) {
            try {
                await leitorQR.stop();
                leitorQR.clear();
            } catch(e) {}
        }

        leitorQR = null;
        qrProcessado = false;

        document.getElementById("areaQR").style.display = "none";

        const botao = document.getElementById("btnCamera");
        botao.disabled = false;
        botao.innerText = "📷 Ler QR Code";
    }
    </script>

    """,msg=msg,recentes=recentes)


@app.route("/checkin/<int:id>/excluir", methods=["POST"])
@login_required
@permissao_required("checkin")
def checkin_excluir(id):
    con=db()

    con.cursor().execute(
        "DELETE FROM checkins WHERE id=%s AND academia_id=%s",
        (id,aid())
    )

    con.commit()
    con.close()

    return redirect("/checkin")


@app.route("/planos", methods=["GET","POST"])
@login_required
@permissao_required("planos")
def planos():
    con=db()
    if request.method=="POST":
        con.cursor().execute("INSERT INTO planos(academia_id,nome,valor,periodicidade,descricao) VALUES(%s,%s,%s,%s,%s)",
                    (aid(),request.form["nome"],float(request.form["valor"] or 0),request.form["periodicidade"],request.form.get("descricao")))
        con.commit()
    rows=con.cursor().execute("SELECT * FROM planos WHERE academia_id=%s ORDER BY id DESC",(aid(),)).fetchall(); con.close()
    return page("Planos","""
    <h1>Planos</h1><div class="grid"><div class="card"><form method="post"><label>Nome</label><input name="nome" required>
    <label>Valor</label><input type="number" step=".01" name="valor" value="0"><label>Periodicidade</label>
    <select name="periodicidade"><option>MENSAL</option><option>TRIMESTRAL</option><option>SEMESTRAL</option><option>ANUAL</option><option>AVULSO</option></select>
    <label>Descrição</label><textarea name="descricao"></textarea><button class="green">Criar plano</button></form></div>
    <div class="card">
    {% for x in rows %}
      <div style="padding:14px 0;border-bottom:1px solid #ddd">
        <p style="margin:0 0 10px 0">
          <b>{{x.nome}}</b><br>
          R$ {{'%.2f'|format(x.valor)}} · {{x.periodicidade}}
        </p>

        {% if x.valor == 0 %}
          <span class="pill">🎁 Plano gratuito</span>
        {% endif %}

        <form method="post"
              action="/planos/{{x.id}}/excluir"
              style="display:inline"
              onsubmit="return confirm('Excluir o plano {{x.nome}}?');">
          <button type="submit"
                  class="danger"
                  style="margin-top:8px">
            🗑️ Excluir
          </button>
        </form>
      </div>
    {% else %}
      <p class="muted">Nenhum plano cadastrado.</p>
    {% endfor %}
    </div></div>""",rows=rows)

@app.route("/planos/<int:id>/excluir", methods=["POST"])
@login_required
@permissao_required("planos")
def plano_excluir(id):
    con=db()

    plano=con.cursor().execute(
        "SELECT * FROM planos WHERE id=%s AND academia_id=%s",
        (id,aid())
    ).fetchone()

    if plano:
        con.cursor().execute(
            "DELETE FROM planos WHERE id=%s AND academia_id=%s",
            (id,aid())
        )
        con.commit()

    con.close()
    return redirect("/planos")



# ============================================================
# PIX BR CODE / QR CODE
# ============================================================

def pix_campo(id_campo, valor):
    valor = str(valor or "")
    return f"{id_campo}{len(valor):02d}{valor}"


def pix_limpar_texto(texto, limite):
    import unicodedata

    texto = str(texto or "").strip().upper()

    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        c for c in texto
        if unicodedata.category(c) != "Mn"
    )

    permitido = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .-"
    texto = "".join(c for c in texto if c in permitido)

    return texto[:limite]


def pix_crc16(payload):
    polinomio = 0x1021
    resultado = 0xFFFF

    for byte in payload.encode("utf-8"):
        resultado ^= byte << 8

        for _ in range(8):
            if resultado & 0x8000:
                resultado = (
                    (resultado << 1) ^ polinomio
                ) & 0xFFFF
            else:
                resultado = (resultado << 1) & 0xFFFF

    return f"{resultado:04X}"


def gerar_pix_payload(chave, nome, cidade, valor, txid="***"):

    chave = str(chave or "").strip()
    nome = pix_limpar_texto(nome, 25)
    cidade = pix_limpar_texto(cidade, 15)

    try:
        valor = float(valor)
    except (ValueError, TypeError):
        valor = 0

    gui = pix_campo("00", "BR.GOV.BCB.PIX")
    chave_pix = pix_campo("01", chave)

    merchant_account = pix_campo(
        "26",
        gui + chave_pix
    )

    payload = (
        pix_campo("00", "01") +
        merchant_account +
        pix_campo("52", "0000") +
        pix_campo("53", "986")
    )

    if valor > 0:
        payload += pix_campo(
            "54",
            f"{valor:.2f}"
        )

    payload += (
        pix_campo("58", "BR") +
        pix_campo("59", nome or "RECEBEDOR") +
        pix_campo("60", cidade or "BRASIL") +
        pix_campo(
            "62",
            pix_campo("05", txid)
        )
    )

    payload_crc = payload + "6304"
    return payload_crc + pix_crc16(payload_crc)


@app.route("/financeiro/pix-cobranca")
@login_required
@permissao_required("financeiro")
def financeiro_pix_cobranca():

    valor = request.args.get("valor", "0")
    aluno_id = request.args.get("aluno_id", "")
    referencia = request.args.get("referencia", "")

    con = db()

    academia = con.cursor().execute("""
        SELECT *
        FROM academias
        WHERE id=%s
        LIMIT 1
    """, (aid(),)).fetchone()

    aluno = None

    if aluno_id:
        aluno = con.cursor().execute("""
            SELECT id,nome
            FROM alunos
            WHERE id=%s
              AND academia_id=%s
            LIMIT 1
        """, (aluno_id, aid())).fetchone()

    con.close()

    if not academia:
        return redirect("/financeiro")

    if not academia["pix_ativo"]:
        flash("O PIX não está ativado nas Configurações.")
        return redirect("/financeiro")

    if not academia["pix_chave"]:
        flash("Cadastre a chave PIX nas Configurações.")
        return redirect("/financeiro")

    try:
        valor_float = float(
            str(valor).replace(",", ".")
        )
    except (ValueError, TypeError):
        valor_float = 0

    if valor_float <= 0:
        flash("Informe um valor válido para gerar o PIX.")
        return redirect("/financeiro")

    payload = gerar_pix_payload(
        academia["pix_chave"],
        academia["pix_nome"] or academia["nome"],
        academia["pix_cidade"] or "BRASIL",
        valor_float
    )

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3
    )

    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")

    qr_base64 = base64.b64encode(
        buffer.getvalue()
    ).decode("ascii")

    return page("Pagamento PIX", """
    <h1>💳 Pagamento PIX</h1>

    <div class="card"
         style="max-width:520px;margin:auto;text-align:center">

        <h2>{{academia.nome}}</h2>

        {% if aluno %}
        <p>
            <b>Aluno:</b>
            {{aluno.nome}}
        </p>
        {% endif %}

        {% if referencia %}
        <p>
            <b>Mensalidade:</b>
            {{referencia}}
        </p>
        {% endif %}

        <div class="big">
            R$ {{'%.2f'|format(valor)}}
        </div>

        <p class="muted">
            Escaneie o QR Code com o aplicativo do banco
        </p>

        <img
            src="data:image/png;base64,{{qr_base64}}"
            alt="QR Code PIX"
            style="
                width:100%;
                max-width:320px;
                background:white;
                padding:10px;
                border-radius:12px;
            ">

        <h3>PIX Copia e Cola</h3>

        <textarea
            id="pixPayload"
            readonly
            style="
                width:100%;
                min-height:130px;
                font-size:13px;
                box-sizing:border-box;
            ">{{payload}}</textarea>

        <button
            type="button"
            class="green"
            onclick="copiarPix()"
            style="width:100%;margin-top:10px">
            📋 Copiar código PIX
        </button>

        <div id="copiado"
             style="
                display:none;
                margin-top:10px;
                font-weight:bold;
            ">
            ✅ Código PIX copiado
        </div>

        <p style="margin-top:20px">
            <b>Chave PIX:</b><br>
            {{academia.pix_chave}}
        </p>

        <p class="muted">
            Após confirmar o recebimento no banco,
            volte ao Financeiro e registre o pagamento.
        </p>

        <a
            class="btn green"
            href="/financeiro"
            style="
                display:block;
                text-align:center;
                text-decoration:none;
                margin-top:15px;
            ">
            ← Voltar e registrar pagamento
        </a>

    </div>

    <script>
    function copiarPix(){

        const campo =
            document.getElementById("pixPayload");

        if(navigator.clipboard &&
           navigator.clipboard.writeText){

            navigator.clipboard
                .writeText(campo.value)
                .then(function(){
                    document.getElementById(
                        "copiado"
                    ).style.display="block";
                });

        }else{

            campo.select();
            document.execCommand("copy");

            document.getElementById(
                "copiado"
            ).style.display="block";
        }
    }
    </script>
    """,
    academia=academia,
    aluno=aluno,
    referencia=referencia,
    valor=valor_float,
    payload=payload,
    qr_base64=qr_base64)



@app.route("/financeiro", methods=["GET","POST"])
@login_required
@permissao_required("financeiro")
def financeiro():
    con=db()

    alunos=con.cursor().execute(
        "SELECT id,nome FROM alunos WHERE academia_id=%s AND ativo=1 ORDER BY nome",
        (aid(),)
    ).fetchall()

    # Cria referências inteligentes: mês anterior, atual e próximos 12 meses.
    hoje=datetime.now()
    referencias=[]

    nomes_meses=[
        "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
        "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"
    ]

    for deslocamento in range(-1,13):
        total_meses=(hoje.year * 12 + hoje.month - 1) + deslocamento
        ano=total_meses // 12
        mes=(total_meses % 12) + 1

        referencias.append({
            "valor":f"{mes:02d}/{ano}",
            "nome":f"{nomes_meses[mes-1]}/{ano}"
        })

    msg=""

    if request.method=="POST":
        f=request.form

        aluno_id=f["aluno_id"]
        referencia=f["referencia"]

        # Impede mensalidade duplicada.
        existente=con.cursor().execute("""
            SELECT id
            FROM pagamentos
            WHERE academia_id=%s
              AND aluno_id=%s
              AND referencia=%s
              AND status='PAGO'
            LIMIT 1
        """,(aid(),aluno_id,referencia)).fetchone()

        if existente:
            msg="⚠️ Esta mensalidade já foi registrada para este aluno."
        else:
            try:
                valor=float(str(f["valor"]).replace(",","."))
            except (ValueError,TypeError):
                valor=0

            con.cursor().execute("""
                INSERT INTO pagamentos(
                    academia_id,aluno_id,referencia,
                    valor,forma,status,pago_em
                )
                VALUES(%s,%s,%s,%s,%s,'PAGO',%s)
            """,(
                aid(),
                aluno_id,
                referencia,
                valor,
                f["forma"],
                agora()
            ))

            con.cursor().execute("""
                INSERT INTO caixa(
                    academia_id,tipo,descricao,
                    valor,forma,data
                )
                VALUES(%s,'ENTRADA',%s,%s,%s,%s)
            """,(
                aid(),
                "Mensalidade "+referencia,
                valor,
                f["forma"],
                agora()
            ))

            con.commit()
            msg="✅ Pagamento registrado com sucesso."

    pags=con.cursor().execute("""
        SELECT p.*,a.nome
        FROM pagamentos p
        JOIN alunos a ON a.id=p.aluno_id
        WHERE p.academia_id=%s
        ORDER BY p.id DESC
        LIMIT 30
    """,(aid(),)).fetchall()

    total=con.cursor().execute("""
        SELECT COALESCE(SUM(valor),0)n
        FROM pagamentos
        WHERE academia_id=%s AND status='PAGO'
    """,(aid(),)).fetchone()["n"]

    con.close()

    return page("Financeiro","""
    <h1>Financeiro</h1>

    <div class="card">
      <div class="muted">Total recebido</div>
      <div class="big">R$ {{'%.2f'|format(total)}}</div>
    </div>

    <br>

    <div class="grid">

      <div class="card">
        <h2>Registrar pagamento</h2>

        {% if msg %}
          <div style="font-weight:bold;margin-bottom:15px">
            {{msg}}
          </div>
        {% endif %}

        <form method="post">

          <label>Aluno</label>
          <select name="aluno_id" required>
            {% for a in alunos %}
              <option value="{{a.id}}">{{a.nome}}</option>
            {% endfor %}
          </select>

          <label>Referência</label>
          <select name="referencia" required>
            {% for r in referencias %}
              <option value="{{r.valor}}"
                {% if r.valor == referencia_atual %}selected{% endif %}>
                {{r.nome}}
              </option>
            {% endfor %}
          </select>

          <div class="muted" style="margin-top:5px;margin-bottom:10px">
            📅 Competência da mensalidade
          </div>

          <label>Valor</label>
          <input
            type="number"
            step=".01"
            min="0"
            name="valor"
            required>

          <label>Forma</label>
          <select name="forma">
            <option>PIX</option>
            <option>DINHEIRO</option>
            <option>DÉBITO</option>
            <option>CRÉDITO</option>
            <option>BOLETO</option>
          </select>

          <button class="green" type="submit">
            ✅ Registrar pagamento
          </button>

          <button
            type="button"
            onclick="gerarPixFinanceiro(this.form)"
            style="
                width:100%;
                margin-top:10px;
                min-height:52px;
                font-size:17px;
                font-weight:bold;
            ">
            💳 GERAR PIX / QR CODE
          </button>

          <script>
          function gerarPixFinanceiro(form){

              const aluno =
                  form.querySelector('[name="aluno_id"]').value;

              const referencia =
                  form.querySelector('[name="referencia"]').value;

              const valor =
                  form.querySelector('[name="valor"]').value;

              const forma =
                  form.querySelector('[name="forma"]').value;

              if(!valor || parseFloat(valor) <= 0){
                  alert("Informe o valor da mensalidade.");
                  return;
              }

              if(forma !== "PIX"){
                  alert("Selecione PIX como forma de pagamento.");
                  return;
              }

              const url =
                  "/financeiro/pix-cobranca" +
                  "?aluno_id=" + encodeURIComponent(aluno) +
                  "&referencia=" + encodeURIComponent(referencia) +
                  "&valor=" + encodeURIComponent(valor);

              window.location.href = url;
          }
          </script>

        </form>
      </div>

      <div class="card">
        <h2>Últimos recebimentos</h2>

        {% for p in pags %}
          <div style="padding:14px 0;border-bottom:1px solid #ddd">

            <p style="margin:0 0 10px 0">
              <b>{{p.nome}}</b> · R$ {{'%.2f'|format(p.valor)}}<br>
              <span class="muted">
                {{p.referencia}} · {{p.forma}} · {{p.pago_em}}
              </span>
            </p>

            <a href="/financeiro/{{p.id}}/comprovante"
               class="btn green"
               style="display:inline-block;margin:5px 8px 5px 0;text-decoration:none">
              🧾 Comprovante
            </a>

            <form method="post"
                  action="/financeiro/{{p.id}}/excluir"
                  style="display:inline"
                  onsubmit="return confirm('Excluir este recebimento? O valor também será retirado do financeiro.');">

              <button type="submit"
                      class="danger"
                      style="margin-top:5px">
                🗑️ Excluir
              </button>

            </form>

          </div>
        {% else %}
          <p class="muted">Nenhum recebimento registrado.</p>
        {% endfor %}
      </div>

    </div>
    """,
    alunos=alunos,
    pags=pags,
    total=total,
    referencias=referencias,
    referencia_atual=f"{hoje.month:02d}/{hoje.year}",
    msg=msg)




@app.route("/financeiro/<int:id>/comprovante")
@login_required
@permissao_required("financeiro")
def financeiro_comprovante(id):
    con = db()

    pagamento = con.cursor().execute("""
        SELECT
            p.*,
            a.nome AS aluno_nome
        FROM pagamentos p
        JOIN alunos a
          ON a.id = p.aluno_id
         AND a.academia_id = p.academia_id
        WHERE p.id=%s
          AND p.academia_id=%s
        LIMIT 1
    """, (id, aid())).fetchone()

    academia = con.cursor().execute("""
        SELECT *
        FROM academias
        WHERE id=%s
        LIMIT 1
    """, (aid(),)).fetchone()

    con.close()

    if not pagamento:
        flash("Comprovante não encontrado.")
        return redirect("/financeiro")

    return page("Comprovante", """
<style>

.recibo-wrap{
    max-width:430px;
    margin:0 auto;
}

.recibo{
    background:white;
    color:#000;
    padding:18px;
    border:2px dashed #777;
    font-family:Arial,sans-serif;
}

.recibo-cabecalho{
    text-align:center;
}

.recibo-logo{
    display:block;
    max-width:150px;
    max-height:85px;
    width:auto;
    height:auto;
    object-fit:contain;
    margin:0 auto 8px auto;
}

.recibo-cabecalho h2{
    margin:4px 0;
    font-size:22px;
}

.recibo-titulo{
    font-weight:900;
    font-size:16px;
    margin-top:10px;
}

.recibo-linha{
    border-top:1px dashed #555;
    margin:14px 0;
}

.recibo-info{
    line-height:1.8;
    font-size:15px;
}

.recibo-valor{
    text-align:center;
    font-size:30px;
    font-weight:900;
    margin:15px 0;
}

.recibo-final{
    text-align:center;
    font-size:14px;
}

.acoes-recibo{
    max-width:430px;
    margin:18px auto;
}

.acoes-recibo button,
.acoes-recibo a{
    display:block;
    width:100%;
    box-sizing:border-box;
    text-align:center;
    text-decoration:none;
    margin:10px 0;
    min-height:52px;
    font-size:17px;
    font-weight:bold;
}

@media print{

    @page{
        size:58mm auto;
        margin:2mm;
    }

    body{
        margin:0 !important;
        padding:0 !important;
        background:white !important;
    }

    body *{
        visibility:hidden !important;
    }

    #recibo,
    #recibo *{
        visibility:visible !important;
    }

    #recibo{
        position:absolute;
        left:0;
        top:0;
        width:54mm !important;
        max-width:54mm !important;
        box-sizing:border-box;
        margin:0 !important;
        padding:2mm !important;
        border:0 !important;
        font-family:monospace !important;
        font-size:10px !important;
    }

    #recibo .recibo-logo{
        display:block !important;
        max-width:34mm !important;
        max-height:18mm !important;
        width:auto !important;
        height:auto !important;
        object-fit:contain !important;
        margin:0 auto 2mm auto !important;
    }

    #recibo h2{
        font-size:15px !important;
    }

    #recibo .recibo-titulo{
        font-size:11px !important;
    }

    #recibo .recibo-info{
        font-size:10px !important;
        line-height:1.5 !important;
    }

    #recibo .recibo-valor{
        font-size:18px !important;
    }

    #recibo .recibo-final{
        font-size:9px !important;
    }

    .acoes-recibo{
        display:none !important;
    }
}

</style>

<div class="recibo-wrap">

<div id="recibo" class="recibo">

    <div class="recibo-cabecalho">

        {% if academia.logo %}
        <img class="recibo-logo"
             src="/static/logos/{{academia.logo}}"
             alt="Logo {{academia.nome}}">
        {% endif %}

        <h2>{{ academia.nome }}</h2>

        {% if academia.documento %}
        <div>{{ academia.documento }}</div>
        {% endif %}

        {% if academia.telefone %}
        <div>{{ academia.telefone }}</div>
        {% endif %}

        {% if academia.endereco %}
        <div>{{ academia.endereco }}</div>
        {% endif %}

        <div class="recibo-titulo">
            COMPROVANTE DE PAGAMENTO
        </div>

    </div>

    <div class="recibo-linha"></div>

    <div class="recibo-info">

        <b>Comprovante:</b>
        #{{ pagamento.id }}
        <br>

        <b>Aluno:</b>
        {{ pagamento.aluno_nome }}
        <br>

        <b>Mensalidade:</b>
        {{ pagamento.referencia }}
        <br>

        <b>Forma:</b>
        {{ pagamento.forma }}
        <br>

        <b>Data/Hora:</b>
        {{ pagamento.pago_em }}

    </div>

    <div class="recibo-linha"></div>

    <div class="recibo-valor">
        R$ {{ '%.2f'|format(pagamento.valor) }}
    </div>

    <div class="recibo-linha"></div>

    <div class="recibo-final">
        PAGAMENTO RECEBIDO
        <br><br>
        Obrigado!
        <br>
        Sistema TatameOne
    </div>

</div>

</div>

<div class="acoes-recibo">

    <button class="green"
            type="button"
            onclick="window.print()">
        🖨️ Imprimir comprovante
    </button>

    <button type="button"
            onclick="imprimirBluetooth()">
        📱 Impressora Bluetooth
    </button>

    <a class="btn"
       href="/financeiro">
        ← Voltar ao Financeiro
    </a>

</div>

<script>

function textoComprovante(){

    return [
        "{{ academia.nome|e }}",
        "COMPROVANTE DE PAGAMENTO",
        "------------------------------",
        "Comprovante: #{{ pagamento.id }}",
        "Aluno: {{ pagamento.aluno_nome|e }}",
        "Mensalidade: {{ pagamento.referencia|e }}",
        "Forma: {{ pagamento.forma|e }}",
        "Data/Hora: {{ pagamento.pago_em|e }}",
        "------------------------------",
        "R$ {{ '%.2f'|format(pagamento.valor) }}",
        "------------------------------",
        "PAGAMENTO RECEBIDO",
        "",
        "Obrigado!",
        "Sistema TatameOne",
        "",
        "",
        ""
    ].join("\\n");

}

function imprimirBluetooth(){

    const texto = textoComprovante();

    try{

        const bytes =
            new TextEncoder().encode(texto);

        let binario = "";

        bytes.forEach(function(b){
            binario += String.fromCharCode(b);
        });

        const base64 = btoa(binario);

        window.location.href =
            "rawbt:base64," + base64;

    }catch(erro){

        window.print();

    }

}

</script>
""",
    pagamento=pagamento,
    academia=academia)


@app.route("/financeiro/<int:id>/excluir", methods=["POST"])
@login_required
@permissao_required("financeiro")
def financeiro_excluir(id):
    con=db()

    pagamento=con.cursor().execute("""
        SELECT *
        FROM pagamentos
        WHERE id=%s AND academia_id=%s
    """,(id,aid())).fetchone()

    if pagamento:

        # Procura somente UMA entrada correspondente no caixa.
        caixa=con.cursor().execute("""
            SELECT id
            FROM caixa
            WHERE academia_id=%s
              AND tipo='ENTRADA'
              AND descricao=%s
              AND valor=%s
              AND forma=%s
              AND data=%s
            ORDER BY id DESC
            LIMIT 1
        """,(
            aid(),
            "Mensalidade "+pagamento["referencia"],
            pagamento["valor"],
            pagamento["forma"],
            pagamento["pago_em"]
        )).fetchone()

        if caixa:
            con.cursor().execute("""
                DELETE FROM caixa
                WHERE id=%s AND academia_id=%s
            """,(caixa["id"],aid()))

        con.cursor().execute("""
            DELETE FROM pagamentos
            WHERE id=%s AND academia_id=%s
        """,(id,aid()))

        con.commit()

    con.close()
    return redirect("/financeiro")



# ============================================================
# PROFESSORES
# ============================================================

@app.route("/professores", methods=["GET","POST"])
@login_required
@permissao_required("aulas")
def professores():
    con = db()
    erro = ""
    sucesso = ""

    if request.method == "POST":
        nome = request.form.get("nome","").strip()
        telefone = request.form.get("telefone","").strip()
        email = request.form.get("email","").strip().lower()
        especialidades = [
            x.strip()
            for x in request.form.getlist("especialidades")
            if x.strip()
        ]
        especialidade = ",".join(especialidades)

        if not nome:
            erro = "Informe o nome do professor."
        else:
            existente = con.cursor().execute(
                """SELECT id
                   FROM professores
                   WHERE academia_id=%s
                   AND lower(trim(nome))=lower(trim(%s))
                   AND ativo=1
                   LIMIT 1""",
                (aid(),nome)
            ).fetchone()

            if existente:
                erro = "Já existe um professor ativo com este nome."
            else:
                con.cursor().execute(
                    """INSERT INTO professores
                       (academia_id,nome,telefone,email,especialidade,ativo)
                       VALUES(%s,%s,%s,%s,%s,1)""",
                    (aid(),nome,telefone,email,especialidade)
                )
                con.commit()
                sucesso = "Professor cadastrado com sucesso."

    rows = con.cursor().execute(
        """SELECT id,nome,telefone,email,especialidade,ativo
           FROM professores
           WHERE academia_id=%s
           ORDER BY ativo DESC,nome""",
        (aid(),)
    ).fetchall()

    modalidades = con.cursor().execute(
        """SELECT id,nome
           FROM modalidades
           WHERE academia_id=%s AND ativo=1
           ORDER BY nome""",
        (aid(),)
    ).fetchall()

    con.close()

    return page("Professores","""
    <h1>👨‍🏫 Professores</h1>

    {% if erro %}
    <div class="card"
         style="color:#dc2626;margin-bottom:18px">
      {{erro}}
    </div>
    {% endif %}

    {% if sucesso %}
    <div class="card"
         style="color:#16a34a;margin-bottom:18px">
      {{sucesso}}
    </div>
    {% endif %}

    <div class="grid">

      <div class="card">

        <h2>➕ Novo professor</h2>

        <form method="post">

          <label>Nome</label>
          <input name="nome" required>

          <label>Telefone</label>
          <input name="telefone">

          <label>E-mail</label>
          <input name="email" type="email">

          <label>Especialidades</label>

          <div class="card"
               style="box-shadow:none;border:1px solid #ddd;margin-bottom:18px">

            {% for m in modalidades %}

            <label style="display:block;margin-bottom:14px">
              <input type="checkbox"
                     name="especialidades"
                     value="{{m.nome}}"
                     style="width:auto;margin-right:10px">
              🥋 {{m.nome}}
            </label>

            {% else %}

            <p class="muted">
              Nenhuma modalidade cadastrada.
              Cadastre modalidades nas Configurações.
            </p>

            {% endfor %}

          </div>

          <button class="green"
                  style="width:100%">
            Cadastrar professor
          </button>

        </form>

      </div>

      <div class="card">

        <h2>👥 Professores cadastrados</h2>

        {% for p in rows %}

        <div style="padding:18px 0;
                    border-bottom:1px solid #ddd">

          <b style="font-size:24px">
            {{p.nome}}
          </b>

          {% if p.especialidade %}
          <p>🥋 {{p.especialidade}}</p>
          {% endif %}

          {% if p.telefone %}
          <p>📱 {{p.telefone}}</p>
          {% endif %}

          {% if p.email %}
          <p>✉️ {{p.email}}</p>
          {% endif %}

          {% if p.ativo %}
            <span class="pill">ATIVO</span>
          {% else %}
            <span class="pill">INATIVO</span>
          {% endif %}

          <div class="actions"
               style="margin-top:18px">

            <a class="btn"
               href="/professores/{{p.id}}/editar">
              ✏️ Editar
            </a>

            <form method="post"
                  action="/professores/{{p.id}}/status"
                  style="margin:0">

              {% if p.ativo %}

              <button type="submit"
                      class="danger">
                ⛔ Desativar
              </button>

              {% else %}

              <button type="submit"
                      class="green">
                ✅ Ativar
              </button>

              {% endif %}

            </form>

          </div>

        </div>

        {% else %}

        <p class="muted">
          Nenhum professor cadastrado.
        </p>

        {% endfor %}

      </div>

    </div>
    """,
    rows=rows,
    modalidades=modalidades,
    erro=erro,
    sucesso=sucesso)


@app.route("/professores/<int:id>/editar",
           methods=["GET","POST"])
@login_required
@permissao_required("aulas")
def professor_editar(id):

    con = db()

    prof = con.cursor().execute(
        """SELECT id,nome,telefone,email,
                  especialidade,ativo
           FROM professores
           WHERE id=%s AND academia_id=%s""",
        (id,aid())
    ).fetchone()

    if not prof:
        con.close()
        return redirect("/professores")

    erro = ""

    if request.method == "POST":

        nome = request.form.get("nome","").strip()
        telefone = request.form.get("telefone","").strip()
        email = request.form.get("email","").strip().lower()
        especialidades = [
            x.strip()
            for x in request.form.getlist("especialidades")
            if x.strip()
        ]
        especialidade = ",".join(especialidades)

        if not nome:
            erro = "Informe o nome do professor."

        else:

            con.cursor().execute(
                """UPDATE professores
                   SET nome=%s,
                       telefone=%s,
                       email=%s,
                       especialidade=%s
                   WHERE id=%s
                   AND academia_id=%s""",
                (
                    nome,
                    telefone,
                    email,
                    especialidade,
                    id,
                    aid()
                )
            )

            con.commit()
            con.close()

            return redirect("/professores")

    modalidades = con.cursor().execute(
        """SELECT id,nome
           FROM modalidades
           WHERE academia_id=%s AND ativo=1
           ORDER BY nome""",
        (aid(),)
    ).fetchall()

    con.close()

    return page("Editar professor","""

    <h1>✏️ Editar professor</h1>

    {% if erro %}
    <div class="card"
         style="color:#dc2626;margin-bottom:18px">
      {{erro}}
    </div>
    {% endif %}

    <div class="card">

      <form method="post">

        <label>Nome</label>
        <input name="nome"
               value="{{p.nome}}"
               required>

        <label>Telefone</label>
        <input name="telefone"
               value="{{p.telefone or ''}}">

        <label>E-mail</label>
        <input name="email"
               type="email"
               value="{{p.email or ''}}">

        <label>Especialidades</label>

        {% set atuais = (p.especialidade or '').split(',') %}

        <div class="card"
             style="box-shadow:none;border:1px solid #ddd;margin-bottom:18px">

          {% for m in modalidades %}

          <label style="display:block;margin-bottom:14px">
            <input type="checkbox"
                   name="especialidades"
                   value="{{m.nome}}"
                   style="width:auto;margin-right:10px"
                   {% if m.nome in atuais %}checked{% endif %}>
            🥋 {{m.nome}}
          </label>

          {% else %}

          <p class="muted">
            Nenhuma modalidade cadastrada.
          </p>

          {% endfor %}

        </div>

        <button class="green"
                style="width:100%">
          Salvar alterações
        </button>

      </form>

    </div>

    """,
    p=prof,
    modalidades=modalidades,
    erro=erro)


@app.route("/professores/<int:id>/status",
           methods=["POST"])
@login_required
@permissao_required("aulas")
def professor_status(id):

    con = db()

    prof = con.cursor().execute(
        """SELECT id,ativo
           FROM professores
           WHERE id=%s AND academia_id=%s""",
        (id,aid())
    ).fetchone()

    if prof:

        novo_status = 0 if prof["ativo"] else 1

        con.cursor().execute(
            """UPDATE professores
               SET ativo=%s
               WHERE id=%s
               AND academia_id=%s""",
            (novo_status,id,aid())
        )

        con.commit()

    con.close()

    return redirect("/professores")


@app.route("/aulas", methods=["GET","POST"])
@login_required
@permissao_required("aulas")
def aulas():
    con = db()
    erro = ""

    if request.method == "POST":
        f = request.form

        modalidade = f.get("modalidade","").strip()
        professor = f.get("professor","").strip()
        semana = f.get("semana","TODAS").strip().upper()

        if semana not in ("TODAS","A","B"):
            semana = "TODAS"

        ordem_dias = [
            "Segunda","Terça","Quarta","Quinta",
            "Sexta","Sábado","Domingo"
        ]

        dias = [
            d for d in ordem_dias
            if d in request.form.getlist("dias")
        ]

        horarios_entrada = request.form.getlist("horarios")

        horarios = []
        for h in horarios_entrada:
            h = h.strip()
            if h and h not in horarios:
                horarios.append(h)

        try:
            capacidade = int(f.get("capacidade") or 20)
        except (ValueError, TypeError):
            capacidade = 20

        professor_valido = True

        if professor:
            prof = con.cursor().execute(
                """SELECT especialidade
                   FROM professores
                   WHERE academia_id=%s
                     AND nome=%s
                     AND ativo=1""",
                (aid(),professor)
            ).fetchone()

            if not prof:
                professor_valido = False
            else:
                especialidades = [
                    x.strip()
                    for x in str(prof["especialidade"] or "").split(",")
                    if x.strip()
                ]
                if modalidade not in especialidades:
                    professor_valido = False

        if not modalidade:
            erro = "Selecione a modalidade."
        elif not professor_valido:
            erro = "Este professor não possui a especialidade da modalidade selecionada."
        elif not dias:
            erro = "Selecione pelo menos um dia."
        elif not horarios:
            erro = "Informe pelo menos um horário."
        elif capacidade < 1:
            erro = "A capacidade deve ser de pelo menos 1 aluno."
        else:
            dias_texto = " / ".join(dias)
            horarios_texto = " / ".join(horarios)

            con.cursor().execute(
                """INSERT INTO aulas
                   (academia_id,modalidade,professor,dia,
                    horario,capacidade,semana)
                   VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (
                    aid(), modalidade, professor,
                    dias_texto, horarios_texto,
                    capacidade, semana
                )
            )
            con.commit()

    rows = con.cursor().execute(
        """SELECT a.*,
                  (
                    SELECT COUNT(*)
                    FROM alunos al
                    WHERE al.academia_id=a.academia_id
                      AND al.ativo=1
                      AND lower(trim(COALESCE(al.modalidade,''))) =
                          lower(trim(COALESCE(a.modalidade,'')))
                  ) AS alunos_modalidade,
                  GREATEST(
                    a.capacidade - (
                      SELECT COUNT(*)
                      FROM alunos al
                      WHERE al.academia_id=a.academia_id
                        AND al.ativo=1
                        AND lower(trim(COALESCE(al.modalidade,''))) =
                            lower(trim(COALESCE(a.modalidade,'')))
                    ),
                    0
                  ) AS vagas_disponiveis
           FROM aulas a
           WHERE a.academia_id=%s
           ORDER BY a.ativo DESC,a.id DESC""",
        (aid(),)
    ).fetchall()

    mods = con.cursor().execute(
        """SELECT *
           FROM modalidades
           WHERE academia_id=%s
           ORDER BY nome""",
        (aid(),)
    ).fetchall()

    professores = con.cursor().execute(
        """SELECT id,nome,especialidade
           FROM professores
           WHERE academia_id=%s AND ativo=1
           ORDER BY nome""",
        (aid(),)
    ).fetchall()

    con.close()

    return page("Aulas","""
    <h1>📅 Agenda de aulas</h1>

    {% if erro %}
    <div class="card" style="color:#dc2626;margin-bottom:18px">
      {{erro}}
    </div>
    {% endif %}

    <div class="grid">
      <div class="card">
        <form method="post">

          <label>Modalidade</label>
          <select name="modalidade"
                  id="modalidade_aula"
                  required
                  onchange="filtrarProfessores()">
            <option value="">Selecione</option>
            {% for m in mods %}
            <option value="{{m.nome}}">{{m.nome}}</option>
            {% endfor %}
          </select>

          <label>Professor</label>
          <select name="professor"
                  id="professor_aula"
                  disabled>
            <option value="">Primeiro selecione a modalidade</option>
            {% for p in professores %}
            <option value="{{p.nome}}"
                    data-especialidades="{{p.especialidade or ''}}"
                    hidden>
              {{p.nome}}
            </option>
            {% endfor %}
          </select>

          <p id="aviso_professor"
             class="muted"
             style="margin-top:-10px;margin-bottom:20px">
            Selecione uma modalidade para visualizar os professores habilitados.
          </p>

          <a class="btn light"
             href="/professores"
             style="display:flex;align-items:center;justify-content:center;width:100%;margin-bottom:22px">
            👨‍🏫 Gerenciar professores
          </a>

          <label>Semana</label>
          <select name="semana">
            <option value="TODAS">Todas as semanas</option>
            <option value="A">Semana A</option>
            <option value="B">Semana B</option>
          </select>

          <label>Dias da semana</label>
          <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:8px 0 22px">
            {% for d in ["Segunda","Terça","Quarta","Quinta","Sexta","Sábado","Domingo"] %}
            <label style="display:flex;align-items:center;gap:8px;padding:10px;border:1px solid #ddd;border-radius:10px;margin:0">
              <input type="checkbox"
                     name="dias"
                     value="{{d}}"
                     style="width:auto;margin:0">
              {{d}}
            </label>
            {% endfor %}
          </div>

          <label>Horários</label>

          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">
            <input type="time" name="horarios">
            <input type="time" name="horarios">
            <input type="time" name="horarios">
          </div>

          <p class="muted" style="margin-top:8px;margin-bottom:18px">
            Informe até 3 horários para esta programação.
          </p>

          <label>Capacidade por aula</label>
          <input type="number"
                 name="capacidade"
                 min="1"
                 value="20">

          <button class="green" style="width:100%">
            ➕ Cadastrar programação
          </button>

        </form>
      </div>

      <div class="card">

        {% for x in rows %}
        <div style="padding:16px 0;border-bottom:1px solid #ddd">

          <p style="margin:0 0 12px 0;line-height:1.7">
            <b style="font-size:18px">{{x.modalidade}}</b><br>

            📅
            {% if (x.semana or 'TODAS') == 'A' %}
              <b>Semana A</b>
            {% elif (x.semana or 'TODAS') == 'B' %}
              <b>Semana B</b>
            {% else %}
              <b>Todas as semanas</b>
            {% endif %}
            <br>

            📆 <b>{{x.dia.replace(' / ', ' e ')}}</b><br>
            🕐 <b>{{x.horario}}</b><br>

            👨‍🏫 {{x.professor or 'Professor não definido'}}<br>

            👥 {{x.alunos_modalidade}}
            aluno{% if x.alunos_modalidade != 1 %}s{% endif %}
            · {{x.vagas_disponiveis}} de
            {{x.capacidade}} vagas disponíveis
          </p>

          {% if x.ativo %}
          <span class="pill">ATIVA</span>
          {% else %}
          <span class="pill">INATIVA</span>
          {% endif %}

          <div class="actions" style="margin-top:18px">

            <a class="btn" href="/aulas/{{x.id}}/editar">
              ✏️ Editar programação
            </a>

            <form method="post"
                  action="/aulas/{{x.id}}/status"
                  style="margin:0">
              {% if x.ativo %}
              <button type="submit" class="danger">⏸️ Desativar</button>
              {% else %}
              <button type="submit" class="green">▶️ Ativar</button>
              {% endif %}
            </form>

            <form method="post"
                  action="/aulas/{{x.id}}/excluir"
                  style="margin:0"
                  onsubmit="return confirm('Excluir esta programação?');">
              <button type="submit" class="danger">🗑️ Excluir</button>
            </form>

          </div>
        </div>

        {% else %}
        <p class="muted">Nenhuma aula cadastrada.</p>
        {% endfor %}

      </div>
    </div>

    <script>
    function filtrarProfessores() {
        const modalidade =
            document.getElementById("modalidade_aula").value;
        const select =
            document.getElementById("professor_aula");
        const aviso =
            document.getElementById("aviso_professor");

        select.value = "";
        let encontrados = 0;

        Array.from(select.options).forEach((option,index) => {
            if (index === 0) return;

            const especialidades =
                (option.dataset.especialidades || "")
                .split(",")
                .map(x => x.trim())
                .filter(Boolean);

            const mostrar =
                modalidade !== "" &&
                especialidades.includes(modalidade);

            option.hidden = !mostrar;
            option.disabled = !mostrar;

            if (mostrar) encontrados++;
        });

        if (!modalidade) {
            select.disabled = true;
            select.options[0].text =
                "Primeiro selecione a modalidade";
            aviso.textContent =
                "Selecione uma modalidade para visualizar os professores habilitados.";
        } else if (encontrados === 0) {
            select.disabled = true;
            select.options[0].text =
                "Nenhum professor habilitado";
            aviso.textContent =
                "Nenhum professor ativo possui esta especialidade.";
        } else {
            select.disabled = false;
            select.options[0].text =
                "Professor não definido";
            aviso.textContent =
                encontrados === 1
                ? "1 professor habilitado para esta modalidade."
                : encontrados + " professores habilitados para esta modalidade.";
        }
    }

    document.addEventListener(
        "DOMContentLoaded",
        filtrarProfessores
    );
    </script>
    """,
    rows=rows,
    mods=mods,
    professores=professores,
    erro=erro)


@app.route("/aulas/<int:id>/editar", methods=["GET","POST"])
@login_required
@permissao_required("aulas")
def aula_editar(id):
    con = db()

    aula = con.cursor().execute(
        """SELECT *
           FROM aulas
           WHERE id=%s AND academia_id=%s""",
        (id,aid())
    ).fetchone()

    if not aula:
        con.close()
        return redirect("/aulas")

    mods = con.cursor().execute(
        """SELECT id,nome
           FROM modalidades
           WHERE academia_id=%s AND ativo=1
           ORDER BY nome""",
        (aid(),)
    ).fetchall()

    professores = con.cursor().execute(
        """SELECT id,nome,especialidade
           FROM professores
           WHERE academia_id=%s AND ativo=1
           ORDER BY nome""",
        (aid(),)
    ).fetchall()

    erro = ""

    if request.method == "POST":
        f = request.form

        modalidade = f.get("modalidade","").strip()
        professor = f.get("professor","").strip()
        semana = f.get("semana","TODAS").strip().upper()

        if semana not in ("TODAS","A","B"):
            semana = "TODAS"

        ordem_dias = [
            "Segunda","Terça","Quarta","Quinta",
            "Sexta","Sábado","Domingo"
        ]

        dias = [
            d for d in ordem_dias
            if d in request.form.getlist("dias")
        ]

        horarios = []
        for h in request.form.getlist("horarios"):
            h = h.strip()
            if h and h not in horarios:
                horarios.append(h)

        try:
            capacidade = int(f.get("capacidade") or 20)
        except (ValueError, TypeError):
            capacidade = 20

        professor_valido = True

        if professor:
            prof = con.cursor().execute(
                """SELECT especialidade
                   FROM professores
                   WHERE academia_id=%s
                     AND nome=%s
                     AND ativo=1""",
                (aid(),professor)
            ).fetchone()

            if not prof:
                professor_valido = False
            else:
                especialidades = [
                    x.strip()
                    for x in str(prof["especialidade"] or "").split(",")
                    if x.strip()
                ]
                if modalidade not in especialidades:
                    professor_valido = False

        if not modalidade:
            erro = "Selecione a modalidade."
        elif not professor_valido:
            erro = "Este professor não possui a especialidade da modalidade selecionada."
        elif not dias:
            erro = "Selecione pelo menos um dia."
        elif not horarios:
            erro = "Informe pelo menos um horário."
        elif capacidade < 1:
            erro = "A capacidade deve ser de pelo menos 1 aluno."
        else:
            con.cursor().execute(
                """UPDATE aulas
                   SET modalidade=%s,
                       professor=%s,
                       semana=%s,
                       dia=%s,
                       horario=%s,
                       capacidade=%s
                   WHERE id=%s AND academia_id=%s""",
                (
                    modalidade,
                    professor,
                    semana,
                    " / ".join(dias),
                    " / ".join(horarios),
                    capacidade,
                    id,
                    aid()
                )
            )

            con.commit()
            con.close()
            return redirect("/aulas")

    dias_atuais = [
        x.strip()
        for x in str(aula["dia"] or "").split("/")
        if x.strip()
    ]

    horarios_atuais = [
        x.strip()
        for x in str(aula["horario"] or "").split("/")
        if x.strip()
    ]

    while len(horarios_atuais) < 3:
        horarios_atuais.append("")

    con.close()

    return page("Editar aula","""
    <h1>✏️ Editar programação</h1>

    {% if erro %}
    <div class="card"
         style="color:#dc2626;margin-bottom:18px">
      {{erro}}
    </div>
    {% endif %}

    <div class="card">
      <form method="post">

        <label>Modalidade</label>
        <select name="modalidade"
                id="modalidade_editar"
                required
                onchange="filtrarProfessoresEditar()">
          {% for m in mods %}
          <option value="{{m.nome}}"
                  {% if m.nome == aula.modalidade %}selected{% endif %}>
            {{m.nome}}
          </option>
          {% endfor %}
        </select>

        <label>Professor</label>
        <select name="professor"
                id="professor_editar">
          <option value="">Professor não definido</option>
          {% for p in professores %}
          <option value="{{p.nome}}"
                  data-especialidades="{{p.especialidade or ''}}"
                  {% if p.nome == aula.professor %}selected{% endif %}>
            {{p.nome}}
          </option>
          {% endfor %}
        </select>

        <p id="aviso_professor_editar"
           class="muted"
           style="margin-top:-10px;margin-bottom:20px">
        </p>

        <label>Semana</label>
        <select name="semana">
          <option value="TODAS"
                  {% if (aula.semana or 'TODAS') == 'TODAS' %}selected{% endif %}>
            Todas as semanas
          </option>
          <option value="A"
                  {% if aula.semana == 'A' %}selected{% endif %}>
            Semana A
          </option>
          <option value="B"
                  {% if aula.semana == 'B' %}selected{% endif %}>
            Semana B
          </option>
        </select>

        <label>Dias da semana</label>

        <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:8px 0 22px">
          {% for d in ["Segunda","Terça","Quarta","Quinta","Sexta","Sábado","Domingo"] %}
          <label style="display:flex;align-items:center;gap:8px;padding:10px;border:1px solid #ddd;border-radius:10px;margin:0">
            <input type="checkbox"
                   name="dias"
                   value="{{d}}"
                   {% if d in dias_atuais %}checked{% endif %}
                   style="width:auto;margin:0">
            {{d}}
          </label>
          {% endfor %}
        </div>

        <label>Horários</label>

        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">
          <input type="time"
                 name="horarios"
                 value="{{horarios_atuais[0]}}">
          <input type="time"
                 name="horarios"
                 value="{{horarios_atuais[1]}}">
          <input type="time"
                 name="horarios"
                 value="{{horarios_atuais[2]}}">
        </div>

        <label style="margin-top:18px">Capacidade</label>
        <input type="number"
               name="capacidade"
               min="1"
               value="{{aula.capacidade or 20}}">

        <button class="green" style="width:100%">
          💾 Salvar programação
        </button>

      </form>
    </div>

    <script>
    function filtrarProfessoresEditar() {
        const modalidade =
            document.getElementById("modalidade_editar").value;
        const select =
            document.getElementById("professor_editar");
        const aviso =
            document.getElementById("aviso_professor_editar");

        let encontrados = 0;

        Array.from(select.options).forEach((option,index) => {
            if (index === 0) return;

            const especialidades =
                (option.dataset.especialidades || "")
                .split(",")
                .map(x => x.trim())
                .filter(Boolean);

            const mostrar =
                modalidade !== "" &&
                especialidades.includes(modalidade);

            option.hidden = !mostrar;
            option.disabled = !mostrar;

            if (mostrar) encontrados++;
        });

        aviso.textContent =
            encontrados === 0
            ? "Nenhum professor ativo possui esta especialidade."
            : encontrados + " professor(es) habilitado(s).";
    }

    document.addEventListener(
        "DOMContentLoaded",
        filtrarProfessoresEditar
    );
    </script>
    """,
    aula=aula,
    mods=mods,
    professores=professores,
    dias_atuais=dias_atuais,
    horarios_atuais=horarios_atuais,
    erro=erro)


@app.route("/aulas/<int:id>/status", methods=["POST"])
@login_required
@permissao_required("aulas")
def aula_status(id):
    con = db()

    aula = con.cursor().execute(
        """SELECT id,ativo
           FROM aulas
           WHERE id=%s AND academia_id=%s""",
        (id,aid())
    ).fetchone()

    if aula:
        novo_status = 0 if aula["ativo"] else 1

        con.cursor().execute(
            """UPDATE aulas
               SET ativo=%s
               WHERE id=%s
               AND academia_id=%s""",
            (novo_status,id,aid())
        )

        con.commit()

    con.close()

    return redirect("/aulas")


@app.route("/aulas/<int:id>/excluir", methods=["POST"])
@login_required
@permissao_required("aulas")
def aula_excluir(id):
    con = db()

    aula = con.cursor().execute(
        """SELECT id
           FROM aulas
           WHERE id=%s AND academia_id=%s""",
        (id, aid())
    ).fetchone()

    if aula:
        con.cursor().execute(
            """DELETE FROM aulas
               WHERE id=%s AND academia_id=%s""",
            (id, aid())
        )
        con.commit()

    con.close()

    return redirect("/aulas")


@app.route("/avaliacoes", methods=["GET","POST"])
@login_required
@permissao_required("avaliacoes")
def avaliacoes():
    con=db()

    alunos=con.cursor().execute(
        "SELECT id,nome FROM alunos WHERE academia_id=%s AND ativo=1 ORDER BY nome",
        (aid(),)
    ).fetchall()

    campos_numericos = [
        "peso","altura","gordura","cintura","braco",
        "pescoco","ombros","peito","abdomen","quadril",
        "braco_direito","braco_esquerdo",
        "antebraco_direito","antebraco_esquerdo",
        "coxa_direita","coxa_esquerda",
        "panturrilha_direita","panturrilha_esquerda",
        "massa_muscular","massa_ossea","agua_corporal",
        "gordura_visceral","metabolismo_basal",
        "dobra_peitoral","dobra_abdominal","dobra_coxa",
        "dobra_triceps","dobra_subescapular",
        "dobra_suprailiaca","dobra_axilar",
        "flexibilidade","forca","resistencia","agilidade",
        "pressao_sistolica","pressao_diastolica",
        "frequencia_cardiaca","frequencia_repouso"
    ]

    if request.method=="POST":
        f=request.form

        valores=[]
        for campo in campos_numericos:
            valor=f.get(campo)
            if valor:
                try:
                    valores.append(float(str(valor).replace(",",".")))
                except (ValueError,TypeError):
                    valores.append(None)
            else:
                valores.append(None)

        colunas = ",".join(campos_numericos)

        marcadores = ",".join(["%s"] * (
            3 + len(campos_numericos) + 4
        ))

        sql=f"""
            INSERT INTO avaliacoes(
                academia_id,aluno_id,data,
                {colunas},
                objetivo,protocolo,unidade,observacoes
            )
            VALUES({marcadores})
        """

        parametros = [
            aid(),
            f["aluno_id"],
            f["data"],
            *valores,
            f.get("objetivo") or None,
            f.get("protocolo") or None,
            f.get("unidade") or "METRICO",
            f.get("observacoes") or None
        ]

        con.cursor().execute(sql,parametros)
        con.commit()

    rows=con.cursor().execute("""
        SELECT v.*,a.nome
        FROM avaliacoes v
        JOIN alunos a ON a.id=v.aluno_id
        WHERE v.academia_id=%s
        ORDER BY v.data DESC,v.id DESC
        LIMIT 50
    """,(aid(),)).fetchall()

    con.close()

    return page("Avaliações","""
    <h1>🌍 Avaliações e evolução</h1>

    <style>
    .avaliacoes-layout{
        display:grid;
        grid-template-columns:1fr;
        gap:24px;
        align-items:start;
    }

    .avaliacoes-layout .card{
        padding:28px;
        border-radius:28px;
    }

    .avaliacoes-layout h2{
        font-size:44px;
        margin:18px 0 24px;
    }

    .avaliacoes-layout label{
        font-size:32px;
        font-weight:700;
        display:block;
        margin-top:12px;
    }

    .avaliacoes-layout input,
    .avaliacoes-layout select,
    .avaliacoes-layout textarea{
        font-size:25px;
        padding:20px 22px;
        min-height:68px;
        border-radius:18px;
        margin:10px 0 22px;
    }

    .avaliacoes-layout textarea{
        min-height:130px;
    }

    .avaliacoes-layout .grid{
        gap:20px;
    }

    .avaliacoes-layout p{
        font-size:30px;
        line-height:1.35;
    }

    .avaliacoes-layout button{
        font-size:24px !important;
        padding:18px 24px;
        min-height:64px;
        border-radius:16px;
    }

    @media(max-width:760px){
        .avaliacoes-layout{
            grid-template-columns:1fr;
        }
    }
    </style>

    <div class="avaliacoes-layout">

      <div class="card">

        <form method="post">

          <h2>👤 Dados básicos</h2>

          <label>Aluno</label>
          <select name="aluno_id" required>
            {% for a in alunos %}
              <option value="{{a.id}}">{{a.nome}}</option>
            {% endfor %}
          </select>

          <label>Data da avaliação</label>
          <input type="date" name="data" required>

          <label>Sistema de unidades</label>
          <select name="unidade">
            <option value="METRICO">Métrico — kg / cm</option>
            <option value="IMPERIAL">Imperial — lb / in</option>
          </select>

          <div class="grid">
            <div>
              <label>Peso</label>
              <input name="peso" type="number" step=".01">
            </div>
            <div>
              <label>Altura</label>
              <input name="altura" type="number" step=".01">
            </div>
            <div>
              <label>Gordura corporal %</label>
              <input name="gordura" type="number" step=".01">
            </div>
          </div>

          <hr>

          <h2>📏 Perimetria</h2>

          <div class="grid">
            <div><label>Pescoço</label><input name="pescoco" type="number" step=".01"></div>
            <div><label>Ombros</label><input name="ombros" type="number" step=".01"></div>
            <div><label>Peito / Tórax</label><input name="peito" type="number" step=".01"></div>
            <div><label>Cintura</label><input name="cintura" type="number" step=".01"></div>
            <div><label>Abdômen</label><input name="abdomen" type="number" step=".01"></div>
            <div><label>Quadril</label><input name="quadril" type="number" step=".01"></div>

            <div><label>Braço direito</label><input name="braco_direito" type="number" step=".01"></div>
            <div><label>Braço esquerdo</label><input name="braco_esquerdo" type="number" step=".01"></div>

            <div><label>Antebraço direito</label><input name="antebraco_direito" type="number" step=".01"></div>
            <div><label>Antebraço esquerdo</label><input name="antebraco_esquerdo" type="number" step=".01"></div>

            <div><label>Coxa direita</label><input name="coxa_direita" type="number" step=".01"></div>
            <div><label>Coxa esquerda</label><input name="coxa_esquerda" type="number" step=".01"></div>

            <div><label>Panturrilha direita</label><input name="panturrilha_direita" type="number" step=".01"></div>
            <div><label>Panturrilha esquerda</label><input name="panturrilha_esquerda" type="number" step=".01"></div>
          </div>

          <hr>

          <h2>🧬 Composição corporal</h2>

          <div class="grid">
            <div><label>Massa muscular</label><input name="massa_muscular" type="number" step=".01"></div>
            <div><label>Massa óssea</label><input name="massa_ossea" type="number" step=".01"></div>
            <div><label>Água corporal %</label><input name="agua_corporal" type="number" step=".01"></div>
            <div><label>Gordura visceral</label><input name="gordura_visceral" type="number" step=".01"></div>
            <div><label>Metabolismo basal (kcal)</label><input name="metabolismo_basal" type="number" step=".01"></div>
          </div>

          <hr>

          <h2>📐 Dobras cutâneas</h2>

          <div class="grid">
            <div><label>Peitoral (mm)</label><input name="dobra_peitoral" type="number" step=".01"></div>
            <div><label>Abdominal (mm)</label><input name="dobra_abdominal" type="number" step=".01"></div>
            <div><label>Coxa (mm)</label><input name="dobra_coxa" type="number" step=".01"></div>
            <div><label>Tríceps (mm)</label><input name="dobra_triceps" type="number" step=".01"></div>
            <div><label>Subescapular (mm)</label><input name="dobra_subescapular" type="number" step=".01"></div>
            <div><label>Supra-ilíaca (mm)</label><input name="dobra_suprailiaca" type="number" step=".01"></div>
            <div><label>Axilar (mm)</label><input name="dobra_axilar" type="number" step=".01"></div>
          </div>

          <hr>

          <h2>🏃 Performance</h2>

          <div class="grid">
            <div><label>Flexibilidade</label><input name="flexibilidade" type="number" step=".01"></div>
            <div><label>Força</label><input name="forca" type="number" step=".01"></div>
            <div><label>Resistência</label><input name="resistencia" type="number" step=".01"></div>
            <div><label>Agilidade</label><input name="agilidade" type="number" step=".01"></div>
          </div>

          <hr>

          <h2>❤️ Sinais básicos</h2>

          <div class="grid">
            <div><label>Pressão sistólica</label><input name="pressao_sistolica" type="number" step="1"></div>
            <div><label>Pressão diastólica</label><input name="pressao_diastolica" type="number" step="1"></div>
            <div><label>Frequência cardíaca</label><input name="frequencia_cardiaca" type="number" step="1"></div>
            <div><label>FC de repouso</label><input name="frequencia_repouso" type="number" step="1"></div>
          </div>

          <hr>

          <h2>🎯 Objetivo e protocolo</h2>

          <label>Objetivo</label>
          <select name="objetivo">
            <option value="">Selecione</option>
            <option>Emagrecimento</option>
            <option>Hipertrofia</option>
            <option>Condicionamento físico</option>
            <option>Performance esportiva</option>
            <option>Mobilidade / Flexibilidade</option>
            <option>Qualidade de vida</option>
            <option>Outro</option>
          </select>

          <label>Protocolo de avaliação</label>
          <select name="protocolo">
            <option value="">Não definido</option>
            <option>Antropometria</option>
            <option>Bioimpedância</option>
            <option>Jackson & Pollock 3 dobras</option>
            <option>Jackson & Pollock 7 dobras</option>
            <option>Pollock 3 dobras</option>
            <option>Faulkner</option>
            <option>Personalizado</option>
          </select>

          <label>Observações</label>
          <textarea name="observacoes" rows="4"></textarea>

          <button class="green"
                  style="width:100%;font-size:17px">
            💾 Salvar avaliação completa
          </button>

        </form>

      </div>

      <div class="card">

        <h2>📈 Histórico de avaliações</h2>

        {% for x in rows %}

          <div style="padding:15px 0;border-bottom:1px solid #ddd">

            <p>
              <b>{{x.nome}}</b> · {{x.data}}
            </p>

            <h3>👤 Dados básicos</h3>
            <p>
              Peso: <b>{{x.peso or '-'}}</b><br>
              Altura: <b>{{x.altura or '-'}}</b><br>

              {% if x.peso and x.altura and x.unidade != 'IMPERIAL' %}
                IMC:
                <b>{{'%.2f'|format(x.peso / (x.altura * x.altura))}}</b><br>
              {% endif %}

              Gordura corporal: <b>{{x.gordura or '-'}}</b>%<br>
              Unidade: <b>{{x.unidade or 'METRICO'}}</b>
            </p>

            <h3>📏 Perimetria</h3>
            <p>
              Pescoço: <b>{{x.pescoco or '-'}}</b><br>
              Ombros: <b>{{x.ombros or '-'}}</b><br>
              Peito / Tórax: <b>{{x.peito or '-'}}</b><br>
              Cintura: <b>{{x.cintura or '-'}}</b><br>
              Abdômen: <b>{{x.abdomen or '-'}}</b><br>
              Quadril: <b>{{x.quadril or '-'}}</b><br>
              Braço direito: <b>{{x.braco_direito or '-'}}</b><br>
              Braço esquerdo: <b>{{x.braco_esquerdo or '-'}}</b><br>
              Antebraço direito: <b>{{x.antebraco_direito or '-'}}</b><br>
              Antebraço esquerdo: <b>{{x.antebraco_esquerdo or '-'}}</b><br>
              Coxa direita: <b>{{x.coxa_direita or '-'}}</b><br>
              Coxa esquerda: <b>{{x.coxa_esquerda or '-'}}</b><br>
              Panturrilha direita: <b>{{x.panturrilha_direita or '-'}}</b><br>
              Panturrilha esquerda
<b>{{x.panturrilha_esquerda or '-'}}</b>
            </p>

            <h3>🧬 Composição corporal</h3>
            <p>
              Massa muscular: <b>{{x.massa_muscular or '-'}}</b><br>
              Massa óssea: <b>{{x.massa_ossea or '-'}}</b><br>
              Água corporal: <b>{{x.agua_corporal or '-'}}</b>%<br>
              Gordura visceral: <b>{{x.gordura_visceral or '-'}}</b><br>
              Metabolismo basal: <b>{{x.metabolismo_basal or '-'}}</b> kcal
            </p>

            <h3>📐 Dobras cutâneas</h3>
            <p>
              Peitoral: <b>{{x.dobra_peitoral or '-'}}</b> mm<br>
              Abdominal: <b>{{x.dobra_abdominal or '-'}}</b> mm<br>
              Coxa: <b>{{x.dobra_coxa or '-'}}</b> mm<br>
              Tríceps: <b>{{x.dobra_triceps or '-'}}</b> mm<br>
              Subescapular: <b>{{x.dobra_subescapular or '-'}}</b> mm<br>
              Supra-ilíaca: <b>{{x.dobra_suprailiaca or '-'}}</b> mm<br>
              Axilar: <b>{{x.dobra_axilar or '-'}}</b> mm
            </p>

            <h3>🏃 Performance</h3>
            <p>
              Flexibilidade: <b>{{x.flexibilidade or '-'}}</b><br>
              Força: <b>{{x.forca or '-'}}</b><br>
              Resistência: <b>{{x.resistencia or '-'}}</b><br>
              Agilidade: <b>{{x.agilidade or '-'}}</b>
            </p>

            <h3>❤️ Sinais básicos</h3>
            <p>
              Pressão arterial:
              <b>{{x.pressao_sistolica or '-'}} / {{x.pressao_diastolica or '-'}}</b><br>
              Frequência cardíaca: <b>{{x.frequencia_cardiaca or '-'}}</b><br>
              FC de repouso: <b>{{x.frequencia_repouso or '-'}}</b>
            </p>

            <h3>🎯 Objetivo e protocolo</h3>

            {% if x.objetivo %}
              <p>🎯 Objetivo: <b>{{x.objetivo}}</b></p>
            {% else %}
              <p>🎯 Objetivo: <b>-</b></p>
            {% endif %}

            {% if x.protocolo %}
              <p>📋 Protocolo: <b>{{x.protocolo}}</b></p>
            {% else %}
              <p>📋 Protocolo: <b>-</b></p>
            {% endif %}

            {% if x.observacoes %}
              <p class="muted">📝 {{x.observacoes}}</p>
            {% endif %}

            <form method="post"
                  action="/avaliacoes/{{x.id}}/excluir"
                  onsubmit="return confirm('Excluir esta avaliação?');">

              <button type="submit" class="danger">
                🗑️ Excluir
              </button>

            </form>

          </div>

        {% else %}
          <p class="muted">Nenhuma avaliação registrada.</p>
        {% endfor %}

      </div>

    </div>
    """,alunos=alunos,rows=rows)


@app.route("/avaliacoes/<int:id>/excluir", methods=["POST"])
@login_required
@permissao_required("avaliacoes")
def avaliacao_excluir(id):
    con=db()

    con.cursor().execute(
        "DELETE FROM avaliacoes WHERE id=%s AND academia_id=%s",
        (id,aid())
    )

    con.commit()
    con.close()

    return redirect("/avaliacoes")


@app.route("/usuarios", methods=["GET","POST"])
@login_required
def usuarios():
    if str(session.get("perfil") or "").upper() != "DONO":
        flash("Apenas o dono da academia pode gerenciar usuários.")
        return redirect("/")

    con = db()
    erro = ""
    sucesso = ""

    if request.method == "POST":
        nome = request.form.get("nome","").strip()
        email = request.form.get("email","").strip().lower()
        senha = request.form.get("senha","").strip()
        perfil = request.form.get("perfil","FUNCIONARIO").strip().upper()

        if perfil not in ("ADMIN","PROFESSOR","FUNCIONARIO"):
            erro = "Perfil inválido."
        elif not nome or not email or not senha:
            erro = "Preencha nome, e-mail e senha."
        else:
            existente = con.cursor().execute(
                "SELECT id FROM usuarios WHERE lower(email)=lower(%s)",
                (email,)
            ).fetchone()

            if existente:
                erro = "Este e-mail já está cadastrado."
            else:
                con.cursor().execute(
                    """INSERT INTO usuarios
                    (academia_id,nome,email,senha,perfil,ativo,criado_em)
                    VALUES(%s,%s,%s,%s,%s,1,%s)""",
                    (aid(),nome,email,senha,perfil,agora())
                )
                con.commit()
                sucesso = "Usuário cadastrado com sucesso."

    rows = con.cursor().execute(
        """SELECT id,nome,email,perfil,ativo
           FROM usuarios
           WHERE academia_id=%s
           ORDER BY nome""",
        (aid(),)
    ).fetchall()

    con.close()

    return page("Usuários","""
    <h1>👥 Usuários e funcionários</h1>

    {% if erro %}
    <div class="card" style="color:#dc2626;margin-bottom:18px">
        {{erro}}
    </div>
    {% endif %}

    {% if sucesso %}
    <div class="card" style="color:#16a34a;margin-bottom:18px">
        {{sucesso}}
    </div>
    {% endif %}

    <div class="grid">

      <div class="card">
        <h2>➕ Novo usuário</h2>

        <form method="post">
          <label>Nome</label>
          <input name="nome" required>

          <label>E-mail</label>
          <input name="email" type="email" required>

          <label>Senha</label>
          <input name="senha" type="password" required>

          <label>Perfil</label>
          <select name="perfil" required>
            <option value="FUNCIONARIO">Funcionário</option>
            <option value="PROFESSOR">Professor</option>
            <option value="ADMIN">Administrador</option>
          </select>

          <button class="green" style="width:100%">
            Criar usuário
          </button>
        </form>
      </div>

      <div class="card">
        <h2>👤 Usuários cadastrados</h2>

        {% for u in rows %}
        <div style="padding:16px 0;border-bottom:1px solid #ddd">
          <b>{{u.nome}}</b>
          <p>{{u.email}}</p>
          <span class="pill">{{u.perfil}}</span>
          {% if u.ativo %}
            <span class="pill">ATIVO</span>
          {% else %}
            <span class="pill">INATIVO</span>
          {% endif %}

          {% if u.perfil != 'DONO' %}
          <div class="actions" style="margin-top:18px">

            <a class="btn" href="/usuarios/{{u.id}}/editar">
              ✏️ Editar
            </a>

            <form method="post"
                  action="/usuarios/{{u.id}}/status"
                  style="margin:0">

              {% if u.ativo %}
              <button type="submit" class="danger">
                ⛔ Desativar
              </button>
              {% else %}
              <button type="submit" class="green">
                ✅ Ativar
              </button>
              {% endif %}

            </form>

            <form method="post"
                  action="/usuarios/{{u.id}}/excluir"
                  style="margin:0"
                  onsubmit="return confirm('Excluir este usuário definitivamente?');">
              <button type="submit" class="danger">
                🗑️ Excluir
              </button>
            </form>

          </div>
          {% endif %}

        </div>
        {% else %}
        <p class="muted">Nenhum usuário cadastrado.</p>
        {% endfor %}
      </div>

    </div>
    """, rows=rows, erro=erro, sucesso=sucesso)


@app.route("/usuarios/<int:id>/editar", methods=["GET","POST"])
@login_required
def usuario_editar(id):
    if str(session.get("perfil") or "").upper() != "DONO":
        flash("Apenas o dono da academia pode gerenciar usuários.")
        return redirect("/")

    con = db()

    u = con.cursor().execute(
        """SELECT id,nome,email,perfil,ativo,permissoes_customizadas
           FROM usuarios
           WHERE id=%s AND academia_id=%s""",
        (id, aid())
    ).fetchone()

    if not u:
        con.close()
        return redirect("/usuarios")

    if str(u["perfil"]).upper() == "DONO":
        con.close()
        flash("O usuário DONO é protegido.")
        return redirect("/usuarios")

    erro = ""

    if request.method == "POST":
        nome = request.form.get("nome","").strip()
        email = request.form.get("email","").strip().lower()
        perfil = request.form.get("perfil","FUNCIONARIO").strip().upper()
        nova_senha = request.form.get("nova_senha","").strip()

        areas_validas = {
            "painel", "alunos", "checkin", "planos",
            "financeiro", "aulas", "avaliacoes"
        }

        permissoes_escolhidas = [
            area for area in request.form.getlist("permissoes")
            if area in areas_validas
        ]

        permissoes_customizadas = ",".join(permissoes_escolhidas)

        if perfil not in ("ADMIN","PROFESSOR","FUNCIONARIO"):
            erro = "Perfil inválido."

        elif not nome or not email:
            erro = "Nome e e-mail são obrigatórios."

        else:
            existente = con.cursor().execute(
                """SELECT id FROM usuarios
                   WHERE lower(email)=lower(%s)
                   AND id<>%s""",
                (email,id)
            ).fetchone()

            if existente:
                erro = "Este e-mail já está sendo usado."

            else:
                if nova_senha:
                    con.cursor().execute(
                        """UPDATE usuarios
                           SET nome=%s,email=%s,perfil=%s,senha=%s,
                               permissoes_customizadas=%s
                           WHERE id=%s AND academia_id=%s""",
                        (nome,email,perfil,nova_senha,
                         permissoes_customizadas,id,aid())
                    )
                else:
                    con.cursor().execute(
                        """UPDATE usuarios
                           SET nome=%s,email=%s,perfil=%s,
                               permissoes_customizadas=%s
                           WHERE id=%s AND academia_id=%s""",
                        (nome,email,perfil,
                         permissoes_customizadas,id,aid())
                    )

                con.commit()
                con.close()
                return redirect("/usuarios")

    con.close()

    return page("Editar usuário","""
    <h1>✏️ Editar usuário</h1>

    {% if erro %}
    <div class="card" style="color:#dc2626;margin-bottom:18px">
        {{erro}}
    </div>
    {% endif %}

    <div class="card">

      <form method="post">

        <label>Nome</label>
        <input name="nome" value="{{u.nome}}" required>

        <label>E-mail</label>
        <input name="email" type="email" value="{{u.email}}" required>

        <label>Perfil</label>
        <select name="perfil">
          <option value="FUNCIONARIO" {% if u.perfil == 'FUNCIONARIO' %}selected{% endif %}>
            Funcionário
          </option>
          <option value="PROFESSOR" {% if u.perfil == 'PROFESSOR' %}selected{% endif %}>
            Professor
          </option>
          <option value="ADMIN" {% if u.perfil == 'ADMIN' %}selected{% endif %}>
            Administrador
          </option>
        </select>

        <label>Nova senha</label>
        <input name="nova_senha" type="password"
               placeholder="Deixe vazio para manter a senha atual">

        <hr style="margin:28px 0">

        <h2>🔐 Permissões de acesso</h2>
        <p class="muted">
          Escolha exatamente quais áreas este usuário poderá acessar.
        </p>

        {% set atuais = (u.permissoes_customizadas or '').split(',') %}

        <div class="card" style="box-shadow:none;border:1px solid #ddd">

          <label style="display:block;margin-bottom:16px">
            <input type="checkbox" name="permissoes" value="painel"
                   style="width:auto;margin-right:12px"
                   {% if 'painel' in atuais %}checked{% endif %}>
            📊 Painel
          </label>

          <label style="display:block;margin-bottom:16px">
            <input type="checkbox" name="permissoes" value="alunos"
                   style="width:auto;margin-right:12px"
                   {% if 'alunos' in atuais %}checked{% endif %}>
            👥 Alunos
          </label>

          <label style="display:block;margin-bottom:16px">
            <input type="checkbox" name="permissoes" value="checkin"
                   style="width:auto;margin-right:12px"
                   {% if 'checkin' in atuais %}checked{% endif %}>
            ✅ Check-in
          </label>

          <label style="display:block;margin-bottom:16px">
            <input type="checkbox" name="permissoes" value="planos"
                   style="width:auto;margin-right:12px"
                   {% if 'planos' in atuais %}checked{% endif %}>
            💳 Planos
          </label>

          <label style="display:block;margin-bottom:16px">
            <input type="checkbox" name="permissoes" value="financeiro"
                   style="width:auto;margin-right:12px"
                   {% if 'financeiro' in atuais %}checked{% endif %}>
            💰 Financeiro
          </label>

          <label style="display:block;margin-bottom:16px">
            <input type="checkbox" name="permissoes" value="aulas"
                   style="width:auto;margin-right:12px"
                   {% if 'aulas' in atuais %}checked{% endif %}>
            📅 Aulas
          </label>

          <label style="display:block;margin-bottom:4px">
            <input type="checkbox" name="permissoes" value="avaliacoes"
                   style="width:auto;margin-right:12px"
                   {% if 'avaliacoes' in atuais %}checked{% endif %}>
            📈 Avaliações
          </label>

        </div>

        <button class="green" style="width:100%;margin-top:20px">
          Salvar alterações
        </button>

      </form>

    </div>
    """, u=u, erro=erro)


@app.route("/usuarios/<int:id>/status", methods=["POST"])
@login_required
def usuario_status(id):
    if str(session.get("perfil") or "").upper() != "DONO":
        flash("Apenas o dono da academia pode gerenciar usuários.")
        return redirect("/")

    con = db()

    u = con.cursor().execute(
        """SELECT id,perfil,ativo
           FROM usuarios
           WHERE id=%s AND academia_id=%s""",
        (id,aid())
    ).fetchone()

    if not u:
        con.close()
        return redirect("/usuarios")

    if str(u["perfil"]).upper() == "DONO":
        con.close()
        flash("O usuário DONO não pode ser desativado.")
        return redirect("/usuarios")

    novo_status = 0 if u["ativo"] else 1

    con.cursor().execute(
        """UPDATE usuarios
           SET ativo=%s
           WHERE id=%s AND academia_id=%s""",
        (novo_status,id,aid())
    )

    con.commit()
    con.close()

    return redirect("/usuarios")


@app.route("/usuarios/<int:id>/excluir", methods=["POST"])
@login_required
def usuario_excluir(id):
    if str(session.get("perfil") or "").upper() != "DONO":
        flash("Apenas o dono da academia pode excluir usuários.")
        return redirect("/")

    con = db()

    u = con.cursor().execute(
        """SELECT id,perfil
           FROM usuarios
           WHERE id=%s AND academia_id=%s""",
        (id, aid())
    ).fetchone()

    if not u:
        con.close()
        return redirect("/usuarios")

    if str(u["perfil"]).upper() == "DONO":
        con.close()
        flash("O usuário DONO é protegido e não pode ser excluído.")
        return redirect("/usuarios")

    con.cursor().execute(
        """DELETE FROM usuarios
           WHERE id=%s
           AND academia_id=%s
           AND upper(perfil) <> 'DONO'""",
        (id, aid())
    )

    con.commit()
    con.close()

    flash("Usuário excluído com sucesso.")
    return redirect("/usuarios")


@app.route("/config", methods=["GET","POST"])
@login_required
@permissao_required("config")
def config():
    con=db()
    if request.method=="POST":
        f=request.form

        # Logo própria da academia
        logo_atual = con.cursor().execute(
            "SELECT logo FROM academias WHERE id=%s",
            (aid(),)
        ).fetchone()

        logo_nome = logo_atual["logo"] if logo_atual else None
        logo = request.files.get("logo")

        if logo and logo.filename:
            extensao = os.path.splitext(logo.filename)[1].lower()

            if extensao in (".png", ".jpg", ".jpeg", ".webp"):
                os.makedirs("static/logos", exist_ok=True)

                logo_nome = "academia_%s%s" % (
                    aid(),
                    extensao
                )

                logo.save(
                    os.path.join(
                        "static",
                        "logos",
                        logo_nome
                    )
                )

        con.cursor().execute("""
            UPDATE academias
            SET nome=%s,
                documento=%s,
                telefone=%s,
                endereco=%s,
                cor=%s,
                logo=%s,
                pix_ativo=%s,
                pix_tipo_chave=%s,
                pix_chave=%s,
                pix_nome=%s,
                pix_cidade=%s
            WHERE id=%s
        """,(
            f["nome"],
            f.get("documento"),
            f.get("telefone"),
            f.get("endereco"),
            f.get("cor"),
            logo_nome,
            1 if f.get("pix_ativo") else 0,
            f.get("pix_tipo_chave"),
            f.get("pix_chave","").strip(),
            f.get("pix_nome","").strip(),
            f.get("pix_cidade","").strip().upper(),
            aid()
        ))
        con.commit()
    ac=con.cursor().execute("SELECT * FROM academias WHERE id=%s",(aid(),)).fetchone()
    mods=con.cursor().execute("SELECT * FROM modalidades WHERE academia_id=%s ORDER BY nome",(aid(),)).fetchall()
    con.close()
    return page("Configurações","""
    <h1>Configurações</h1><div class="grid"><div class="card"><h2>Academia</h2><form method="post" enctype="multipart/form-data">
    <label>Nome</label><input name="nome" value="{{ac.nome}}" required><label>CNPJ/CPF</label><input name="documento" value="{{ac.documento or ''}}">
    <label>Telefone</label><input name="telefone" value="{{ac.telefone or ''}}"><label>Endereço</label><input name="endereco" value="{{ac.endereco or ''}}">
    <label>Cor principal</label>
    <input type="color" name="cor" value="{{ac.cor or '#111827'}}">

    <hr style="margin:24px 0">

    <h2>🖼️ Logo da academia</h2>

    <p class="muted">
      A logo será utilizada nos comprovantes de pagamento.
    </p>

    {% if ac.logo %}
    <div style="text-align:center;margin:15px 0">
      <img src="/static/logos/{{ac.logo}}"
           alt="Logo da academia"
           style="max-width:220px;
                  max-height:120px;
                  object-fit:contain">
    </div>
    {% endif %}

    <label>Selecionar logo</label>

    <input type="file"
           name="logo"
           accept="image/png,image/jpeg,image/webp">

    <p class="muted">
      Formatos aceitos: PNG, JPG, JPEG ou WEBP.
    </p>

    <hr style="margin:28px 0">

    <h2>💳 PIX</h2>
    <p class="muted">Configure o PIX utilizado para receber as mensalidades desta academia.</p>

    <label style="display:flex;align-items:center;gap:10px;margin:15px 0">
        <input type="checkbox"
               name="pix_ativo"
               value="1"
               style="width:24px;height:24px"
               {% if ac.pix_ativo %}checked{% endif %}>
        <b>Ativar recebimentos por PIX</b>
    </label>

    <label>Tipo da chave PIX</label>
    <select name="pix_tipo_chave">
        <option value="">Selecione</option>
        <option value="CPF" {% if ac.pix_tipo_chave=='CPF' %}selected{% endif %}>CPF</option>
        <option value="CNPJ" {% if ac.pix_tipo_chave=='CNPJ' %}selected{% endif %}>CNPJ</option>
        <option value="CELULAR" {% if ac.pix_tipo_chave=='CELULAR' %}selected{% endif %}>Celular</option>
        <option value="EMAIL" {% if ac.pix_tipo_chave=='EMAIL' %}selected{% endif %}>E-mail</option>
        <option value="ALEATORIA" {% if ac.pix_tipo_chave=='ALEATORIA' %}selected{% endif %}>Chave aleatória</option>
    </select>

    <label>Chave PIX</label>
    <input name="pix_chave"
           value="{{ac.pix_chave or ''}}"
           placeholder="Digite a chave PIX">

    <label>Nome do recebedor</label>
    <input name="pix_nome"
           value="{{ac.pix_nome or ''}}"
           placeholder="Nome do titular">

    <label>Cidade</label>
    <input name="pix_cidade"
           value="{{ac.pix_cidade or ''}}"
           placeholder="Ex.: RIO DE JANEIRO">

    <button class="green">💾 Salvar configurações</button>
    </form></div>
    <div class="card"><h2>Modalidades disponíveis</h2>{% for m in mods %}<span class="pill">{{m.nome}}</span> {% endfor %}
    <p class="muted">A estrutura aceita modalidades diferentes por academia.</p>
    <h3>Plano do sistema</h3><p>{{ac.plano}}</p>

    {% if session.get('perfil') == 'DONO' %}
    <hr style="margin:28px 0">
    <h2>👥 Equipe e acessos</h2>
    <p class="muted">Cadastre administradores, professores e funcionários.</p>
    <a class="btn green" href="/usuarios"
       style="display:flex;align-items:center;justify-content:center;width:100%;font-size:26px;font-weight:800;min-height:70px">
       👥 Usuários e funcionários
    </a>
    {% endif %}

    </div></div>""",ac=ac,mods=mods)

# Inicializa o banco também quando o aplicativo é carregado pelo Gunicorn/Render.
# init_db usa CREATE TABLE IF NOT EXISTS, portanto pode ser executado com segurança.
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5001)), debug=False)

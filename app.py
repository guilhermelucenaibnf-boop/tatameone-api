import os
import psycopg
from psycopg.rows import dict_row
import secrets
import qrcode
import io
import base64
from datetime import datetime
from functools import wraps
from flask import Flask, request, redirect, url_for, session, render_template_string, flash, send_from_directory

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tatameone-2-troque-em-producao")
DATABASE_URL = os.environ.get("DATABASE_URL")

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
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
"""CREATE TABLE IF NOT EXISTS pre_cadastros(id BIGSERIAL PRIMARY KEY,academia_id BIGINT NOT NULL,nome TEXT NOT NULL,documento TEXT,nascimento TEXT,telefone TEXT,email TEXT,responsavel TEXT,telefone_responsavel TEXT,modalidade TEXT,graduacao TEXT,observacoes TEXT,status TEXT DEFAULT 'PENDENTE',criado_em TEXT NOT NULL,endereco TEXT,contato_emergencia TEXT,telefone_emergencia TEXT,foto TEXT)"""
    ]
    for sql in comandos: cur.execute(sql)
    cur.execute("SELECT COUNT(*) AS n FROM academias")
    if cur.fetchone()["n"]==0:
        cur.execute("INSERT INTO academias(nome,plano,criado_em) VALUES(%s,%s,%s) RETURNING id",("TatameOne Demonstração","PREMIUM",agora()))
        academia_inicial=cur.fetchone()["id"]
        cur.execute("INSERT INTO usuarios(academia_id,nome,email,senha,perfil,criado_em) VALUES(%s,%s,%s,%s,%s,%s)",(academia_inicial,"Administrador","admin@tatameone.local","1234","DONO",agora()))
        for m in ("Musculação","Jiu-Jítsu","Muay Thai","Boxe","Funcional","Cross Training","Pilates","Yoga","Dança","Natação","Personal"):
            cur.execute("INSERT INTO modalidades(academia_id,nome) VALUES(%s,%s)",(academia_inicial,m))
        cur.execute("INSERT INTO planos(academia_id,nome,valor,periodicidade,descricao) VALUES(%s,%s,%s,%s,%s)",(academia_inicial,"Plano Gratuito",0,"MENSAL","Plano sem cobrança"))
    con.commit()
    con.close()

def login_required(fn):
    @wraps(fn)
    def wrap(*a, **kw):
        if not session.get("uid"):
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return wrap

def aid():
    return session.get("academia_id")

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
.top{background:#111827;color:white;padding:14px 18px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0}
.brand{font-size:21px;font-weight:800}.brand b{color:#22c55e}
.wrap{max-width:1150px;margin:auto;padding:18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.card{background:white;border-radius:16px;padding:16px;box-shadow:0 2px 12px #00000010}
.big{font-size:28px;font-weight:800}.muted{color:#6b7280}
.nav-wrap{max-width:1150px;margin:auto;padding:14px 18px 0}
.nav{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.nav a.btn{min-height:120px;border-radius:22px;padding:20px 22px;display:flex;align-items:center;gap:18px;text-align:left;box-shadow:0 4px 18px #00000018}
.nav-icon{font-size:48px;line-height:1;width:64px;text-align:center;flex:0 0 64px}
.nav-copy{display:flex;flex-direction:column;gap:4px;min-width:0;flex:1}
.nav-title{font-size:24px;font-weight:800;line-height:1.1}
.nav-desc{font-size:15px;color:#6b7280;font-weight:400;line-height:1.3}
.nav-arrow{font-size:42px;font-weight:800;color:#16a34a}
.nav a.danger .nav-desc,.nav a.danger .nav-arrow{color:#fee2e2}
a.btn,button{border:0;border-radius:10px;padding:11px 14px;background:#111827;color:white;text-decoration:none;cursor:pointer}
a.green,button.green{background:#16a34a} a.light{background:white;color:#111827;border:1px solid #ddd}
input,select,textarea{width:100%;padding:11px;border:1px solid #d1d5db;border-radius:10px;margin:5px 0 12px}
label{font-size:13px;font-weight:700} table{width:100%;border-collapse:collapse;background:white}
th,td{text-align:left;padding:10px;border-bottom:1px solid #eee}.pill{padding:5px 8px;border-radius:99px;background:#dcfce7;font-size:12px}
h1{margin-top:5px}.actions{display:flex;gap:8px;flex-wrap:wrap}.danger{background:#dc2626!important}
@media(max-width:760px){
  .wrap{padding:14px}.top{padding:14px 16px}.big{font-size:24px}
  .nav-wrap{padding:16px 10px 10px}
  .nav{grid-template-columns:1fr;gap:16px}
  .nav a.btn{min-height:140px;padding:24px 22px;border-radius:24px}
  .nav-icon{font-size:58px;width:74px;flex-basis:74px}
  .nav-title{font-size:30px}
  .nav-desc{font-size:17px}
  .nav-arrow{font-size:50px}
  th:nth-child(n+4),td:nth-child(n+4){display:none}
}
</style></head><body>
<div class="top"><div class="brand"><img src="/static/img/logo_tatameone.png" alt="TatameOne" style="height:72px;width:clamp(230px,55vw,420px);max-width:65vw;object-fit:contain;object-position:left center;display:block"></div><div>{{session.get('nome','')}}</div></div>
{% if session.get('uid') and request.path == '/' %}
<div class="nav-wrap"><div class="nav">
<a class="btn light" href="/painel"><span class="nav-icon">📊</span><span class="nav-copy"><span class="nav-title">Painel</span><span class="nav-desc">Visão geral da academia</span></span><span class="nav-arrow">›</span></a>
<a class="btn light" href="/alunos"><span class="nav-icon">👥</span><span class="nav-copy"><span class="nav-title">Alunos</span><span class="nav-desc">Cadastros e acompanhamento</span></span><span class="nav-arrow">›</span></a>
<a class="btn light" href="/checkin"><span class="nav-icon">✅</span><span class="nav-copy"><span class="nav-title">Check-in</span><span class="nav-desc">Registrar entrada dos alunos</span></span><span class="nav-arrow">›</span></a>
<a class="btn light" href="/planos"><span class="nav-icon">💳</span><span class="nav-copy"><span class="nav-title">Planos</span><span class="nav-desc">Planos e mensalidades</span></span><span class="nav-arrow">›</span></a>
<a class="btn light" href="/financeiro"><span class="nav-icon">💰</span><span class="nav-copy"><span class="nav-title">Financeiro</span><span class="nav-desc">Pagamentos e recebimentos</span></span><span class="nav-arrow">›</span></a>
<a class="btn light" href="/aulas"><span class="nav-icon">📅</span><span class="nav-copy"><span class="nav-title">Aulas</span><span class="nav-desc">Agenda, horários e professores</span></span><span class="nav-arrow">›</span></a>
<a class="btn light" href="/avaliacoes"><span class="nav-icon">📈</span><span class="nav-copy"><span class="nav-title">Avaliações</span><span class="nav-desc">Avaliações e evolução</span></span><span class="nav-arrow">›</span></a>
<a class="btn light" href="/config"><span class="nav-icon">⚙️</span><span class="nav-copy"><span class="nav-title">Configurações</span><span class="nav-desc">Dados e modalidades</span></span><span class="nav-arrow">›</span></a>
<a class="btn danger" href="/logout"><span class="nav-icon">🚪</span><span class="nav-copy"><span class="nav-title">Sair</span><span class="nav-desc">Encerrar sessão</span></span><span class="nav-arrow">›</span></a>
</div></div>
{% endif %}
{% if session.get('uid') and request.path != '/' %}
<div style="max-width:1150px;margin:14px auto 0;padding:0 18px">
<a href="/" style="display:inline-flex;align-items:center;gap:8px;background:#111827;color:white;text-decoration:none;padding:11px 16px;border-radius:10px;font-weight:700">← Voltar ao Painel</a>
</div>
{% endif %}
<div class="wrap">{{body|safe}}</div></body></html>
"""

def page(title, body, **ctx):
    inner = render_template_string(body, **ctx)
    return render_template_string(BASE, title=title, body=inner)

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

@app.route("/login", methods=["GET","POST"])
def login():
    erro=""
    if request.method=="POST":
        con=db()
        u=con.cursor().execute("SELECT * FROM usuarios WHERE lower(email)=lower(%s) AND senha=%s AND ativo=1",
                      (request.form["email"].strip(),request.form["senha"])).fetchone()
        con.close()
        if u:
            session.update(uid=u["id"], academia_id=u["academia_id"], nome=u["nome"], perfil=u["perfil"])
            return redirect("/")
        erro="E-mail ou senha inválidos."
    return page("Entrar","""
    <div class="card" style="max-width:430px;margin:7vh auto"><h1>Entrar</h1>
    <p class="muted">Gestão completa para academias.</p>
    {% if erro %}<p style="color:#dc2626">{{erro}}</p>{% endif %}
    <form method="post"><label>E-mail</label><input name="email" type="email" required value="admin@tatameone.local">
    <label>Senha</label><input name="senha" type="password" required value="1234">
    <button class="green" style="width:100%">Entrar</button></form></div>""", erro=erro)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
@login_required
def inicio():
    return page("Início", "")

@app.route("/painel")
@login_required
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
    <h1>{{ac.nome}}</h1><p class="muted">Visão geral da academia · Plano {{ac.plano}}</p>
    <div class="grid">
      <div class="card"><div class="muted">Alunos ativos</div><div class="big">{{s.alunos}}</div></div>
      <div class="card"><div class="muted">Check-ins hoje</div><div class="big">{{s.checkins}}</div></div>
      <div class="card"><div class="muted">Receita registrada</div><div class="big">R$ {{'%.2f'|format(s.receita)}}</div></div>
      <div class="card"><div class="muted">Aulas cadastradas</div><div class="big">{{s.aulas}}</div></div>
    </div><br>
    <div class="grid"><a class="btn green" href="/alunos/novo">+ Novo aluno</a>
    <a class="btn" href="/checkin">✓ Fazer check-in</a><a class="btn" href="/financeiro">R$ Registrar pagamento</a></div>
    """,s=stats,ac=ac)

@app.route("/alunos")
@login_required
def alunos():
    con=db()
    rows=con.cursor().execute("SELECT * FROM alunos WHERE academia_id=%s ORDER BY nome",(aid(),)).fetchall()
    pendentes=con.cursor().execute("SELECT * FROM pre_cadastros WHERE academia_id=%s AND status='PENDENTE' ORDER BY id DESC",(aid(),)).fetchall()
    con.close()
    link_publico=request.url_root.rstrip("/")+"/cadastro/"+str(aid())
    return page("Alunos","""
    <div class="actions"><h1 style="flex:1">Alunos</h1><a class="btn green" href="/alunos/novo">+ Novo aluno</a></div>
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
        foto_nome=None
        foto=request.files.get("foto_camera")
        if not foto or not foto.filename:
            foto=request.files.get("foto")
        if foto and foto.filename:
            ext=os.path.splitext(foto.filename)[1].lower()
            if ext in (".jpg",".jpeg",".png",".webp"):
                os.makedirs("static/alunos",exist_ok=True)
                foto_nome=secrets.token_hex(12)+ext
                foto.save(os.path.join("static/alunos",foto_nome))
        con.cursor().execute("""INSERT INTO pre_cadastros(
        academia_id,nome,documento,nascimento,telefone,email,responsavel,telefone_responsavel,
        modalidade,graduacao,observacoes,status,criado_em,endereco,contato_emergencia,telefone_emergencia,foto)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'PENDENTE',%s,%s,%s,%s,%s)""",
        (academia_id,f["nome"],f.get("documento"),f.get("nascimento"),f.get("telefone"),f.get("email"),
         f.get("responsavel"),f.get("telefone_responsavel"),f.get("modalidade"),f.get("graduacao"),
         f.get("observacoes"),agora(),f.get("endereco"),f.get("contato_emergencia"),f.get("telefone_emergencia"),foto_nome))
        con.commit();con.close()
        return public_page("Cadastro enviado","""
        <div class="card" style="max-width:620px;margin:7vh auto;text-align:center">
        <div style="font-size:70px">✅</div><h1>Cadastro enviado com sucesso!</h1>
        <p>Seus dados foram enviados para <b>{{nome}}</b>.</p>
        <div class="ok">Aguarde a análise da academia. Não é necessário instalar o aplicativo.</div></div>""",ac,nome=ac["nome"])
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
def aprovar_pre_cadastro(id):
    con=db()
    p=con.cursor().execute("SELECT * FROM pre_cadastros WHERE id=%s AND academia_id=%s AND status='PENDENTE'",(id,aid())).fetchone()
    if p:
        con.cursor().execute("""INSERT INTO alunos(academia_id,nome,documento,nascimento,telefone,email,responsavel,
        telefone_responsavel,modalidade,graduacao,observacoes,qr_token,criado_em,endereco,
        contato_emergencia,telefone_emergencia,foto)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (aid(),p["nome"],p["documento"],p["nascimento"],p["telefone"],p["email"],p["responsavel"],
         p["telefone_responsavel"],p["modalidade"],p["graduacao"],p["observacoes"],secrets.token_hex(8),agora(),
         p["endereco"],p["contato_emergencia"],p["telefone_emergencia"],p["foto"]))
        con.cursor().execute("UPDATE pre_cadastros SET status='APROVADO' WHERE id=%s",(id,))
        con.commit()
    con.close()
    return redirect("/alunos")

@app.route("/alunos/pre-cadastro/<int:id>/recusar")
@login_required
def recusar_pre_cadastro(id):
    con=db()
    con.cursor().execute("UPDATE pre_cadastros SET status='RECUSADO' WHERE id=%s AND academia_id=%s",(id,aid()))
    con.commit()
    con.close()
    return redirect("/alunos")

@app.route("/alunos/novo", methods=["GET","POST"])
@login_required
def aluno_novo():
    con=db()
    mods=con.cursor().execute("SELECT nome FROM modalidades WHERE academia_id=%s AND ativo=1 ORDER BY nome",(aid(),)).fetchall()

    if request.method=="POST":
        f=request.form

        foto_nome=None
        foto=request.files.get("foto_camera")
        if not foto or not foto.filename:
            foto=request.files.get("foto")
        if foto and foto.filename:
            ext=os.path.splitext(foto.filename)[1].lower()
            if ext in (".jpg",".jpeg",".png",".webp"):
                os.makedirs("static/alunos",exist_ok=True)
                foto_nome=secrets.token_hex(12)+ext
                foto.save(os.path.join("static/alunos",foto_nome))

        con.cursor().execute("""INSERT INTO alunos(
            academia_id,nome,documento,nascimento,telefone,email,
            responsavel,telefone_responsavel,modalidade,graduacao,
            observacoes,qr_token,criado_em,endereco,
            contato_emergencia,telefone_emergencia,foto
        ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
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
            foto_nome
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
        <img src="/static/alunos/{{x.foto}}"
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
            con.cursor().execute(
                "INSERT INTO checkins(academia_id,aluno_id,entrada) VALUES(%s,%s,%s)",
                (aid(),x["id"],agora())
            )
            con.commit()
            msg="Check-in confirmado: "+x["nome"]
        else:
            msg="Aluno não encontrado ou inativo."

    recentes=con.cursor().execute("""
        SELECT c.entrada,a.nome
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
        <p><b>{{r.nome}}</b> · {{r.entrada}}</p>
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


@app.route("/planos", methods=["GET","POST"])
@login_required
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
    <div class="card">{% for x in rows %}<p><b>{{x.nome}}</b><br>R$ {{'%.2f'|format(x.valor)}} · {{x.periodicidade}}</p>{% endfor %}</div></div>""",rows=rows)

@app.route("/financeiro", methods=["GET","POST"])
@login_required
def financeiro():
    con=db()
    alunos=con.cursor().execute("SELECT id,nome FROM alunos WHERE academia_id=%s AND ativo=1 ORDER BY nome",(aid(),)).fetchall()
    if request.method=="POST":
        f=request.form
        con.cursor().execute("INSERT INTO pagamentos(academia_id,aluno_id,referencia,valor,forma,status,pago_em) VALUES(%s,%s,%s,%s,%s,'PAGO',%s)",
                    (aid(),f["aluno_id"],f["referencia"],float(f["valor"]),f["forma"],agora()))
        con.cursor().execute("INSERT INTO caixa(academia_id,tipo,descricao,valor,forma,data) VALUES(%s,'ENTRADA',%s,%s,%s,%s)",
                    (aid(),"Mensalidade "+f["referencia"],float(f["valor"]),f["forma"],agora()))
        con.commit()
    pags=con.cursor().execute("""SELECT p.*,a.nome FROM pagamentos p JOIN alunos a ON a.id=p.aluno_id
    WHERE p.academia_id=%s ORDER BY p.id DESC LIMIT 30""",(aid(),)).fetchall()
    total=con.cursor().execute("SELECT COALESCE(SUM(valor),0)n FROM pagamentos WHERE academia_id=%s AND status='PAGO'",(aid(),)).fetchone()["n"]
    con.close()
    return page("Financeiro","""
    <h1>Financeiro</h1><div class="card"><div class="muted">Total recebido</div><div class="big">R$ {{'%.2f'|format(total)}}</div></div><br>
    <div class="grid"><div class="card"><h2>Registrar pagamento</h2><form method="post">
    <label>Aluno</label><select name="aluno_id" required>{% for a in alunos %}<option value="{{a.id}}">{{a.nome}}</option>{% endfor %}</select>
    <label>Referência</label><input name="referencia" placeholder="08/2026" required><label>Valor</label><input type="number" step=".01" name="valor" required>
    <label>Forma</label><select name="forma"><option>PIX</option><option>DINHEIRO</option><option>DÉBITO</option><option>CRÉDITO</option><option>BOLETO</option></select>
    <button class="green">Registrar</button></form></div><div class="card"><h2>Últimos recebimentos</h2>
    {% for p in pags %}<p><b>{{p.nome}}</b> · R$ {{'%.2f'|format(p.valor)}}<br><span class="muted">{{p.referencia}} · {{p.forma}} · {{p.pago_em}}</span></p>{% endfor %}</div></div>
    """,alunos=alunos,pags=pags,total=total)

@app.route("/aulas", methods=["GET","POST"])
@login_required
def aulas():
    con=db()
    if request.method=="POST":
        f=request.form
        con.cursor().execute("INSERT INTO aulas(academia_id,modalidade,professor,dia,horario,capacidade) VALUES(%s,%s,%s,%s,%s,%s)",
                    (aid(),f["modalidade"],f.get("professor"),f.get("dia"),f.get("horario"),int(f.get("capacidade") or 20)))
        con.commit()
    rows=con.cursor().execute("SELECT * FROM aulas WHERE academia_id=%s AND ativo=1 ORDER BY dia,horario",(aid(),)).fetchall(); con.close()
    return page("Aulas","""
    <h1>Agenda de aulas</h1><div class="grid"><div class="card"><form method="post"><label>Modalidade</label><input name="modalidade" required>
    <label>Professor</label><input name="professor"><label>Dia</label><select name="dia"><option>Segunda</option><option>Terça</option><option>Quarta</option><option>Quinta</option><option>Sexta</option><option>Sábado</option><option>Domingo</option></select>
    <label>Horário</label><input type="time" name="horario"><label>Capacidade</label><input type="number" name="capacidade" value="20">
    <button class="green">Cadastrar aula</button></form></div><div class="card">{% for x in rows %}<p><b>{{x.modalidade}}</b> · {{x.dia}} {{x.horario}}<br>{{x.professor or 'Professor não definido'}} · {{x.capacidade}} vagas</p>{% endfor %}</div></div>""",rows=rows)

@app.route("/avaliacoes", methods=["GET","POST"])
@login_required
def avaliacoes():
    con=db(); alunos=con.cursor().execute("SELECT id,nome FROM alunos WHERE academia_id=%s AND ativo=1 ORDER BY nome",(aid(),)).fetchall()
    if request.method=="POST":
        f=request.form
        con.cursor().execute("""INSERT INTO avaliacoes(academia_id,aluno_id,data,peso,altura,gordura,cintura,braco,observacoes)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",(aid(),f["aluno_id"],f["data"],f.get("peso") or None,f.get("altura") or None,
        f.get("gordura") or None,f.get("cintura") or None,f.get("braco") or None,f.get("observacoes")))
        con.commit()
    rows=con.cursor().execute("""SELECT v.*,a.nome FROM avaliacoes v JOIN alunos a ON a.id=v.aluno_id
    WHERE v.academia_id=%s ORDER BY v.id DESC LIMIT 30""",(aid(),)).fetchall(); con.close()
    return page("Avaliações","""
    <h1>Avaliações e evolução</h1><div class="grid"><div class="card"><form method="post">
    <label>Aluno</label><select name="aluno_id">{% for a in alunos %}<option value="{{a.id}}">{{a.nome}}</option>{% endfor %}</select>
    <label>Data</label><input type="date" name="data" required><div class="grid"><div><label>Peso (kg)</label><input name="peso" type="number" step=".01"></div>
    <div><label>Altura (m)</label><input name="altura" type="number" step=".01"></div><div><label>Gordura %</label><input name="gordura" type="number" step=".01"></div>
    <div><label>Cintura (cm)</label><input name="cintura" type="number" step=".01"></div><div><label>Braço (cm)</label><input name="braco" type="number" step=".01"></div></div>
    <label>Observações</label><textarea name="observacoes"></textarea><button class="green">Salvar avaliação</button></form></div>
    <div class="card">{% for x in rows %}<p><b>{{x.nome}}</b> · {{x.data}}<br>Peso: {{x.peso or '-'}} kg · Gordura: {{x.gordura or '-'}}%</p>{% endfor %}</div></div>""",alunos=alunos,rows=rows)

@app.route("/config", methods=["GET","POST"])
@login_required
def config():
    con=db()
    if request.method=="POST":
        f=request.form
        con.cursor().execute("""UPDATE academias SET nome=%s,documento=%s,telefone=%s,endereco=%s,cor=%s WHERE id=%s""",
                    (f["nome"],f.get("documento"),f.get("telefone"),f.get("endereco"),f.get("cor"),aid()))
        con.commit()
    ac=con.cursor().execute("SELECT * FROM academias WHERE id=%s",(aid(),)).fetchone()
    mods=con.cursor().execute("SELECT * FROM modalidades WHERE academia_id=%s ORDER BY nome",(aid(),)).fetchall()
    con.close()
    return page("Configurações","""
    <h1>Configurações</h1><div class="grid"><div class="card"><h2>Academia</h2><form method="post">
    <label>Nome</label><input name="nome" value="{{ac.nome}}" required><label>CNPJ/CPF</label><input name="documento" value="{{ac.documento or ''}}">
    <label>Telefone</label><input name="telefone" value="{{ac.telefone or ''}}"><label>Endereço</label><input name="endereco" value="{{ac.endereco or ''}}">
    <label>Cor principal</label><input type="color" name="cor" value="{{ac.cor or '#111827'}}"><button class="green">Salvar</button></form></div>
    <div class="card"><h2>Modalidades disponíveis</h2>{% for m in mods %}<span class="pill">{{m.nome}}</span> {% endfor %}
    <p class="muted">A estrutura aceita modalidades diferentes por academia.</p><h3>Plano do sistema</h3><p>{{ac.plano}}</p></div></div>""",ac=ac,mods=mods)

# Inicializa o banco também quando o aplicativo é carregado pelo Gunicorn/Render.
# init_db usa CREATE TABLE IF NOT EXISTS, portanto pode ser executado com segurança.
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=False)

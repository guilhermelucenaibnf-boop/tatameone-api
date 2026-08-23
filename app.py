import os
import sqlite3
import secrets
from datetime import datetime
from functools import wraps
from flask import Flask, request, redirect, url_for, session, render_template_string, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tatameone-2-troque-em-producao")
DB = os.environ.get("TATAMEONE_DB", "tatameone.db")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    con = db()
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS academias(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      nome TEXT NOT NULL,
      documento TEXT,
      telefone TEXT,
      endereco TEXT,
      logo TEXT,
      cor TEXT DEFAULT '#111827',
      plano TEXT DEFAULT 'GRATUITO',
      ativo INTEGER DEFAULT 1,
      criado_em TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS usuarios(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      academia_id INTEGER,
      nome TEXT NOT NULL,
      email TEXT UNIQUE NOT NULL,
      senha TEXT NOT NULL,
      perfil TEXT NOT NULL DEFAULT 'ADMIN',
      ativo INTEGER DEFAULT 1,
      criado_em TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS modalidades(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      academia_id INTEGER NOT NULL,
      nome TEXT NOT NULL,
      ativo INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS alunos(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      academia_id INTEGER NOT NULL,
      nome TEXT NOT NULL,
      documento TEXT,
      nascimento TEXT,
      telefone TEXT,
      email TEXT,
      responsavel TEXT,
      telefone_responsavel TEXT,
      modalidade TEXT,
      graduacao TEXT,
      observacoes TEXT,
      qr_token TEXT UNIQUE,
      ativo INTEGER DEFAULT 1,
      criado_em TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS planos(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      academia_id INTEGER NOT NULL,
      nome TEXT NOT NULL,
      valor REAL DEFAULT 0,
      periodicidade TEXT DEFAULT 'MENSAL',
      descricao TEXT,
      ativo INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS matriculas(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      academia_id INTEGER NOT NULL,
      aluno_id INTEGER NOT NULL,
      plano_id INTEGER,
      inicio TEXT,
      vencimento_dia INTEGER DEFAULT 10,
      valor REAL DEFAULT 0,
      status TEXT DEFAULT 'ATIVA'
    );
    CREATE TABLE IF NOT EXISTS pagamentos(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      academia_id INTEGER NOT NULL,
      aluno_id INTEGER NOT NULL,
      referencia TEXT,
      valor REAL NOT NULL,
      forma TEXT DEFAULT 'PIX',
      status TEXT DEFAULT 'PAGO',
      pago_em TEXT
    );
    CREATE TABLE IF NOT EXISTS checkins(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      academia_id INTEGER NOT NULL,
      aluno_id INTEGER NOT NULL,
      entrada TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS professores(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      academia_id INTEGER NOT NULL,
      nome TEXT NOT NULL,
      telefone TEXT,
      email TEXT,
      especialidade TEXT,
      ativo INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS aulas(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      academia_id INTEGER NOT NULL,
      modalidade TEXT NOT NULL,
      professor TEXT,
      dia TEXT,
      horario TEXT,
      capacidade INTEGER DEFAULT 20,
      ativo INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS avaliacoes(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      academia_id INTEGER NOT NULL,
      aluno_id INTEGER NOT NULL,
      data TEXT NOT NULL,
      peso REAL,
      altura REAL,
      gordura REAL,
      cintura REAL,
      braco REAL,
      observacoes TEXT
    );
    CREATE TABLE IF NOT EXISTS treinos(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      academia_id INTEGER NOT NULL,
      aluno_id INTEGER NOT NULL,
      titulo TEXT NOT NULL,
      descricao TEXT,
      criado_em TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS caixa(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      academia_id INTEGER NOT NULL,
      tipo TEXT NOT NULL,
      descricao TEXT,
      valor REAL NOT NULL,
      forma TEXT,
      data TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS avisos(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      academia_id INTEGER NOT NULL,
      titulo TEXT NOT NULL,
      mensagem TEXT NOT NULL,
      criado_em TEXT NOT NULL
    );
    """)
    # instalação inicial
    if cur.execute("SELECT COUNT(*) n FROM academias").fetchone()["n"] == 0:
        cur.execute("INSERT INTO academias(nome,plano,criado_em) VALUES(?,?,?)",
                    ("TatameOne Demonstração","PREMIUM",agora()))
        aid = cur.lastrowid
        cur.execute("""INSERT INTO usuarios(academia_id,nome,email,senha,perfil,criado_em)
                       VALUES(?,?,?,?,?,?)""",
                    (aid,"Administrador","admin@tatameone.local","1234","DONO",agora()))
        for m in ("Musculação","Jiu-Jítsu","Muay Thai","Boxe","Funcional","Cross Training",
                  "Pilates","Yoga","Dança","Natação","Personal"):
            cur.execute("INSERT INTO modalidades(academia_id,nome) VALUES(?,?)",(aid,m))
        cur.execute("""INSERT INTO planos(academia_id,nome,valor,periodicidade,descricao)
                       VALUES(?,?,?,?,?)""",(aid,"Plano Gratuito",0,"MENSAL","Plano sem cobrança"))
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
<style>
*{box-sizing:border-box} body{margin:0;font-family:Arial,sans-serif;background:#f3f4f6;color:#111827}
.top{background:#111827;color:white;padding:14px 18px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0}
.brand{font-size:21px;font-weight:800}.brand b{color:#22c55e}
.wrap{max-width:1150px;margin:auto;padding:18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.card{background:white;border-radius:16px;padding:16px;box-shadow:0 2px 12px #00000010}
.big{font-size:28px;font-weight:800}.muted{color:#6b7280}.nav{display:flex;gap:8px;overflow:auto;padding:10px 0}
a.btn,button{border:0;border-radius:10px;padding:11px 14px;background:#111827;color:white;text-decoration:none;cursor:pointer}
a.green,button.green{background:#16a34a} a.light{background:white;color:#111827;border:1px solid #ddd}
input,select,textarea{width:100%;padding:11px;border:1px solid #d1d5db;border-radius:10px;margin:5px 0 12px}
label{font-size:13px;font-weight:700} table{width:100%;border-collapse:collapse;background:white}
th,td{text-align:left;padding:10px;border-bottom:1px solid #eee}.pill{padding:5px 8px;border-radius:99px;background:#dcfce7;font-size:12px}
h1{margin-top:5px}.actions{display:flex;gap:8px;flex-wrap:wrap}.danger{background:#dc2626!important}
@media(max-width:600px){.wrap{padding:12px}.top{padding:12px}.big{font-size:24px}th:nth-child(n+4),td:nth-child(n+4){display:none}}
</style></head><body>
<div class="top"><div class="brand">TATAME<b>ONE</b></div><div>{{session.get('nome','')}}</div></div>
{% if session.get('uid') %}
<div class="wrap"><div class="nav">
<a class="btn light" href="/">Painel</a><a class="btn light" href="/alunos">Alunos</a>
<a class="btn light" href="/checkin">Check-in</a><a class="btn light" href="/planos">Planos</a>
<a class="btn light" href="/financeiro">Financeiro</a><a class="btn light" href="/aulas">Aulas</a>
<a class="btn light" href="/avaliacoes">Avaliações</a><a class="btn light" href="/config">Configurações</a>
<a class="btn danger" href="/logout">Sair</a></div></div>
{% endif %}
<div class="wrap">{{body|safe}}</div></body></html>
"""

def page(title, body, **ctx):
    inner = render_template_string(body, **ctx)
    return render_template_string(BASE, title=title, body=inner)

@app.route("/login", methods=["GET","POST"])
def login():
    erro=""
    if request.method=="POST":
        con=db()
        u=con.execute("SELECT * FROM usuarios WHERE lower(email)=lower(?) AND senha=? AND ativo=1",
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
def dashboard():
    con=db()
    stats={
      "alunos":con.execute("SELECT COUNT(*) n FROM alunos WHERE academia_id=? AND ativo=1",(aid(),)).fetchone()["n"],
      "checkins":con.execute("SELECT COUNT(*) n FROM checkins WHERE academia_id=? AND date(entrada)=date('now','localtime')",(aid(),)).fetchone()["n"],
      "receita":con.execute("SELECT COALESCE(SUM(valor),0) n FROM pagamentos WHERE academia_id=? AND status='PAGO'",(aid(),)).fetchone()["n"],
      "aulas":con.execute("SELECT COUNT(*) n FROM aulas WHERE academia_id=? AND ativo=1",(aid(),)).fetchone()["n"]
    }
    ac=con.execute("SELECT * FROM academias WHERE id=?",(aid(),)).fetchone()
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
    con=db(); rows=con.execute("SELECT * FROM alunos WHERE academia_id=? ORDER BY nome",(aid(),)).fetchall(); con.close()
    return page("Alunos","""
    <div class="actions"><h1 style="flex:1">Alunos</h1><a class="btn green" href="/alunos/novo">+ Novo aluno</a></div>
    <div style="overflow:auto"><table><tr><th>Nome</th><th>Modalidade</th><th>Telefone</th><th>Status</th><th>Ação</th></tr>
    {% for x in rows %}<tr><td><b>{{x.nome}}</b></td><td>{{x.modalidade or '-'}}</td><td>{{x.telefone or '-'}}</td>
    <td><span class="pill">{{'ATIVO' if x.ativo else 'INATIVO'}}</span></td><td><a href="/alunos/{{x.id}}">Abrir</a></td></tr>{% endfor %}
    </table></div>""",rows=rows)

@app.route("/alunos/novo", methods=["GET","POST"])
@login_required
def aluno_novo():
    con=db()
    mods=con.execute("SELECT nome FROM modalidades WHERE academia_id=? AND ativo=1 ORDER BY nome",(aid(),)).fetchall()
    if request.method=="POST":
        f=request.form
        con.execute("""INSERT INTO alunos(academia_id,nome,documento,nascimento,telefone,email,responsavel,
        telefone_responsavel,modalidade,graduacao,observacoes,qr_token,criado_em)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",(aid(),f["nome"],f.get("documento"),f.get("nascimento"),f.get("telefone"),
        f.get("email"),f.get("responsavel"),f.get("telefone_responsavel"),f.get("modalidade"),f.get("graduacao"),
        f.get("observacoes"),secrets.token_hex(8),agora()))
        con.commit(); con.close(); return redirect("/alunos")
    con.close()
    return page("Novo aluno","""
    <h1>Novo aluno</h1><div class="card"><form method="post">
    <div class="grid"><div><label>Nome completo</label><input name="nome" required></div><div><label>CPF/Documento</label><input name="documento"></div>
    <div><label>Nascimento</label><input type="date" name="nascimento"></div><div><label>Telefone</label><input name="telefone"></div>
    <div><label>E-mail</label><input type="email" name="email"></div><div><label>Modalidade</label><select name="modalidade">
    <option value="">Selecione</option>{% for m in mods %}<option>{{m.nome}}</option>{% endfor %}</select></div>
    <div><label>Graduação/Faixa</label><input name="graduacao"></div><div><label>Responsável</label><input name="responsavel"></div>
    <div><label>Telefone responsável</label><input name="telefone_responsavel"></div></div>
    <label>Observações</label><textarea name="observacoes"></textarea><button class="green">Salvar aluno</button></form></div>""",mods=mods)

@app.route("/alunos/<int:id>")
@login_required
def aluno(id):
    con=db()
    x=con.execute("SELECT * FROM alunos WHERE id=? AND academia_id=?",(id,aid())).fetchone()
    pags=con.execute("SELECT * FROM pagamentos WHERE aluno_id=? AND academia_id=? ORDER BY id DESC LIMIT 10",(id,aid())).fetchall()
    checks=con.execute("SELECT * FROM checkins WHERE aluno_id=? AND academia_id=? ORDER BY id DESC LIMIT 10",(id,aid())).fetchall()
    con.close()
    if not x:return "Aluno não encontrado",404
    return page(x["nome"],"""
    <h1>{{x.nome}}</h1><p><span class="pill">{{x.modalidade or 'Sem modalidade'}}</span> {{x.graduacao or ''}}</p>
    <div class="grid"><div class="card"><b>Telefone</b><p>{{x.telefone or '-'}}</p></div>
    <div class="card"><b>QR/Token de check-in</b><p>{{x.qr_token}}</p></div></div><br>
    <div class="card"><h2>Últimos check-ins</h2>{% for c in checks %}<p>{{c.entrada}}</p>{% else %}<p class="muted">Nenhum.</p>{% endfor %}</div><br>
    <div class="card"><h2>Pagamentos</h2>{% for p in pags %}<p>{{p.referencia}} · R$ {{'%.2f'|format(p.valor)}} · {{p.forma}}</p>{% else %}<p class="muted">Nenhum.</p>{% endfor %}</div>
    """,x=x,pags=pags,checks=checks)

@app.route("/checkin", methods=["GET","POST"])
@login_required
def checkin():
    msg=""
    con=db()
    if request.method=="POST":
        busca=request.form["busca"].strip()
        x=con.execute("""SELECT * FROM alunos WHERE academia_id=? AND ativo=1 AND
        (qr_token=? OR lower(nome) LIKE lower(?)) LIMIT 1""",(aid(),busca,"%"+busca+"%")).fetchone()
        if x:
            con.execute("INSERT INTO checkins(academia_id,aluno_id,entrada) VALUES(?,?,?)",(aid(),x["id"],agora()))
            con.commit(); msg="Check-in confirmado: "+x["nome"]
        else: msg="Aluno não encontrado ou inativo."
    recentes=con.execute("""SELECT c.entrada,a.nome FROM checkins c JOIN alunos a ON a.id=c.aluno_id
    WHERE c.academia_id=? ORDER BY c.id DESC LIMIT 12""",(aid(),)).fetchall()
    con.close()
    return page("Check-in","""
    <h1>Check-in</h1><div class="card"><form method="post"><label>Nome ou token do QR Code</label>
    <input name="busca" autofocus required placeholder="Digite o nome ou leia o QR"><button class="green">Confirmar entrada</button></form>
    {% if msg %}<h3>{{msg}}</h3>{% endif %}</div><br><div class="card"><h2>Recentes</h2>
    {% for r in recentes %}<p><b>{{r.nome}}</b> · {{r.entrada}}</p>{% endfor %}</div>""",msg=msg,recentes=recentes)

@app.route("/planos", methods=["GET","POST"])
@login_required
def planos():
    con=db()
    if request.method=="POST":
        con.execute("INSERT INTO planos(academia_id,nome,valor,periodicidade,descricao) VALUES(?,?,?,?,?)",
                    (aid(),request.form["nome"],float(request.form["valor"] or 0),request.form["periodicidade"],request.form.get("descricao")))
        con.commit()
    rows=con.execute("SELECT * FROM planos WHERE academia_id=? ORDER BY id DESC",(aid(),)).fetchall(); con.close()
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
    alunos=con.execute("SELECT id,nome FROM alunos WHERE academia_id=? AND ativo=1 ORDER BY nome",(aid(),)).fetchall()
    if request.method=="POST":
        f=request.form
        con.execute("INSERT INTO pagamentos(academia_id,aluno_id,referencia,valor,forma,status,pago_em) VALUES(?,?,?,?,?,'PAGO',?)",
                    (aid(),f["aluno_id"],f["referencia"],float(f["valor"]),f["forma"],agora()))
        con.execute("INSERT INTO caixa(academia_id,tipo,descricao,valor,forma,data) VALUES(?,'ENTRADA',?,?,?,?)",
                    (aid(),"Mensalidade "+f["referencia"],float(f["valor"]),f["forma"],agora()))
        con.commit()
    pags=con.execute("""SELECT p.*,a.nome FROM pagamentos p JOIN alunos a ON a.id=p.aluno_id
    WHERE p.academia_id=? ORDER BY p.id DESC LIMIT 30""",(aid(),)).fetchall()
    total=con.execute("SELECT COALESCE(SUM(valor),0)n FROM pagamentos WHERE academia_id=? AND status='PAGO'",(aid(),)).fetchone()["n"]
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
        con.execute("INSERT INTO aulas(academia_id,modalidade,professor,dia,horario,capacidade) VALUES(?,?,?,?,?,?)",
                    (aid(),f["modalidade"],f.get("professor"),f.get("dia"),f.get("horario"),int(f.get("capacidade") or 20)))
        con.commit()
    rows=con.execute("SELECT * FROM aulas WHERE academia_id=? AND ativo=1 ORDER BY dia,horario",(aid(),)).fetchall(); con.close()
    return page("Aulas","""
    <h1>Agenda de aulas</h1><div class="grid"><div class="card"><form method="post"><label>Modalidade</label><input name="modalidade" required>
    <label>Professor</label><input name="professor"><label>Dia</label><select name="dia"><option>Segunda</option><option>Terça</option><option>Quarta</option><option>Quinta</option><option>Sexta</option><option>Sábado</option><option>Domingo</option></select>
    <label>Horário</label><input type="time" name="horario"><label>Capacidade</label><input type="number" name="capacidade" value="20">
    <button class="green">Cadastrar aula</button></form></div><div class="card">{% for x in rows %}<p><b>{{x.modalidade}}</b> · {{x.dia}} {{x.horario}}<br>{{x.professor or 'Professor não definido'}} · {{x.capacidade}} vagas</p>{% endfor %}</div></div>""",rows=rows)

@app.route("/avaliacoes", methods=["GET","POST"])
@login_required
def avaliacoes():
    con=db(); alunos=con.execute("SELECT id,nome FROM alunos WHERE academia_id=? AND ativo=1 ORDER BY nome",(aid(),)).fetchall()
    if request.method=="POST":
        f=request.form
        con.execute("""INSERT INTO avaliacoes(academia_id,aluno_id,data,peso,altura,gordura,cintura,braco,observacoes)
        VALUES(?,?,?,?,?,?,?,?,?)""",(aid(),f["aluno_id"],f["data"],f.get("peso") or None,f.get("altura") or None,
        f.get("gordura") or None,f.get("cintura") or None,f.get("braco") or None,f.get("observacoes")))
        con.commit()
    rows=con.execute("""SELECT v.*,a.nome FROM avaliacoes v JOIN alunos a ON a.id=v.aluno_id
    WHERE v.academia_id=? ORDER BY v.id DESC LIMIT 30""",(aid(),)).fetchall(); con.close()
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
        con.execute("""UPDATE academias SET nome=?,documento=?,telefone=?,endereco=?,cor=? WHERE id=?""",
                    (f["nome"],f.get("documento"),f.get("telefone"),f.get("endereco"),f.get("cor"),aid()))
        con.commit()
    ac=con.execute("SELECT * FROM academias WHERE id=?",(aid(),)).fetchone()
    mods=con.execute("SELECT * FROM modalidades WHERE academia_id=? ORDER BY nome",(aid(),)).fetchall()
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

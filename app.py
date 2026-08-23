# BRECHO G3 - instalador de versao inicial
# Execute: python app.py
import os, sqlite3, json, secrets, re, unicodedata, io, base64
from datetime import datetime
from urllib.parse import quote_plus
from flask import Flask, request, redirect, session, render_template_string

app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY","brecho-g3-2026")
DB="brechog3.db"
os.makedirs("static/produtos",exist_ok=True)



def crc16_ccitt(text):
    crc=0xFFFF
    for b in text.encode("utf-8"):
        crc ^= b << 8
        for _ in range(8):
            crc=((crc<<1)^0x1021)&0xFFFF if crc&0x8000 else (crc<<1)&0xFFFF
    return f"{crc:04X}"

def tlv(tag, value):
    value=str(value)
    return f"{tag}{len(value.encode('utf-8')):02d}{value}"

def pix_text(value, limit):
    value=unicodedata.normalize("NFKD", str(value or "")).encode("ASCII","ignore").decode()
    value=re.sub(r"[^A-Za-z0-9 .-]","",value).strip().upper()
    return value[:limit] or "BRECHO G3"

def pix_payload(chave, valor, nome="BRECHO G3", cidade="RIO DE JANEIRO", txid="***"):
    chave=str(chave or "").strip()
    if not chave: return ""
    merchant=tlv("00","BR.GOV.BCB.PIX")+tlv("01",chave)
    payload=(tlv("00","01")+tlv("26",merchant)+tlv("52","0000")+tlv("53","986"))
    if float(valor)>0: payload+=tlv("54",f"{float(valor):.2f}")
    payload+=tlv("58","BR")+tlv("59",pix_text(nome,25))+tlv("60",pix_text(cidade,15))
    payload+=tlv("62",tlv("05",pix_text(txid,25)))+"6304"
    return payload+crc16_ccitt(payload)

def qr_data_uri(text):
    try:
        import qrcode
        img=qrcode.make(text)
        b=io.BytesIO(); img.save(b,format="PNG")
        return "data:image/png;base64,"+base64.b64encode(b.getvalue()).decode()
    except Exception:
        return ""

CSS="""
*{box-sizing:border-box}html,body{margin:0;width:100%;min-height:100%;background:#000;color:#fff;font-family:Arial,sans-serif}body{font-size:17px}.app{width:100%;max-width:760px;min-height:100dvh;margin:auto;background:#000}header{padding:28px 16px 20px;text-align:center;border-bottom:1px solid #8a6422}.brandline{display:flex;justify-content:center;align-items:center;gap:12px}.brandicon{font-size:42px;color:#e7a92d}.logo{color:#e7a92d;font-size:34px;font-weight:900}.sub{font-size:13px;margin-top:7px;text-transform:uppercase}main{padding:22px 16px 38px}.box{background:linear-gradient(145deg,#171717,#090909);border:1px solid #8a6422;border-radius:22px;padding:20px;margin-bottom:16px}h2{font-size:27px}input,select,textarea{width:100%;padding:15px;margin:6px 0 12px;background:#1b1b1b;color:#fff;border:1px solid #66502a;border-radius:14px;font-size:16px}button,.btn{background:#e7a92d;color:#090909;border:0;border-radius:14px;padding:14px 16px;font-weight:bold;text-decoration:none;display:inline-block}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.card{overflow:hidden;background:#141414;border:1px solid #6e5223;border-radius:19px}.card img,.pic{width:100%;aspect-ratio:1;object-fit:cover}.pic{display:grid;place-items:center;font-size:62px;background:#222}.pad{padding:14px}.price{color:#e9bd50;font-weight:bold;font-size:21px}.muted{color:#d0d0d0;font-size:14px}.row{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap}.danger{background:#6d1c1c;color:#fff}
.voltar-bar{margin-bottom:18px}
.voltar-btn{display:inline-flex;align-items:center;gap:10px;background:#171717;color:#e7a92d;border:1px solid #a87920;border-radius:16px;padding:14px 20px;font-size:18px;font-weight:900;text-decoration:none}
.foto-editor{margin:16px 0 20px;padding:16px;border:1px solid #8a6422;border-radius:18px;background:#0d0d0d;text-align:center}
.foto-preview{width:100%;max-height:360px;object-fit:contain;border-radius:15px;background:#181818;display:none;margin-bottom:14px}
.foto-preview.show{display:block}
.foto-actions{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.foto-actions label,.foto-actions button{width:100%;margin:0;text-align:center;cursor:pointer}
.file-hidden{position:absolute;left:-9999px;width:1px;height:1px;opacity:0}
.prod-thumb{width:92px;height:92px;object-fit:cover;border-radius:14px;border:1px solid #8a6422;background:#222}
.prod-info{display:flex;align-items:center;gap:14px;min-width:0}
.prod-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.ver-fotos{width:100%;text-align:center;margin-top:10px}
.galeria-produto{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.galeria-produto .card img{width:100%;aspect-ratio:1;object-fit:cover;cursor:pointer}
.foto-grande{position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.96);display:none;align-items:center;justify-content:center;padding:18px}
.foto-grande.aberta{display:flex}
.foto-grande img{max-width:96vw;max-height:82vh;object-fit:contain;border-radius:14px}
.foto-fechar{position:absolute;top:18px;right:18px;font-size:24px}
.foto-nav{position:absolute;top:50%;transform:translateY(-50%);font-size:34px;padding:14px 18px}
.foto-ant{left:8px}.foto-prox{right:8px}
.foto-contador{position:absolute;bottom:20px;left:0;right:0;text-align:center;font-weight:bold}
@media(max-width:480px){.foto-actions{grid-template-columns:1fr}.prod-thumb{width:82px;height:82px}}
.menu-grid{display:flex;flex-direction:column;gap:14px}.menu-card{min-height:168px;padding:24px 22px;display:flex;align-items:center;gap:22px;color:#fff;text-decoration:none;background:linear-gradient(145deg,#171717,#090909);border:1px solid #a87920;border-radius:22px}.menu-icon{width:104px;flex:0 0 104px;text-align:center;color:#e7a92d;font-size:72px;line-height:1}.menu-copy{flex:1}.menu-title{font-size:34px;font-weight:900;margin-bottom:10px}.menu-desc{font-size:20px;color:#d0d0d0;line-height:1.25}.menu-arrow{font-size:58px;color:#e7a92d;font-weight:900}.menu-badge{background:#e7a92d;color:#090909;border-radius:50%;min-width:52px;height:52px;display:grid;place-items:center;font-size:22px;font-weight:900}.diferenciais{margin-top:32px;padding:30px 12px;border-top:2px solid #8a6422;text-align:center;color:#fff;font-size:31px;font-weight:900;line-height:1.55;letter-spacing:.2px}.diferenciais b{color:#e7a92d;font-size:36px}
#splash{position:fixed;inset:0;z-index:9999;background:#000;display:flex;align-items:center;justify-content:center;transition:opacity .55s}#splash.hide{opacity:0;pointer-events:none}.splash-inner{text-align:center;padding:28px}.splash-mark{font-size:110px;line-height:1;color:#e7a92d;text-shadow:0 0 28px rgba(231,169,45,.4)}.splash-g3{font-size:80px;font-weight:900;color:#e7a92d;line-height:.9;margin-top:-18px}.splash-name{font-size:39px;font-weight:900;color:#e7a92d;margin-top:30px}.splash-sub{font-size:15px;line-height:1.5;margin-top:12px;text-transform:uppercase}.loader{width:42px;height:42px;border:4px solid #3b2c10;border-top-color:#e7a92d;border-radius:50%;margin:55px auto 14px;animation:spin .85s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:480px){.logo{font-size:28px}.brandicon{font-size:34px}.sub{font-size:11px}main{padding:18px 12px 30px}.menu-card{min-height:148px;padding:20px 16px;gap:16px}.menu-icon{width:88px;flex-basis:88px;font-size:62px}.menu-title{font-size:29px}.menu-desc{font-size:17px}.menu-arrow{font-size:48px}.splash-mark{font-size:90px}.splash-g3{font-size:66px}.splash-name{font-size:33px}}
"""

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init():
    c=db()
    c.executescript("""CREATE TABLE IF NOT EXISTS produtos(id INTEGER PRIMARY KEY AUTOINCREMENT,nome TEXT,time_nome TEXT,categoria TEXT,tamanho TEXT,estado TEXT,preco REAL,estoque INTEGER,imagem TEXT,descricao TEXT);
CREATE TABLE IF NOT EXISTS config(chave TEXT PRIMARY KEY,valor TEXT);
CREATE TABLE IF NOT EXISTS fotos(id INTEGER PRIMARY KEY AUTOINCREMENT,produto_id INTEGER,arquivo TEXT,principal INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS vendas(id INTEGER PRIMARY KEY AUTOINCREMENT,data TEXT,total REAL,pagamento TEXT,itens TEXT);""")
    for sql in ["ALTER TABLE vendas ADD COLUMN tipo_entrega TEXT DEFAULT 'retirada'","ALTER TABLE vendas ADD COLUMN taxa_entrega REAL DEFAULT 0","ALTER TABLE vendas ADD COLUMN status TEXT DEFAULT 'ATIVO'","ALTER TABLE vendas ADD COLUMN estoque_devolvido INTEGER DEFAULT 0","ALTER TABLE produtos ADD COLUMN ativo INTEGER DEFAULT 1"]:
        try: c.execute(sql)
        except sqlite3.OperationalError: pass
    for k,v in {"nome":"BRECHÓ GETRES","slogan":"Blusas de times nacionais e internacionais","pix":"","whatsapp":"5521976723047","cnpj":"","endereco":"","mensagem":"Obrigado pela preferência!","impressora":"android","largura_papel":"58","impressora_nome":"KA-1445","impressora_ip":"","impressora_porta":"9100","cidade_pix":"RIO DE JANEIRO","taxa_entrega":"10.00","logo":""}.items():
        c.execute("INSERT OR IGNORE INTO config VALUES(?,?)",(k,v))
    c.commit(); c.close()

def migrar_nome_getres():
    c=db()
    r=c.execute("SELECT valor FROM config WHERE chave='nome'").fetchone()
    if r and str(r["valor"]).strip().upper()=="BRECHÓ G3":
        c.execute("UPDATE config SET valor='BRECHÓ GETRES' WHERE chave='nome'")
        c.commit()
    c.close()

def conf():
    c=db(); d={x["chave"]:x["valor"] for x in c.execute("SELECT * FROM config")}; c.close(); return d

def largura_impressao_mm(C=None):
    C=C or conf()
    try:
        mm=int(str(C.get("largura_papel","58")).strip())
    except Exception:
        mm=58
    return 76 if mm>=80 else 54

def botoes_impressao(texto_compartilhar="BRECHÓ GETRES"):
    """Opções de impressão: Android, compartilhamento, ESC/POS, USB/OTG, Wi-Fi e RawBT."""
    texto_json=json.dumps(texto_compartilhar,ensure_ascii=False)
    return f"""
    <div class='acoes-impressao'>
      <button type='button' onclick='window.print()'>🖨️ ANDROID / IMPRESSÃO PADRÃO</button>
      <button type='button' onclick='compartilharImpressao()'>📤 COMPARTILHAR PARA APP DE IMPRESSÃO</button>
      <button type='button' onclick='copiarEscPos()'>📋 COPIAR TEXTO ESC/POS</button>
      <details style='margin-top:8px;text-align:left'>
        <summary style='cursor:pointer;font-weight:bold'>Outras opções</summary>
        <p style='font-size:12px'>• RawBT: opcional, para quem já usa.</p>
        <p style='font-size:12px'>• USB/OTG: use um serviço Android compatível com sua impressora.</p>
        <p style='font-size:12px'>• Wi-Fi/IP: use o serviço/plugin do fabricante ou um serviço ESC/POS.</p>
        <p style='font-size:12px'>• Bluetooth direto: reservado para versão Android nativa/híbrida.</p>
      </details>
    </div>
    <script>
    const TEXTO_IMPRESSAO={texto_json};
    async function compartilharImpressao(){{
      if(navigator.share){{
        try{{
          await navigator.share({{title:'BRECHÓ GETRES',text:TEXTO_IMPRESSAO}});
          return;
        }}catch(e){{}}
      }}
      try{{
        await navigator.clipboard.writeText(TEXTO_IMPRESSAO);
        alert('Conteúdo copiado. Abra seu aplicativo de impressão e cole/envie.');
      }}catch(e){{
        alert('Use ANDROID / IMPRESSÃO PADRÃO para escolher um serviço de impressão instalado.');
      }}
    }}
    async function copiarEscPos(){{
      try{{
        await navigator.clipboard.writeText(TEXTO_IMPRESSAO);
        alert('Texto copiado para uso em app ESC/POS, RawBT ou plugin da impressora.');
      }}catch(e){{
        alert('Não foi possível copiar. Use o botão de impressão padrão.');
      }}
    }}
    </script>
    """

@app.route("/logo-getres")
def logo_getres():
    from flask import send_file, abort
    C=conf()
    salvo=str(C.get("logo","") or "").strip()
    if not salvo:
        abort(404)
    candidatos=[
        salvo,
        os.path.join("static", salvo),
        os.path.join("static", os.path.basename(salvo)),
    ]
    for caminho in candidatos:
        if os.path.isfile(caminho):
            return send_file(os.path.abspath(caminho), max_age=0)
    abort(404)

def page(title,body,nav=True):
    C=conf()
    path=request.path
    if path != "/":
        destino="/?menu=1"
        body=f"<div class=voltar-bar><a class=voltar-btn href='{destino}'>← VOLTAR</a></div>"+body
    logo_header=(f"<img src='/logo-getres?v={int(datetime.now().timestamp())}' alt='Logo BRECHÓ GETRES' style='width:42px;height:42px;object-fit:contain;display:block'>" if C.get("logo") else "<span class=brandicon>♧</span>")
    return render_template_string("""<!doctype html><html lang=pt-br><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover"><meta name=theme-color content="#000000"><link rel=manifest href="/manifest.json"><title>{{title}}</title><style>"""+CSS+"""</style></head><body><div class=app><header><div class=brandline>"""+logo_header+"""<div class=logo>{{nome}}</div></div><div class=sub>{{slogan}}</div></header><main>"""+body+"""</main></div><script>if("serviceWorker" in navigator){navigator.serviceWorker.register("/service-worker.js").catch(()=>{})}</script></body></html>""",title=title,nome=C["nome"],slogan=C["slogan"])

@app.route("/")
def home():
    C=conf(); whats=re.sub(r"\\D","",C.get("whatsapp","")) or "5521976723047"
    mensagem_whatsapp="""Olá! 👋 Tenho interesse nos produtos do Brechó Getres.

Gostaria de informações sobre:
1️⃣ Produtos disponíveis
2️⃣ Tamanhos e valores
3️⃣ Retirada no local
4️⃣ Envio e taxa de entrega
5️⃣ Fazer um pedido"""
    whatsapp_url=f"https://wa.me/{whats}?text={quote_plus(mensagem_whatsapp)}"
    splash_html="" if request.args.get("menu")=="1" else """<div id=splash><div class=splash-inner><div class=splash-mark>♧</div><div class=splash-g3>GETRES</div><div class=splash-name>BRECHÓ GETRES</div><div class=splash-sub>Blusas de times<br>nacionais e internacionais</div><button class="btn" style="margin-top:45px;font-size:21px;padding:18px 28px" onclick="entrarNaLoja()">ENTRAR NA LOJA</button><div class=muted style="margin-top:16px">Entre e confira nossas blusas.</div></div></div><script>function entrarNaLoja(){var x=document.getElementById('splash');if(x){x.classList.add('hide');setTimeout(function(){x.remove()},600)}}</script>"""
    body=f"""{splash_html}<div class=menu-grid>
    <a class=menu-card href='/destaques'><div class=menu-icon>🏠</div><div class=menu-copy><div class=menu-title>Início</div><div class=menu-desc>Página inicial e destaques</div></div><div class=menu-arrow>›</div></a>
    <a class=menu-card href='/produtos'><div class=menu-icon>👕</div><div class=menu-copy><div class=menu-title>Produtos</div><div class=menu-desc>Ver todos os produtos</div></div><div class=menu-arrow>›</div></a>
    <a class=menu-card href='/carrinho'><div class=menu-icon>🛒</div><div class=menu-copy><div class=menu-title>Carrinho</div><div class=menu-desc>Ver carrinho de compras</div></div><div id=homeBadge class=menu-badge>0</div><div class=menu-arrow>›</div></a>
    <a class=menu-card href='/pedidos'><div class=menu-icon>📋</div><div class=menu-copy><div class=menu-title>Pedidos</div><div class=menu-desc>Acompanhar seus pedidos</div></div><div class=menu-arrow>›</div></a>
    <a class=menu-card href='{whatsapp_url}' target='_blank'><div class=menu-icon>◉</div><div class=menu-copy><div class=menu-title>WhatsApp</div><div class=menu-desc>Fale com Brenno Luccas</div></div><div class=menu-arrow>›</div></a>
    <a class=menu-card href='/estatisticas'><div class=menu-icon>📊</div><div class=menu-copy><div class=menu-title>Estatísticas</div><div class=menu-desc>Vendas, faturamento e estoque</div></div><div class=menu-arrow>›</div></a>
    <a class=menu-card href='/config'><div class=menu-icon>⚙</div><div class=menu-copy><div class=menu-title>Configurações</div><div class=menu-desc>Configurações do app</div></div><div class=menu-arrow>›</div></a></div>
    <div class=diferenciais>
<b>✓</b> Qualidade garantida<br>
<b>✓</b> Preços justos<br>
<b>✓</b> Compra segura<br>
<b>✓</b> Retirada no local<br>
<b>✓</b> Envio com taxa
</div>
    <script>
try{{document.getElementById('homeBadge').textContent=JSON.parse(localStorage.g3cart||'[]').length}}catch(e){{}}

</script>"""
    return page("Brechó Getres",body)

@app.route("/destaques")
def destaques():
    c=db(); rows=c.execute("SELECT * FROM produtos WHERE COALESCE(ativo,1)=1 ORDER BY id DESC").fetchall(); c.close()
    cards=""
    for r in rows:
        foto=("<a href='/galeria/"+str(r["id"])+"'><img src='/static/produtos/"+r["imagem"]+"' alt='Ver fotos'></a>") if r["imagem"] else "<div class=pic>👕</div>"
        cards+=f"""<div class=card>{foto}<div class=pad><b>{r['nome']}</b><div class=muted>{r['tamanho']} • {r['estado']} • estoque {r['estoque']}</div><div class=price>R$ {r['preco']:.2f}</div><button onclick="let c=JSON.parse(localStorage.g3cart||'[]');c.push({r['id']});localStorage.g3cart=JSON.stringify(c);alert('Adicionado ao carrinho')">+ Carrinho</button><br><a class='btn ver-fotos' href='/galeria/{r['id']}'>📸 VER TODAS AS FOTOS</a></div></div>"""
    if not cards: cards="<div class=box>Nenhuma blusa cadastrada. Vá em Produtos → + Novo.</div>"
    return page("Início","<h2>Destaques</h2><div class=grid>"+cards+"</div><br><a class=btn href='/'>← MENU PRINCIPAL</a>")

@app.route("/produtos")
def produtos():
    c=db(); rows=c.execute("SELECT * FROM produtos ORDER BY id DESC").fetchall(); c.close()
    x="<div class=row><h2>Produtos</h2><a class=btn href='/novo'>＋ ADICIONAR</a></div>"
    if not rows:
        x+="<div class=box>Nenhuma blusa cadastrada.</div>"
    for r in rows:
        foto=f"<img class=prod-thumb src='/static/produtos/{r['imagem']}'>" if r["imagem"] else "<div class='prod-thumb pic' style='font-size:36px'>👕</div>"
        x+=f"""<div class=box>
        <div class=prod-info>{foto}<div><b style='font-size:21px'>{r['nome']}</b><div class=muted>{r['time_nome']} • {r['tamanho']}</div><div class=price>R$ {r['preco']:.2f}</div><div class=muted>Estoque: {r['estoque']}</div></div></div>
        <div class=prod-actions>
        <a class=btn href='/editar/{r['id']}'>✏️ DIGITAR / EDITAR</a>
        <a class=btn href='/fotos/{r['id']}'>📷 ADICIONAR FOTOS</a>
        <a class=btn href='/galeria/{r['id']}'>📸 VER TODAS AS FOTOS</a>
        <a class=btn href='/etiqueta/{r['id']}'>🏷️ ETIQUETA</a>
        {("<a class='btn danger' href='/desativar/"+str(r['id'])+"'>⛔ DESATIVAR</a>" if int(r["ativo"] if r["ativo"] is not None else 1)==1 else "<a class='btn' href='/reativar/"+str(r['id'])+"'>♻️ REATIVAR</a>")}
        <a class='btn danger' href='/excluir/{r['id']}' onclick="return confirm('Excluir definitivamente? Se já houve venda, será apenas desativado.')">🗑️ EXCLUIR</a>
        </div></div>"""
    x+="<a class=btn href='/'>← MENU PRINCIPAL</a>"
    return page("Produtos",x)

def form_prod(r=None):
    def v(k): return str(r[k] or "") if r else ""
    atual=v("imagem")
    atual_src=f"/static/produtos/{atual}" if atual else ""
    show=" show" if atual else ""
    return f"""<h2>{'✏️ Editar blusa' if r else '👕 Cadastrar blusa'}</h2>
<form method=post enctype=multipart/form-data class=box id=produtoForm>
<label>Nome da blusa</label><input name=nome value="{v('nome')}" required>
<label>Time</label><input name=time_nome value="{v('time_nome')}">
<label>Categoria</label><select name=categoria><option>{v('categoria')}</option><option>Nacional</option><option>Internacional</option><option>Seleção</option><option>Retrô</option></select>
<label>Tamanho</label><input name=tamanho value="{v('tamanho')}" placeholder="P, M, G, GG...">
<label>Estado</label><select name=estado><option>{v('estado')}</option><option>Nova</option><option>Seminova</option><option>Usada</option></select>
<label>Preço</label><input name=preco value="{v('preco')}" inputmode=decimal>
<label>Estoque</label><input name=estoque type=number value="{v('estoque') or 1}">
<label>Descrição</label><textarea name=descricao>{v('descricao')}</textarea>

<div class=foto-editor>
<h3>📷 Imagem da blusa</h3>
<img id=preview class="foto-preview{show}" src="{atual_src}">
<div id=semFoto class=muted style="{'display:none' if atual else ''};padding:24px">Nenhuma imagem selecionada.</div>
<input class=file-hidden id=imagemInput type=file name=imagem accept="image/*" multiple>
<input type=hidden name=remover_imagem id=removerImagem value=0>
<div class=foto-actions>
<label class=btn for=imagemInput>📷 ADICIONAR FOTOS (ATÉ 6)</label>
<button class=danger type=button onclick=excluirPreview()>🗑️ EXCLUIR FOTO</button>
</div>
<div id=multiPreview class=galeria-produto></div><p class=muted>Selecione até 6 fotos. A primeira será a principal.</p>
</div>

<button style="width:100%;font-size:18px">💾 SALVAR BLUSA</button>
</form>
<script>
const fi=document.getElementById('imagemInput'), pv=document.getElementById('preview'), sf=document.getElementById('semFoto'), rm=document.getElementById('removerImagem');
fi.addEventListener('change',()=>{{let fs=[...(fi.files||[])];if(fs.length>6){{alert('Escolha no máximo 6 fotos.');fi.value='';return}};let mp=document.getElementById('multiPreview');mp.innerHTML='';fs.forEach(f=>{{let im=document.createElement('img');im.src=URL.createObjectURL(f);im.style='width:100%;aspect-ratio:1;object-fit:cover;border-radius:12px';mp.appendChild(im)}});if(fs[0]){{pv.src=URL.createObjectURL(fs[0]);pv.classList.add('show');sf.style.display='none';rm.value='0'}}}});
function excluirPreview(){{fi.value='';pv.removeAttribute('src');pv.classList.remove('show');sf.style.display='block';rm.value='1'}}
</script>"""

@app.route("/novo",methods=["GET","POST"])
@app.route("/editar/<int:pid>",methods=["GET","POST"])
def produto_form(pid=None):
    c=db(); r=c.execute("SELECT * FROM produtos WHERE id=?",(pid,)).fetchone() if pid else None
    if request.method=="POST":
        img=r["imagem"] if r else ""
        old_img=img
        if request.form.get("remover_imagem")=="1":
            img=""
            if old_img:
                try: os.remove("static/produtos/"+old_img)
                except OSError: pass
        novos=[f for f in request.files.getlist("imagem")[:6] if f and f.filename]
        arquivos_novos=[]
        for f in novos:
            ext=os.path.splitext(f.filename)[1].lower() or ".jpg"
            arq=secrets.token_hex(8)+ext
            f.save("static/produtos/"+arq)
            arquivos_novos.append(arq)
        if arquivos_novos: img=arquivos_novos[0]
        vals=(request.form["nome"],request.form.get("time_nome",""),request.form.get("categoria",""),request.form.get("tamanho",""),request.form.get("estado",""),float(request.form.get("preco","0").replace(",",".")),int(request.form.get("estoque","0")),img,request.form.get("descricao",""))
        if pid:
            c.execute("UPDATE produtos SET nome=?,time_nome=?,categoria=?,tamanho=?,estado=?,preco=?,estoque=?,imagem=?,descricao=? WHERE id=?",vals+(pid,))
            produto_id=pid
        else:
            cur=c.execute("INSERT INTO produtos(nome,time_nome,categoria,tamanho,estado,preco,estoque,imagem,descricao) VALUES(?,?,?,?,?,?,?,?,?)",vals)
            produto_id=cur.lastrowid
        if arquivos_novos:
            c.execute("UPDATE fotos SET principal=0 WHERE produto_id=?",(produto_id,))
            existentes=c.execute("SELECT COUNT(*) n FROM fotos WHERE produto_id=?",(produto_id,)).fetchone()["n"]
            for i,arq in enumerate(arquivos_novos[:max(0,6-existentes)]):
                c.execute("INSERT INTO fotos(produto_id,arquivo,principal) VALUES(?,?,?)",(produto_id,arq,1 if i==0 else 0))
        c.commit();c.close();return redirect("/produtos")
    out=page("Produto",form_prod(r));c.close();return out

@app.route("/desativar/<int:pid>")
def desativar(pid):
    c=db(); c.execute("UPDATE produtos SET ativo=0 WHERE id=?",(pid,)); c.commit(); c.close(); return redirect("/produtos")

@app.route("/reativar/<int:pid>")
def reativar(pid):
    c=db(); c.execute("UPDATE produtos SET ativo=1 WHERE id=?",(pid,)); c.commit(); c.close(); return redirect("/produtos")

@app.route("/excluir/<int:pid>")
def excluir(pid):
    c=db(); vendas=c.execute("SELECT itens FROM vendas").fetchall(); usado=False
    for v in vendas:
        try:
            if any(int(x.get("id",0))==pid for x in json.loads(v["itens"] or "[]")): usado=True; break
        except Exception: pass
    if usado:
        c.execute("UPDATE produtos SET ativo=0 WHERE id=?",(pid,)); c.commit(); c.close(); return redirect("/produtos")
    p=c.execute("SELECT imagem FROM produtos WHERE id=?",(pid,)).fetchone()
    fotos_rows=c.execute("SELECT arquivo FROM fotos WHERE produto_id=?",(pid,)).fetchall()
    arquivos=set()
    if p and p["imagem"]: arquivos.add(p["imagem"])
    for f in fotos_rows:
        if f["arquivo"]: arquivos.add(f["arquivo"])
    for arq in arquivos:
        try: os.remove("static/produtos/"+arq)
        except OSError: pass
    c.execute("DELETE FROM fotos WHERE produto_id=?",(pid,)); c.execute("DELETE FROM produtos WHERE id=?",(pid,))
    c.commit(); c.close(); return redirect("/produtos")

@app.route("/galeria/<int:pid>")
def galeria(pid):
    c=db()
    p=c.execute("SELECT * FROM produtos WHERE id=?",(pid,)).fetchone()
    if not p:
        c.close()
        return "Produto não encontrado",404

    rows=c.execute("SELECT arquivo FROM fotos WHERE produto_id=? ORDER BY principal DESC,id DESC",(pid,)).fetchall()
    arquivos=[]
    if p["imagem"]:
        arquivos.append(p["imagem"])
    for r in rows:
        arq=r["arquivo"]
        if arq and arq not in arquivos:
            arquivos.append(arq)
    c.close()

    if not arquivos:
        return page("Fotos",f"<h2>📸 {p['nome']}</h2><div class=box>Nenhuma foto cadastrada para esta blusa.</div>")

    thumbs="".join(
        f"<div class=card><img src='/static/produtos/{arq}' onclick='abrirFoto({i})' alt='Foto {i+1}'></div>"
        for i,arq in enumerate(arquivos)
    )
    js_arquivos=json.dumps(["/static/produtos/"+a for a in arquivos],ensure_ascii=False)
    body=f"""<h2>📸 {p['nome']}</h2>
    <div class=box><b>{len(arquivos)} {'foto' if len(arquivos)==1 else 'fotos'}</b>
    <div class=muted>Toque em uma imagem para visualizar em tamanho grande.</div></div>
    <div class=galeria-produto>{thumbs}</div>
    <div id=fotoGrande class=foto-grande onclick="if(event.target===this)fecharFoto()">
      <button class="btn foto-fechar" onclick=fecharFoto()>✕</button>
      <button class="btn foto-nav foto-ant" onclick="mudarFoto(-1)">‹</button>
      <img id=imagemGrande alt="Foto ampliada">
      <button class="btn foto-nav foto-prox" onclick="mudarFoto(1)">›</button>
      <div id=fotoContador class=foto-contador></div>
    </div>
    <script>
    const fotosGaleria={js_arquivos};
    let fotoAtual=0;
    function mostrarFoto(){{
      document.getElementById('imagemGrande').src=fotosGaleria[fotoAtual];
      document.getElementById('fotoContador').textContent=(fotoAtual+1)+' / '+fotosGaleria.length;
    }}
    function abrirFoto(i){{fotoAtual=i;mostrarFoto();document.getElementById('fotoGrande').classList.add('aberta')}}
    function fecharFoto(){{document.getElementById('fotoGrande').classList.remove('aberta')}}
    function mudarFoto(n){{fotoAtual=(fotoAtual+n+fotosGaleria.length)%fotosGaleria.length;mostrarFoto()}}
    </script>"""
    return page("Galeria",body)


@app.route("/fotos/<int:pid>",methods=["GET","POST"])
def fotos(pid):
    c=db(); p=c.execute("SELECT * FROM produtos WHERE id=?",(pid,)).fetchone()
    if not p: c.close(); return "Produto não encontrado",404
    if request.method=="POST":
        fs=[f for f in request.files.getlist("fotos") if f and f.filename]
        existentes=c.execute("SELECT COUNT(*) n FROM fotos WHERE produto_id=?",(pid,)).fetchone()["n"]
        vagas=max(0,6-existentes)
        for f in fs[:vagas]:
            ext=os.path.splitext(f.filename)[1].lower() or ".jpg"
            arq=secrets.token_hex(10)+ext
            f.save("static/produtos/"+arq)
            tem=c.execute("SELECT 1 FROM fotos WHERE produto_id=?",(pid,)).fetchone()
            c.execute("INSERT INTO fotos(produto_id,arquivo,principal) VALUES(?,?,?)",(pid,arq,0 if tem else 1))
        c.commit(); c.close(); return redirect("/fotos/"+str(pid))
    rows=c.execute("SELECT * FROM fotos WHERE produto_id=? ORDER BY principal DESC,id DESC",(pid,)).fetchall(); c.close()
    cards=""
    for f in rows:
        cards+=f"""<div class=card><img src='/static/produtos/{f["arquivo"]}'><div class=pad>
        {'<b>⭐ Principal</b><br>' if f["principal"] else ''}
        <a class=btn href='/foto-principal/{pid}/{f["id"]}'>⭐ Principal</a>
        <a class='btn danger' href='/foto-excluir/{pid}/{f["id"]}'>🗑 Excluir</a></div></div>"""
    body=f"""<h2>📸 Fotos • G3-{pid:05d}</h2>
    <form method=post enctype=multipart/form-data class=box id=fotosForm>
    <label>➕ Adicionar fotos</label>

    <input class=file-hidden id=cameraFotos type=file name=fotos accept='image/*' capture='environment'>
    <input class=file-hidden id=galeriaFotos type=file name=fotos accept='image/*' multiple>

    <div class=foto-actions>
      <label class=btn for=cameraFotos>📷 TIRAR FOTO</label>
      <label class=btn for=galeriaFotos>🖼️ ESCOLHER DA GALERIA</label>
    </div>

    <div id=selecionadas class=muted style='padding:16px 4px;text-align:center'>
      Nenhuma nova foto selecionada.
    </div>

    <p class=muted>Você pode manter até 6 fotos por produto. Tire uma foto ou selecione várias imagens da galeria; as fotos já salvas não serão apagadas.</p>
    <button id=adicionarFotos type=submit style='width:100%' disabled>➕ ADICIONAR FOTOS</button>
    </form>

    <div class=grid>{cards or '<div class=box>Nenhuma foto adicional.</div>'}</div>

    <script>
    const cam=document.getElementById('cameraFotos');
    const gal=document.getElementById('galeriaFotos');
    const info=document.getElementById('selecionadas');
    const botao=document.getElementById('adicionarFotos');

    function atualizarSelecao(input) {{
      const n=input.files ? input.files.length : 0;
      if(n>0) {{
        info.textContent = n===1 ? '1 nova foto selecionada.' : n+' novas fotos selecionadas.';
        botao.disabled=false;
      }}
    }}
    cam.addEventListener('change',()=>atualizarSelecao(cam));
    gal.addEventListener('change',()=>atualizarSelecao(gal));
    </script>"""
    return page("Fotos",body)

@app.route("/foto-principal/<int:pid>/<int:fid>")
def foto_principal(pid,fid):
    c=db(); c.execute("UPDATE fotos SET principal=0 WHERE produto_id=?",(pid,))
    f=c.execute("SELECT arquivo FROM fotos WHERE id=? AND produto_id=?",(fid,pid)).fetchone()
    if f:
        c.execute("UPDATE fotos SET principal=1 WHERE id=?",(fid,))
        c.execute("UPDATE produtos SET imagem=? WHERE id=?",(f["arquivo"],pid))
    c.commit();c.close();return redirect("/fotos/"+str(pid))

@app.route("/foto-excluir/<int:pid>/<int:fid>")
def foto_excluir(pid,fid):
    c=db();f=c.execute("SELECT * FROM fotos WHERE id=? AND produto_id=?",(fid,pid)).fetchone()
    if f:
        try: os.remove("static/produtos/"+f["arquivo"])
        except: pass
        c.execute("DELETE FROM fotos WHERE id=?",(fid,))
        if f["principal"]:
            n=c.execute("SELECT * FROM fotos WHERE produto_id=? ORDER BY id DESC LIMIT 1",(pid,)).fetchone()
            if n:
                c.execute("UPDATE fotos SET principal=1 WHERE id=?",(n["id"],))
                c.execute("UPDATE produtos SET imagem=? WHERE id=?",(n["arquivo"],pid))
            else: c.execute("UPDATE produtos SET imagem='' WHERE id=?",(pid,))
    c.commit();c.close();return redirect("/fotos/"+str(pid))

@app.route("/etiqueta/<int:pid>")
def etiqueta(pid):
    c=db();p=c.execute("SELECT * FROM produtos WHERE id=?",(pid,)).fetchone();c.close()
    if not p:return "Produto não encontrado",404
    codigo=f"GETRES-{pid:05d}"
    qr=qr_data_uri(codigo); C=conf()
    logo=(f"<img src='/logo-getres?v={int(datetime.now().timestamp())}' alt='Logo' style='width:12mm;height:12mm;object-fit:contain;display:block;margin:0 auto 2mm'>" if C.get("logo") else "")
    return f"""<!doctype html><meta name=viewport content='width=device-width'>
    <style>body{{width:54mm;margin:auto;text-align:center;font:12px monospace;color:#000;background:#fff}}
    h1{{font-size:18px}}.preco{{font-size:23px;font-weight:bold}}img{{width:27mm;height:27mm}}
    button{{width:100%;padding:12px}}@media print{{button{{display:none}}}}</style>
    <div style="text-align:center">{logo}<h1 style="margin:0 0 2mm">BRECHÓ GETRES</h1></div><b>{codigo}</b><hr>
    <b>{p["nome"]}</b><p>{p["time_nome"]}<br>Tam: {p["tamanho"]} • {p["estado"]}</p>
    <div class=preco>R$ {p["preco"]:.2f}</div><img src='{qr}'><br><b>{codigo}</b>
    <button onclick=print()>🖨 IMPRIMIR ETIQUETA</button>"""


@app.route("/carrinho")
def carrinho():
    C=conf()
    try: taxa=float(str(C.get("taxa_entrega","0")).replace(",","."))
    except: taxa=0
    return page("Carrinho",f"""<h2>Carrinho</h2>
<div id=itens class=box>Carregando...</div>
<div class=box>
<label>Como deseja receber?</label>
<select id=entrega onchange=atualizarTotal()>
<option value="retirada">Retirada no local — grátis</option>
<option value="entrega">Entrega — taxa R$ {taxa:.2f}</option>
</select>
<div id=taxaInfo class=muted style="margin:8px 0 16px">Retirada no local: sem taxa.</div>
<label>Pagamento</label>
<select id=pag><option>PIX</option><option>Dinheiro</option><option>Débito</option><option>Crédito</option></select>
<button style="width:100%" onclick=fechar()>FINALIZAR VENDA</button>
</div>
<script>
let ids=JSON.parse(localStorage.g3cart||'[]'), taxaEntrega={taxa:.2f}, subtotal=0;
fetch('/api-cart?ids='+ids.join(',')).then(x=>x.json()).then(d=>{{window.d=d;subtotal=d.reduce((s,x)=>s+x.preco,0);render(d)}});
function render(d){{let taxa=entrega.value==='entrega'?taxaEntrega:0,total=subtotal+taxa;
itens.innerHTML=d.map(x=>`<p>${{x.nome}} <b style="float:right">R$ ${{x.preco.toFixed(2)}}</b></p>`).join('')+
`<hr><p>Subtotal <b style="float:right">R$ ${{subtotal.toFixed(2)}}</b></p>`+
(taxa?`<p>Taxa de entrega <b style="float:right">R$ ${{taxa.toFixed(2)}}</b></p>`:'')+
`<hr><b>Total: R$ ${{total.toFixed(2)}}</b>`}}
function atualizarTotal(){{taxaInfo.textContent=entrega.value==='entrega'?`Entrega: taxa de R$ ${{taxaEntrega.toFixed(2)}}`:'Retirada no local: sem taxa.';render(window.d||[])}}
function fechar(){{if(!ids.length || !window.d || !window.d.length || subtotal<=0){{alert('Carrinho vazio. Adicione pelo menos uma blusa antes de finalizar.');return}}fetch('/vender',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{ids,pagamento:pag.value,tipo_entrega:entrega.value,taxa_entrega:entrega.value==='entrega'?taxaEntrega:0}})}}).then(x=>x.json()).then(x=>{{if(x.ok){{localStorage.removeItem('g3cart');location='/venda/'+x.id}}else alert(x.erro)}})}}
</script>""")

@app.route("/api-cart")
def api_cart():
    ids=[int(x) for x in request.args.get("ids","").split(",") if x.isdigit()]
    if not ids:return []
    c=db(); out=[]
    for i in ids:
        r=c.execute("SELECT id,nome,tamanho,preco,estoque FROM produtos WHERE id=?",(i,)).fetchone()
        if r:out.append(dict(r))
    c.close();return out

@app.route("/vender",methods=["POST"])
def vender():
    d=request.get_json() or {}
    ids=d.get("ids",[])
    if not ids:
        return {"ok":False,"erro":"Carrinho vazio. Adicione pelo menos uma blusa antes de finalizar."},400
    c=db();it=[];total=0
    for i in ids:
        r=c.execute("SELECT * FROM produtos WHERE id=?",(i,)).fetchone()
        if not r or r["estoque"]<1:c.close();return {"ok":False,"erro":"Produto sem estoque"}
        it.append({"id":r["id"],"nome":r["nome"],"tamanho":r["tamanho"],"preco":r["preco"]});total+=r["preco"]
    if not it or total<=0:
        c.rollback();c.close()
        return {"ok":False,"erro":"Não é possível finalizar uma venda com total R$ 0,00."},400
    tipo_entrega=d.get("tipo_entrega","retirada")
    taxa=0
    if tipo_entrega=="entrega":
        try: taxa=float(str(conf().get("taxa_entrega","0")).replace(",","."))
        except: taxa=0
    total+=taxa
    cur=c.execute("INSERT INTO vendas(data,total,pagamento,itens,tipo_entrega,taxa_entrega,status,estoque_devolvido) VALUES(?,?,?,?,?,?,?,?)",(datetime.now().isoformat(timespec="minutes"),total,d.get("pagamento","PIX"),json.dumps(it,ensure_ascii=False),tipo_entrega,taxa,"AGUARDANDO_PAGAMENTO",0))
    vid=cur.lastrowid;c.commit();c.close();return {"ok":True,"id":vid}

@app.route("/venda/<int:vid>")
def venda(vid):
    c=db();v=c.execute("SELECT * FROM vendas WHERE id=?",(vid,)).fetchone();c.close()
    if not v:return "Venda não encontrada",404
    C=conf()
    if v["pagamento"]=="PIX":
        chave=C["pix"].strip()
        payload=pix_payload(chave,v["total"],C["nome"],C.get("cidade_pix","RIO DE JANEIRO"),f"GETRES{vid}")
        qr=qr_data_uri(payload) if payload else ""
        if payload:
            pix=f"""<div class=box style='text-align:center'><h3>💠 PIX QR CODE</h3>
            <p>Valor: <b>R$ {v['total']:.2f}</b></p>
            <button onclick="document.getElementById('pixqr').style.display='block'">GERAR QR CODE PIX</button>
            <div id=pixqr style='display:none;margin-top:14px'>
            <img style='width:230px;max-width:100%;background:white;padding:8px' src='{qr}'>
            <p class=muted>PIX Copia e Cola</p>
            <textarea id=copiapix readonly style='height:120px'>{payload}</textarea>
            <button onclick="navigator.clipboard.writeText(document.getElementById('copiapix').value).then(()=>alert('PIX copiado'))">COPIAR PIX</button>
            </div></div>"""
        else:
            pix="<div class=box><b>PIX não configurado.</b><p>Cadastre sua chave PIX em Configurações.</p><a class=btn href='/config'>CONFIGURAR PIX</a></div>"
    else: pix=""
    status=v["status"] or "AGUARDANDO_PAGAMENTO"
    if status=="CANCELADO":
        pix=""
        botoes="<div class='box' style='text-align:center;border-color:#8b2727'><h3>❌ PEDIDO CANCELADO</h3><p>Este pedido permanece no histórico.</p></div>"
    elif status=="PAGO":
        pix=""
        botoes=f"""<div class='box' style='text-align:center;border-color:#2f8f46'><h3>✅ PAGAMENTO CONFIRMADO</h3><p>Pedido pago e registrado no histórico.</p></div>
<a class=btn style='width:100%;text-align:center;margin-bottom:12px' href='/comprovante/{vid}'>🖨️ COMPROVANTE 58 MM</a>"""
    else:
        botoes=f"""<form method=post action='/confirmar-pagamento/{vid}' onsubmit="return confirm('Confirmar o pagamento deste pedido?')">
<button style='width:100%;font-size:18px;margin-bottom:12px' type=submit>✅ CONFIRMAR PAGAMENTO</button></form>
<a class=btn style='width:100%;text-align:center;margin-bottom:12px' href='/comprovante/{vid}'>🖨️ COMPROVANTE 58 MM</a>
<form method=post action='/cancelar-pedido/{vid}' onsubmit="return confirm('Tem certeza que deseja cancelar este pedido?')">
<button class=danger style='width:100%;font-size:17px' type=submit>❌ CANCELAR PEDIDO</button></form>"""
    entrega_info=f"<p>Taxa de entrega: R$ {v['taxa_entrega']:.2f}</p>" if v["tipo_entrega"]=="entrega" else ""
    return page("Venda",f"<h2>Venda #{vid}</h2><div class=box><div class=price>R$ {v['total']:.2f}</div><p><b>Status: {"⏳ AGUARDANDO PAGAMENTO" if status in ("ATIVO","AGUARDANDO_PAGAMENTO") else status}</b></p><p>Pagamento: {v['pagamento']}</p><p>Recebimento: {'Entrega' if v['tipo_entrega']=='entrega' else 'Retirada no local'}</p>{entrega_info}</div>{pix}{botoes}")

@app.route("/confirmar-pagamento/<int:vid>",methods=["POST"])
def confirmar_pagamento(vid):
    c=db()
    v=c.execute("SELECT * FROM vendas WHERE id=?",(vid,)).fetchone()
    if not v:
        c.close()
        return "Venda não encontrada",404
    if (v["status"] or "AGUARDANDO_PAGAMENTO") in ("ATIVO","AGUARDANDO_PAGAMENTO"):
        try: itens=json.loads(v["itens"] or "[]")
        except Exception: itens=[]
        # Confere todo o estoque antes de alterar qualquer produto.
        for item in itens:
            pid=item.get("id")
            if not pid: continue
            qtd=sum(1 for x in itens if x.get("id")==pid)
            r=c.execute("SELECT estoque,nome FROM produtos WHERE id=?",(pid,)).fetchone()
            if not r or r["estoque"] < qtd:
                disponivel=int(r["estoque"]) if r else 0
                c.close(); nome=r["nome"] if r else "Produto"
                return page("Estoque insuficiente",f"<h2>⚠️ Estoque insuficiente</h2><div class=box><b>{nome}</b><p>Disponível: <b>{disponivel}</b></p><p>O pagamento não foi confirmado.</p><a class=btn href='/carrinho'>← VOLTAR AO CARRINHO</a></div>"),400
        # O estoque só é baixado quando o pagamento é confirmado.
        processados=set()
        for item in itens:
            pid=item.get("id")
            if not pid or pid in processados: continue
            qtd=sum(1 for x in itens if x.get("id")==pid)
            c.execute("UPDATE produtos SET estoque=estoque-? WHERE id=?",(qtd,pid))
            processados.add(pid)
        c.execute("UPDATE vendas SET status='PAGO', estoque_devolvido=0 WHERE id=?",(vid,))
        c.commit()
    c.close()
    return redirect("/venda/"+str(vid))


@app.route("/cancelar-pedido/<int:vid>",methods=["POST"])
def cancelar_pedido(vid):
    c=db(); v=c.execute("SELECT * FROM vendas WHERE id=?",(vid,)).fetchone()
    if not v:
        c.close(); return "Venda não encontrada",404
    status_atual=v["status"] or "AGUARDANDO_PAGAMENTO"
    if status_atual!="CANCELADO":
        # Pedido ATIVO ainda não baixou estoque, então cancelar não altera o estoque.
        # Se futuramente houver cancelamento de pedido PAGO, devolve o estoque uma única vez.
        if status_atual=="PAGO" and not v["estoque_devolvido"]:
            try: itens=json.loads(v["itens"] or "[]")
            except Exception: itens=[]
            for item in itens:
                pid=item.get("id")
                if pid: c.execute("UPDATE produtos SET estoque=estoque+1 WHERE id=?",(pid,))
            c.execute("UPDATE vendas SET estoque_devolvido=1 WHERE id=?",(vid,))
        c.execute("UPDATE vendas SET status='CANCELADO' WHERE id=?",(vid,))
        c.commit()
    c.close()
    return redirect("/venda/"+str(vid))

@app.route("/comprovante/<int:vid>")
def comprovante(vid):
    c=db();v=c.execute("SELECT * FROM vendas WHERE id=?",(vid,)).fetchone();c.close();C=conf()
    if not v:return "Venda não encontrada",404
    itens=json.loads(v["itens"] or "[]")
    linhas="".join(f"<p style='overflow-wrap:anywhere;margin:5px 0'>{x['nome']} {x.get('tamanho','')}<br>R$ {float(x['preco']):.2f}</p>" for x in itens)
    largura=largura_impressao_mm(C)
    logo=(f"<img src='/logo-getres?v={int(datetime.now().timestamp())}' alt='Logo' style='width:12mm;height:12mm;object-fit:contain;display:block'>" if C.get("logo") else "<span style='font-size:24px;font-weight:bold'>♧</span>")
    itens_txt="\\n".join(f"{x['nome']} {x.get('tamanho','')} - R$ {float(x['preco']):.2f}" for x in itens)
    entrega_txt=(f"ENTREGA - Taxa R$ {float(v['taxa_entrega'] or 0):.2f}" if v["tipo_entrega"]=="entrega" else "RETIRADA NO LOCAL")
    texto=(f"{C.get('nome','BRECHÓ GETRES')}\\n{C.get('cnpj','')}\\n{C.get('endereco','')}\\n"
           f"COMPROVANTE #{vid}\\n{itens_txt}\\n{entrega_txt}\\nTOTAL R$ {float(v['total']):.2f}\\n"
           f"{v['pagamento']}\\n{C.get('mensagem','')}")
    botoes=botoes_impressao(texto)
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name=viewport content='width=device-width'>
    <style>
    @page{{size:{largura}mm auto;margin:0}}
    *{{box-sizing:border-box}}
    body{{width:{largura}mm;max-width:{largura}mm;margin:0 auto;padding:2mm;font:12px monospace;color:#000;background:#fff;text-align:center}}
    hr{{border:0;border-top:1px dashed #000}}button{{width:100%;padding:12px;margin:4px 0;font-weight:bold}}
    .marca{{display:flex;align-items:center;justify-content:center;gap:5px}}.acoes-impressao{{margin-top:8px}}
    @media print{{.acoes-impressao{{display:none!important}}body{{padding:1mm}}}}
    </style></head><body>
    <div class=marca>{logo}<h2 style="margin:0;font-size:15px;line-height:1;white-space:nowrap">{C['nome']}</h2></div>
    <p>{C['cnpj']}<br>{C['endereco']}</p><hr><b>COMPROVANTE #{vid}</b>{linhas}<hr>
    <p>{entrega_txt}</p><h3>TOTAL R$ {float(v['total']):.2f}</h3>
    <p>{v['pagamento']}<br>{C['mensagem']}</p>{botoes}</body></html>"""

@app.route("/pedidos")
def pedidos():
    c=db();rows=c.execute("SELECT * FROM vendas ORDER BY id DESC").fetchall();c.close()
    x="<h2>Pedidos</h2>"+''.join(f"<a class='box row' style='display:flex;color:white;text-decoration:none' href='/venda/{r['id']}'><div><b>Venda #{r['id']}</b><div class=muted>{'❌ CANCELADO' if (r['status'] or 'AGUARDANDO_PAGAMENTO')=='CANCELADO' else ('✅ PAGO' if (r['status'] or 'AGUARDANDO_PAGAMENTO')=='PAGO' else '⏳ AGUARDANDO PAGAMENTO')}</div></div><span>R$ {r['total']:.2f}</span></a>" for r in rows)
    return page("Pedidos",x)

@app.route("/menu")
def menu():
    return page("Menu","""<h2>Menu</h2><div class=box><a class=btn href=/config>⚙️ Configurações</a><br><br><a class=btn href=/teste>🖨️ Testar impressora</a></div>""")

@app.route("/estatisticas")
def estatisticas():
    c=db()
    pagos=c.execute("SELECT * FROM vendas WHERE status='PAGO' ORDER BY id DESC").fetchall()
    ativos=c.execute("SELECT COUNT(*) n FROM vendas WHERE COALESCE(status,'AGUARDANDO_PAGAMENTO') IN ('ATIVO','AGUARDANDO_PAGAMENTO')").fetchone()["n"]
    cancelados=c.execute("SELECT COUNT(*) n FROM vendas WHERE status='CANCELADO'").fetchone()["n"]
    agora=datetime.now(); hoje=agora.strftime("%Y-%m-%d"); mes=agora.strftime("%Y-%m")
    fat=sum(float(v["total"] or 0) for v in pagos)
    fat_hoje=sum(float(v["total"] or 0) for v in pagos if str(v["data"] or "").startswith(hoje))
    fat_mes=sum(float(v["total"] or 0) for v in pagos if str(v["data"] or "").startswith(mes))
    ticket=fat/len(pagos) if pagos else 0
    formas={}; vendidos={}; unidades=0
    for v in pagos:
        pg=(v["pagamento"] or "Não informado").strip()
        formas[pg]=formas.get(pg,0)+float(v["total"] or 0)
        try: itens=json.loads(v["itens"] or "[]")
        except Exception: itens=[]
        for item in itens:
            nome=item.get("nome") or "Produto"
            vendidos[nome]=vendidos.get(nome,0)+1; unidades+=1
    top=sorted(vendidos.items(),key=lambda x:(-x[1],x[0].lower()))[:5]
    produtos=c.execute("SELECT nome,estoque FROM produtos ORDER BY estoque ASC,nome").fetchall()
    estoque_total=sum(int(p["estoque"] or 0) for p in produtos)
    sem=[p["nome"] for p in produtos if int(p["estoque"] or 0)<=0]
    c.close()
    moeda=lambda v:("R$ %.2f"%v).replace(".",",")
    formas_html="".join(f"<div class='box row' style='display:flex'><b>{k}</b><span>{moeda(v)}</span></div>" for k,v in sorted(formas.items())) or "<div class=box>Nenhum pagamento confirmado ainda.</div>"
    top_html="".join(f"<div class='box row' style='display:flex'><b>{n}</b><span>{q} un.</span></div>" for n,q in top) or "<div class=box>Nenhum produto vendido ainda.</div>"
    sem_html="".join(f"<div class=box>⚠️ {n}</div>" for n in sem) or "<div class=box>✅ Nenhum produto sem estoque.</div>"
    body=f"""<h2>📊 Estatísticas</h2>
    <div class=grid>
    <div class=box><div class=muted>💰 Faturamento total</div><div class=price>{moeda(fat)}</div><small>Somente pedidos PAGOS</small></div>
    <div class=box><div class=muted>📅 Vendas de hoje</div><div class=price>{moeda(fat_hoje)}</div></div>
    <div class=box><div class=muted>🗓️ Vendas do mês</div><div class=price>{moeda(fat_mes)}</div></div>
    <div class=box><div class=muted>🎫 Ticket médio</div><div class=price>{moeda(ticket)}</div></div>
    <div class=box><b>✅ Pedidos pagos</b><div class=price>{len(pagos)}</div></div>
    <div class=box><b>⏳ Aguardando pagamento</b><div class=price>{ativos}</div></div>
    <div class=box><b>❌ Pedidos cancelados</b><div class=price>{cancelados}</div></div>
    <div class=box><b>👕 Unidades vendidas</b><div class=price>{unidades}</div></div>
    <div class=box><b>📦 Estoque atual</b><div class=price>{estoque_total}</div></div></div>
    <h3>💳 Faturamento por pagamento</h3>{formas_html}
    <h3>🏆 Produtos mais vendidos</h3>{top_html}
    <h3>⚠️ Produtos sem estoque</h3>{sem_html}"""
    return page("Estatísticas",body)

@app.route("/config",methods=["GET","POST"])
def config():
    if request.method=="POST":
        c=db()
        for k in ["nome","slogan","pix","cidade_pix","whatsapp","cnpj","endereco","mensagem",
                  "impressora","largura_papel","impressora_nome","impressora_ip","impressora_porta",
                  "taxa_entrega"]:
            c.execute("INSERT OR REPLACE INTO config VALUES(?,?)",(k,request.form.get(k,"")))
        logo=request.files.get("logo")
        if logo and logo.filename:
            ext=os.path.splitext(logo.filename)[1].lower() or ".png"; arq="logo_getres"+ext
            logo.save("static/"+arq); c.execute("INSERT OR REPLACE INTO config VALUES('logo',?)",(arq,))
        c.commit();c.close();return redirect("/config")

    C=conf()
    labels={"nome":"Nome da loja","slogan":"Slogan","pix":"Chave PIX","cidade_pix":"Cidade do PIX",
            "whatsapp":"WhatsApp","cnpj":"CNPJ/CPF","endereco":"Endereço",
            "mensagem":"Mensagem do comprovante","taxa_entrega":"Taxa de entrega (R$)"}
    fs="".join(f"<label>{labels[k]}</label><input name={k} value='{C.get(k,'')}'>" for k in labels)

    modo=str(C.get("impressora","android") or "android")
    larg=str(C.get("largura_papel","58"))
    def selected(v): return "selected" if modo==v else ""
    sel58="selected" if larg!="80" else ""
    sel80="selected" if larg=="80" else ""

    printer=f"""
    <h3>🖨️ Impressora térmica</h3>
    <label>Método de impressão</label>
    <select name='impressora'>
      <option value='android' {selected('android')}>Android padrão — recomendado e gratuito</option>
      <option value='compartilhar' {selected('compartilhar')}>Compartilhar para aplicativo de impressão</option>
      <option value='escpos' {selected('escpos')}>ESC/POS genérico</option>
      <option value='usb' {selected('usb')}>USB / OTG via serviço Android</option>
      <option value='wifi' {selected('wifi')}>Wi‑Fi / IP via serviço/plugin Android</option>
      <option value='rawbt' {selected('rawbt')}>RawBT — opcional</option>
      <option value='bluetooth_nativo' {selected('bluetooth_nativo')}>Bluetooth direto — futura versão Android nativa</option>
    </select>

    <label>Largura do papel</label>
    <select name='largura_papel'>
      <option value='58' {sel58}>58 mm — portátil mais comum</option>
      <option value='80' {sel80}>80 mm — recibo largo</option>
    </select>

    <label>Nome/modelo da impressora</label>
    <input name='impressora_nome' value='{C.get("impressora_nome","")}' placeholder='Ex.: KA-1445, XPrinter, Elgin, Epson...'>

    <label>IP da impressora (opcional)</label>
    <input name='impressora_ip' value='{C.get("impressora_ip","")}' placeholder='Ex.: 192.168.1.50'>

    <label>Porta ESC/POS (opcional)</label>
    <input name='impressora_porta' value='{C.get("impressora_porta","9100")}' inputmode='numeric'>

    <div class=box style='margin-top:12px'>
      <b>Compatibilidade</b>
      <p class=muted>Android padrão, compartilhamento, ESC/POS, USB/OTG, Wi‑Fi/IP e RawBT opcional.</p>
      <p class=muted>Bluetooth direto pelo navegador não é universal; use RawBT/serviço Android ou uma futura versão nativa.</p>
    </div>

    <a class=btn href='/teste'>🧾 TESTAR IMPRESSORA</a>
    """
    return page("Configurações",
        f"<h2>Configurações</h2><form method=post enctype='multipart/form-data' class=box>{fs}{printer}"
        f"<label>Logo do BRECHÓ GETRES</label><input type=file name=logo accept='image/*'>"
        f"<p class=muted>Usada no comprovante e etiqueta.</p>"
        f"<button style='width:100%'>SALVAR</button></form>")

@app.route("/teste")
def teste():
    C=conf(); largura=largura_impressao_mm(C)
    texto=(f"BRECHÓ GETRES\\nTESTE DE IMPRESSÃO\\n"
           f"Método: {C.get('impressora','android')}\\n"
           f"Papel: {C.get('largura_papel','58')} mm\\n"
           f"Modelo: {C.get('impressora_nome','')}\\n"
           f"ABCDEFGHIJKLMNOPQRSTUVWXYZ\\n0123456789\\n"
           f"Se este texto saiu completo, a largura está correta.")
    botoes=botoes_impressao(texto)
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name=viewport content='width=device-width'>
    <style>
    @page{{size:{largura}mm auto;margin:0}}
    *{{box-sizing:border-box}}
    body{{width:{largura}mm;max-width:{largura}mm;margin:0 auto;padding:2mm;text-align:center;font:12px monospace;color:#000;background:#fff}}
    button{{width:100%;padding:12px;margin:4px 0;font-weight:bold}}.acoes-impressao{{margin-top:8px}}
    @media print{{.acoes-impressao{{display:none!important}}body{{padding:1mm}}}}
    </style></head><body>
    <h2>BRECHÓ GETRES</h2>
    <p>TESTE TÉRMICO {C.get('largura_papel','58')} mm</p>
    <p>Método: {C.get('impressora','android')}</p>
    <p>{C.get('impressora_nome','')}</p>
    <p>------------------------------</p>
    <p>ABCDEFGHIJKLMNOPQRSTUVWXYZ<br>0123456789</p>
    <p>Se tudo sair completo,<br>a largura está correta.</p>
    {botoes}</body></html>"""

@app.route("/manifest.json")
def manifest():
    return {"name":"Brechó Getres","short_name":"GETRES","start_url":"/","display":"standalone",
            "background_color":"#080808","theme_color":"#080808"}

@app.route("/service-worker.js")
def service_worker():
    from flask import Response
    js="""const C='brecho-getres-6-fotos-logo-v4';
self.addEventListener('install',e=>e.waitUntil(caches.open(C).then(c=>c.addAll(['/','/produtos','/carrinho','/pedidos','/estatisticas','/menu','/config']))));
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;e.respondWith(fetch(e.request).then(r=>{let x=r.clone();caches.open(C).then(c=>c.put(e.request,x));return r}).catch(()=>caches.match(e.request)))});
"""
    resp=Response(js,mimetype="application/javascript")
    resp.headers["Cache-Control"]="no-store, no-cache, must-revalidate, max-age=0"
    return resp

init()
migrar_nome_getres()
if __name__=="__main__":
    print("BRECHÓ GETRES: http://127.0.0.1:5000")
    app.run(host="0.0.0.0",port=5000,debug=False)

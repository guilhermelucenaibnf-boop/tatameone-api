import cors from 'cors';

import express, { Request, Response, NextFunction } from 'express';
import { initDb, database } from './db.js';
import { randomUUID } from 'node:crypto';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';

const app = express();
app.use(cors({
  origin: '*',
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

app.use(express.json());
app.use(express.static('public'));

const JWT_SECRET = 'tatameone_chave_secreta_super_segura';

initDb();

interface AuthRequest extends Request {
  usuarioId?: string;
}

function autenticarToken(req: AuthRequest, res: Response, next: NextFunction) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token) {
    return res.status(401).json({ error: 'Acesso negado. Token não fornecido.' });
  }

  try {
    const payload = jwt.verify(token, JWT_SECRET) as { id: string };
    req.usuarioId = payload.id;
    next();
  } catch (err) {
    return res.status(403).json({ error: 'Token inválido ou expirado.' });
  }
}

// --- ROTAS AUTENTICAÇÃO E USUÁRIOS ---

app.get('/health', (req, res) => {
  res.json({ status: 'ok', app: 'TatameOne API' });
});

app.post('/usuarios', async (req, res) => {
  const { nome, email, senha, role, faixa, graus } = req.body;

  if (!nome || !email || !senha) {
    return res.status(400).json({ error: 'Nome, email e senha são obrigatórios.' });
  }

  const id = randomUUID();

  try {
    const senhaHash = await bcrypt.hash(senha, 10);
    const stmt = database.prepare(`
      INSERT INTO usuarios (id, nome, email, senhaHash, role, faixa, graus)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `);

    stmt.run(id, nome, email, senhaHash, role || 'ALUNO', faixa || 'BRANCA', graus || 0);
    res.status(201).json({ id, nome, email, faixa });
  } catch (error: any) {
    res.status(400).json({ error: error.message });
  }
});

app.post('/login', async (req, res) => {
  const { email, senha } = req.body;

  if (!email || !senha) {
    return res.status(400).json({ error: 'Email e senha são obrigatórios.' });
  }

  try {
    const stmt = database.prepare('SELECT * FROM usuarios WHERE email = ?');
    const usuario = stmt.get(email) as any;

    if (!usuario || !(await bcrypt.compare(senha, usuario.senhaHash))) {
      return res.status(400).json({ error: 'Credenciais inválidas.' });
    }

    const token = jwt.sign({ id: usuario.id, email: usuario.email }, JWT_SECRET, { expiresIn: '7d' });

    res.json({
      token,
      usuario: { id: usuario.id, nome: usuario.nome, email: usuario.email, faixa: usuario.faixa, graus: usuario.graus }
    });
  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
});

// --- ROTAS DO DIÁRIO & DASHBOARD ---

app.post('/diario', autenticarToken, (req: AuthRequest, res) => {
  const { posicoesAprendidas, qtdRolas, nivelDesgaste, doresRelatadas, anotacoes } = req.body;
  const usuarioId = req.usuarioId;

  if (!posicoesAprendidas || nivelDesgaste === undefined) {
    return res.status(400).json({ error: 'posicoesAprendidas e nivelDesgaste são obrigatórios.' });
  }

  const id = randomUUID();

  try {
    const stmt = database.prepare(`
      INSERT INTO diario_treino (id, usuarioId, posicoesAprendidas, qtdRolas, nivelDesgaste, doresRelatadas, anotacoes)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `);

    stmt.run(id, usuarioId, posicoesAprendidas, qtdRolas || 0, nivelDesgaste, doresRelatadas || '', anotacoes || '');
    res.status(201).json({ id, usuarioId, posicoesAprendidas });
  } catch (error: any) {
    res.status(400).json({ error: error.message });
  }
});

app.get('/diario', autenticarToken, (req: AuthRequest, res) => {
  const usuarioId = req.usuarioId;
  const { busca } = req.query;

  try {
    let query = 'SELECT * FROM diario_treino WHERE usuarioId = ?';
    const params: any[] = [usuarioId];

    if (busca) {
      query += ' AND posicoesAprendidas LIKE ?';
      params.push(`%${busca}%`);
    }

    query += ' ORDER BY dataTreino DESC';

    const stmt = database.prepare(query);
    const treinos = stmt.all(...params);
    res.json(treinos);
  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/dashboard', autenticarToken, (req: AuthRequest, res) => {
  const usuarioId = req.usuarioId;

  try {
    const statsStmt = database.prepare(`
      SELECT 
        COUNT(*) as totalTreinos,
        COALESCE(SUM(qtdRolas), 0) as totalRolas,
        COALESCE(AVG(nivelDesgaste), 0) as mediaDesgaste
      FROM diario_treino 
      WHERE usuarioId = ?
    `);
    const stats = statsStmt.get(usuarioId) as any;

    const userStmt = database.prepare('SELECT faixa, graus FROM usuarios WHERE id = ?');
    const user = userStmt.get(usuarioId) as any;

    const treinosPorGrau = 50;
    const treinosAtuais = stats.totalTreinos % treinosPorGrau;
    const progressoGrau = Math.min(Math.round((treinosAtuais / treinosPorGrau) * 100), 100);

    res.json({
      totalTreinos: stats.totalTreinos,
      totalRolas: stats.totalRolas,
      mediaDesgaste: Number(stats.mediaDesgaste).toFixed(1),
      faixa: user?.faixa || 'BRANCA',
      graus: user?.graus || 0,
      progressoGrau: `${progressoGrau}%`
    });
  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/diario/exportar/csv', autenticarToken, (req: AuthRequest, res) => {
  const usuarioId = req.usuarioId;

  try {
    const stmt = database.prepare('SELECT dataTreino, posicoesAprendidas, qtdRolas, nivelDesgaste, anotacoes FROM diario_treino WHERE usuarioId = ? ORDER BY dataTreino DESC');
    const treinos = stmt.all(usuarioId) as any[];

    let csv = 'Data,Posicoes,Qtd Rolas,Desgaste (1-5),Anotacoes\n';
    treinos.forEach(t => {
      csv += `"${t.dataTreino}","${t.posicoesAprendidas.replace(/"/g, '""')}",${t.qtdRolas},${t.nivelDesgaste},"${(t.anotacoes || '').replace(/"/g, '""')}"\n`;
    });

    res.setHeader('Content-Type', 'text/csv');
    res.setHeader('Content-Disposition', 'attachment; filename=diario_treinos_tatameone.csv');
    res.status(200).send(csv);
  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
});

app.delete('/diario/:id', autenticarToken, (req: AuthRequest, res) => {
  const { id } = req.params;
  const usuarioId = req.usuarioId;

  try {
    const stmt = database.prepare('DELETE FROM diario_treino WHERE id = ? AND usuarioId = ?');
    const result = stmt.run(id, usuarioId);

    if (result.changes === 0) {
      return res.status(404).json({ error: 'Treino não encontrado.' });
    }

    res.json({ message: 'Treino excluído com sucesso!' });
  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
});

const PORT = 3000;
app.listen(PORT, () => {
  console.log(`🥋 TatameOne API Master rodando em http://localhost:${PORT}`);
});


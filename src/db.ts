import { DatabaseSync } from 'node:sqlite';

export const database = new DatabaseSync('tatameone.db');

export function initDb() {
  database.exec(`
    CREATE TABLE IF NOT EXISTS usuarios (
      id TEXT PRIMARY KEY,
      nome TEXT NOT NULL,
      email TEXT UNIQUE NOT NULL,
      senhaHash TEXT NOT NULL,
      role TEXT DEFAULT 'ALUNO',
      faixa TEXT DEFAULT 'BRANCA',
      graus INTEGER DEFAULT 0,
      modoInterface TEXT DEFAULT 'ADULTO'
    );

    CREATE TABLE IF NOT EXISTS diario_treino (
      id TEXT PRIMARY KEY,
      usuarioId TEXT NOT NULL,
      dataTreino DATETIME DEFAULT CURRENT_TIMESTAMP,
      posicoesAprendidas TEXT NOT NULL,
      qtdRolas INTEGER DEFAULT 0,
      nivelDesgaste INTEGER NOT NULL,
      doresRelatadas TEXT,
      anotacoes TEXT,
      FOREIGN KEY(usuarioId) REFERENCES usuarios(id)
    );
  `);
}


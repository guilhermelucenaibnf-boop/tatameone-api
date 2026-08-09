import { initDb, database } from './db';

initDb();

// Testa inserindo uma verificação simples
const stmt = database.prepare("SELECT name FROM sqlite_master WHERE type='table';");
const tables = stmt.all();

console.log('📋 Tabelas no banco de dados:', tables);


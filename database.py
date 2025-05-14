import sys
import os
import MySQLdb

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import mysql, app

def criar_tabelas():
    with app.app_context():
        conn = mysql.connection
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nome VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            senha VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nome VARCHAR(100) NOT NULL UNIQUE,
            imagem VARCHAR(255) NOT NULL
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS receitas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            usuario_id INT NOT NULL,
            descricao VARCHAR(255) NOT NULL,
            valor DECIMAL(10, 2) NOT NULL,
            data DATE NOT NULL,
            categoria VARCHAR(100) NOT NULL,  # Adicionado
            categoria_id INT,                # Opcional, se quiser manter a FK
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY (categoria_id) REFERENCES categorias(id)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS despesas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            usuario_id INT NOT NULL,
            descricao VARCHAR(255) NOT NULL,
            valor DECIMAL(10, 2) NOT NULL,
            data DATE NOT NULL,
            prazo DATE NOT NULL,
            categoria VARCHAR(100) NOT NULL,  # Adicionado
            categoria_id INT,                 # Opcional
            status ENUM('pendente', 'pago', 'atrasado') DEFAULT 'pendente',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY (categoria_id) REFERENCES categorias(id)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cofre (
            id INT AUTO_INCREMENT PRIMARY KEY,
            usuario_id INT NOT NULL,
            nome VARCHAR(100) NOT NULL,
            limite DECIMAL(10, 2) NOT NULL,
            valor_juntado DECIMAL(10, 2) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            UNIQUE KEY (usuario_id, nome)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS totais_mensais (
            id INT AUTO_INCREMENT PRIMARY KEY,
            usuario_id INT NOT NULL,
            mes INT NOT NULL,
            ano INT NOT NULL,
            total_gasto DECIMAL(10,2) DEFAULT 0,
            total_limite DECIMAL(10,2) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            UNIQUE KEY (usuario_id, mes, ano)
        );
        """)

        conn.commit()
        cursor.close()
        print("Tabelas básicas criadas com sucesso!")

def inserir_categorias():
    with app.app_context():
        conn = mysql.connection
        cursor = conn.cursor()

        categorias = [
            ('Bares', 'bares.png'),
            ('Casa', 'casa.png'),
            ('Comida', 'comida.png'),
            ('Doações', 'doacoes.png'),
            ('Eletrônicos', 'eletronicos.png'),
            ('Estudo', 'estudo.png'),
            ('Impostos', 'impostos.png'),
            ('Maquiagens', 'maquiagens.png'),
            ('Outros', 'outros.png'),
            ('Papelaria', 'papelaria.png'),
            ('Perfumaria', 'perfumaria.png'),
            ('Pets', 'pets.png'),
            ('Roupas', 'roupas.png'),
            ('Salário', 'salario.png'),
            ('Sapatos', 'sapatos.png'),
            ('Saúde', 'saude.png'),
            ('Supermercado', 'supermercado.png'),
            ('Trabalho', 'trabalho.png'),
            ('Transporte', 'transporte.png'),
            ('Viagens', 'viagens.png'),
        ]

        cursor.executemany("INSERT INTO categorias (nome, imagem) VALUES (%s, %s)", categorias)
        conn.commit()
        cursor.close()
        print("Categorias inseridas com sucesso!")

if __name__ == "__main__":
    criar_tabelas()
    inserir_categorias()
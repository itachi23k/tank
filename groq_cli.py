#!/usr/bin/env python3
"""
⚡ Groq CLI - Assistente de Código no Terminal
Modelo: Llama 3.1 8B Instant (GRÁTIS e RÁPIDO)

Uso:
    python groq_cli.py "sua pergunta"
    python groq_cli.py                    # Modo interativo
    python groq_cli.py --file routes.py   # Analisar arquivo
"""

import sys
import os
from groq import Groq

API_KEY = os.environ.get("GROQ_API_KEY", "")

class GroqCLI:
    def __init__(self):
        if not API_KEY:
            print("⚠️ AVISO: A variável de ambiente GROQ_API_KEY não está configurada.")
            print("   Defina-a com: export GROQ_API_KEY='sua_chave_aqui'")
        self.client = Groq(api_key=API_KEY) if API_KEY else None
        self.model = "llama-3.1-8b-instant"
        
        self.system_prompt = (
            "Voce e um assistente especialista em:\n"
            "- Python, Flask, SQLAlchemy, JavaScript\n"
            "- Banco de dados SQLite e PostgreSQL\n"
            "- Desenvolvimento web com Tailwind CSS\n"
            "- Git e deploy\n\n"
            "Responda de forma CLARA e DIRETA.\n"
            "Sempre mostre codigo quando relevante.\n"
            "Use exemplos praticos do mundo real."
        )
        
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]
    
    def ask(self, pergunta):
        """Faz uma pergunta e retorna a resposta"""
        self.messages.append({"role": "user", "content": pergunta})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                temperature=0.7,
                max_tokens=2048
            )
            
            resposta = response.choices[0].message.content
            self.messages.append({"role": "assistant", "content": resposta})
            
            return resposta
            
        except Exception as e:
            return f"Erro: {str(e)}"
    
    def analyze_file(self, filepath):
        """Analisa um arquivo de codigo"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            prompt = (
                "Analise este arquivo de codigo:\n\n"
                "```python\n"
                f"{content[:5000]}\n"
                "```\n\n"
                "Forneca:\n"
                "1. Resumo do que o codigo faz\n"
                "2. Possiveis problemas/bugs\n"
                "3. Sugestoes de melhoria\n"
                "4. Otimizacoes possiveis"
            )
            return self.ask(prompt)
            
        except FileNotFoundError:
            return f"Arquivo nao encontrado: {filepath}"
        except Exception as e:
            return f"Erro ao ler arquivo: {str(e)}"
    
    def interactive_mode(self):
        """Modo interativo (chat continuo)"""
        print("=" * 50)
        print("  ⚡ Groq CLI - Llama 3.1 8B Instant")
        print("  Comandos:")
        print("  /file ARQ  - Analisar arquivo")
        print("  /clear     - Limpar historico")
        print("  /help      - Ajuda")
        print("  /exit      - Sair")
        print("=" * 50)
        print()
        
        while True:
            try:
                user_input = input(">>> ").strip()
                
                if not user_input:
                    continue
                
                if user_input == "/exit":
                    print("\nAte mais!")
                    break
                
                elif user_input == "/clear":
                    self.messages = [{"role": "system", "content": self.system_prompt}]
                    print("Historico limpo\n")
                    continue
                
                elif user_input == "/help":
                    print("""
Comandos disponiveis:
  /file ARQ  - Analisar arquivo
  /clear     - Limpar historico
  /exit      - Sair
  Qualquer texto - Pergunta direta
""")
                    continue
                
                elif user_input.startswith("/file "):
                    filepath = user_input.split("/file ")[1].strip()
                    print(f"\nAnalisando: {filepath}\n")
                    resposta = self.analyze_file(filepath)
                    print(f"{resposta}\n")
                    print("-" * 50 + "\n")
                    continue
                
                # Pergunta normal
                print("Pensando...")
                resposta = self.ask(user_input)
                print(f"\n{resposta}\n")
                print("-" * 50 + "\n")
                
            except KeyboardInterrupt:
                print("\n\nAte mais!")
                break
            except Exception as e:
                print(f"\nErro: {e}\n")

def main():
    cli = GroqCLI()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--file" and len(sys.argv) > 2:
            print(f"Analisando: {sys.argv[2]}\n")
            resposta = cli.analyze_file(sys.argv[2])
            print(resposta)
        else:
            pergunta = " ".join(sys.argv[1:])
            print(cli.ask(pergunta))
    else:
        cli.interactive_mode()

if __name__ == "__main__":
    main()
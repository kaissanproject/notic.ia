import os
import requests
import base64
import time
import json

# --- CONFIGURAÇÃO ---
HUGGINGFACE_API_TOKEN = os.getenv('HUGGINGFACE_API_TOKEN')

# Modelos ATUALIZADOS e mais estáveis da plataforma Hugging Face
# Usaremos um modelo mais robusto e de propósito geral para texto.
TEXT_MODEL_API_URL = "https://api-inference.huggingface.co/models/google/gemma-1.1-7b-it" 
IMAGE_MODEL_API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"

ARTICLES_TO_GENERATE = 3
OUTPUT_FILENAME = "index.html"
TEMPLATE_FILENAME = "template.html"

HEADERS = {"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"}

if not HUGGINGFACE_API_TOKEN:
    print("ERRO CRÍTICO: O token da API Hugging Face não foi encontrado.")
    exit(1)

# --- FUNÇÕES DE GERAÇÃO ---

def query_api(api_url, payload, retries=3, initial_wait=20):
    """Função genérica para fazer requisições à API da Hugging Face com retentativas."""
    for i in range(retries):
        response = requests.post(api_url, headers=HEADERS, json=payload)
        
        if response.status_code == 200:
            return response
        
        elif response.status_code == 503: # Modelo carregando
            wait_time = response.json().get('estimated_time', initial_wait)
            print(f"Modelo está carregando. Esperando {wait_time:.2f} segundos...")
            time.sleep(wait_time)
        else:
            print(f"API retornou erro {response.status_code}: {response.text}")
            print(f"Tentativa {i + 1} de {retries}. Esperando {initial_wait}s...")
            time.sleep(initial_wait)
            
    print(f"API falhou após {retries} tentativas no endpoint: {api_url}")
    return None

def get_trending_topics():
    """Busca tópicos em alta no Brasil usando o modelo de texto."""
    print("Buscando tópicos em alta...")
    prompt = f"Liste {ARTICLES_TO_GENERATE + 2} tópicos de notícias muito populares no Brasil hoje. Retorne apenas os nomes dos tópicos, separados por ponto e vírgula. Exemplo: Reforma tributária;Novidades do futebol brasileiro;Lançamentos de tecnologia no Brasil"
    
    response = query_api(TEXT_MODEL_API_URL, {"inputs": prompt, "parameters": {"max_new_tokens": 100}})
    
    if response:
        try:
            text_result = response.json()[0]['generated_text']
            clean_text = text_result.replace(prompt, "").strip()
            topics = [topic.strip() for topic in clean_text.split(';') if topic.strip()]
            print(f"Tópicos encontrados: {topics}")
            return topics if topics else None
        except (KeyError, IndexError, json.JSONDecodeError, Exception) as e:
            print(f"Erro ao processar a resposta dos tópicos: {e}")
            return None
    return None

def generate_article_content(topic):
    """Gera o conteúdo de um artigo para um tópico específico."""
    print(f"Gerando artigo sobre: {topic}...")
    prompt = f"""
    Sua tarefa é escrever um artigo completo sobre o tópico: "{topic}".
    Você é um jornalista digital brasileiro, com um tom descontraído e envolvente.
    O artigo deve conter um título de notícia chamativo, o conteúdo com 3 parágrafos, e uma meta description para SEO com no máximo 150 caracteres.
    Retorne o resultado estritamente no seguinte formato, sem nenhum texto adicional antes ou depois:
    TITULO: [Seu título aqui]
    CONTEUDO: [Seu conteúdo aqui, com parágrafos separados por uma nova linha]
    METADESCRIPTION: [Sua meta description aqui]
    """
    
    response = query_api(TEXT_MODEL_API_URL, {"inputs": prompt, "parameters": {"max_new_tokens": 500}})
    
    if response:
        try:
            text_result = response.json()[0]['generated_text'].replace(prompt, "").strip()
            content_dict = {}
            lines = text_result.strip().split('\n')
            current_key = None
            for line in lines:
                if line.startswith("TITULO:"):
                    current_key = "title"
                    content_dict[current_key] = line.replace("TITULO:", "").strip()
                elif line.startswith("CONTEUDO:"):
                    current_key = "content"
                    content_dict[current_key] = line.replace("CONTEUDO:", "").strip()
                elif line.startswith("METADESCRIPTION:"):
                    current_key = "meta"
                    content_dict[current_key] = line.replace("METADESCRIPTION:", "").strip()
                elif current_key == "content" and line.strip():
                    content_dict[current_key] += "\n" + line.strip()

            if 'title' in content_dict and 'content' in content_dict:
                print(f"Artigo '{content_dict.get('title')}' gerado.")
                return content_dict
            else:
                print(f"Resposta da IA mal formatada: {text_result}")
                return None

        except (KeyError, IndexError, json.JSONDecodeError, Exception) as e:
            print(f"Erro ao processar o conteúdo do artigo: {e}")
            return None
    return None

def generate_article_image(prompt):
    """Gera uma imagem a partir de um prompt."""
    print(f"Gerando imagem para: '{prompt}'...")
    full_prompt = f"photorealistic, news portal style, high quality photo for an article about: '{prompt}'"
    
    response = query_api(IMAGE_MODEL_API_URL, {"inputs": full_prompt})
    
    if response:
        image_bytes = response.content
        b64_image = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:image/png;base64,{b64_image}"
    else:
        print("Falha ao gerar imagem, usando imagem padrão.")
        return "https://placehold.co/600x400/3498db/ffffff?text=Imagem+Indisponível"

# --- LÓGICA PRINCIPAL ---

def main():
    topics = get_trending_topics()
    if not topics:
        print("Não foi possível obter os tópicos. Encerrando.")
        return

    articles_data = []
    for topic in topics[:ARTICLES_TO_GENERATE]:
        content = generate_article_content(topic)
        if content:
            time.sleep(5) 
            image_url = generate_article_image(content['title'])
            content['image_url'] = image_url
            articles_data.append(content)

    if not articles_data:
        print("Nenhum artigo foi gerado. Encerrando.")
        return

    print("Montando o arquivo HTML final...")
    try:
        with open(TEMPLATE_FILENAME, 'r', encoding='utf-8') as f:
            template = f.read()
    except FileNotFoundError:
        print(f"ERRO: O arquivo de template '{TEMPLATE_FILENAME}' não foi encontrado.")
        return
        
    articles_html = ""
    for article in articles_data:
        content_html = ''.join([f'<p class="mb-4">{p.strip()}</p>' for p in article.get("content", "").split('\n') if p.strip()])
        articles_html += f"""
        <article class="article-card bg-white rounded-lg shadow-lg overflow-hidden flex flex-col">
            <img src="{article.get('image_url')}" alt="{article.get('title', 'Artigo sem título')}" class="w-full h-48 object-cover">
            <div class="p-6 flex flex-col flex-grow">
                <h2 class="text-2xl font-bold mb-2">{article.get('title')}</h2>
                <div class="text-gray-700 leading-relaxed flex-grow">{content_html}</div>
                <meta name="description" content="{article.get('meta', '')}">
            </div>
        </article>
        """

    final_html = template.replace("<!-- PLACEHOLDER_ARTICLES -->", articles_html)
    
    with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
        f.write(final_html)
    
    print("-" * 50)
    print(f"🎉 Sucesso! O site foi gerado no arquivo: {OUTPUT_FILENAME}")
    print("O robô agora fará o commit e publicará a atualização.")
    print("-" * 50)

if __name__ == "__main__":
    main()


# PROMETHEUS MESH V2.0 - Memory Service (RAG)

O **Memory Service** fornece persistência de longo prazo e capacidades de busca semântica para todo o sistema.

## Responsabilidades

- **Armazenamento Vetorial**: Guarda embeddings de textos, logs e decisões.
- **Busca Semântica**: Permite encontrar "coisas parecidas" (ex: "O que eu decidi da última vez que o Chrome travou?").
- **Aprendizado Incremental**: Reforça decisões corretas e penaliza incorretas baseando-se no feedback do usuário.

## Especificações Técnicas

### Stack

- **Database**: Qdrant (Vector DB).
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (Leve e rápido).
- **API**: FastAPI.

### Coleções (Collections)

1. **`decisions`**: Registro de ações tomadas pelo sistema (Timestamp, Contexto, Ação, Aprovado/Rejeitado).
2. **`conversations`**: Histórico de chat usuário-IA (para manter coerência em longas conversas).
3. **`knowledge`**: Snippets de informação técnica ou fatos aprendidos.
4. **`security`**: Assinaturas de ameaças e logs de incidentes.

### Fluxo de Aprendizado (Decision Loop)

1. **Evento**: Sentinel detecta alto uso de CPU por `app.exe`.
2. **Consulta**: Sentinel pergunta à Memory: "O que fazer com `app.exe`?".
3. **Retrieval**: Memory busca vetores similares em `decisions`.
4. **Inferência**:
    - Se encontrou decisões anteriores "Kill" aprovadas pelo usuário -> Recomenda "Kill".
    - Se nunca viu -> Recomenda "Perguntar ao Usuário".
5. **Feedback**: Ação tomada pelo usuário é salva como nova memória, reforçando o peso para o futuro.

### Endpoints Principais

- `POST /memory/store`: Salva novo vetor.
- `POST /memory/search`: Busca por similaridade.
- `POST /decisions/should-approve`: Endpoint específico para lógica de decisão autônoma.

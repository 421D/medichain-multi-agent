# MediChain 后端 API 文档

## 启动方式

```bash
git clone <repo地址>
cd medichain
cp .env.example .env    # 填入API key
docker compose up -d    # 启动后端+数据库+Redis
```

启动后：
- API地址：http://localhost:8000
- Swagger文档（可以直接测试所有接口）：http://localhost:8000/docs

---

## 接口列表

### 1. Session（诊断会话管理）

**创建会话**
```
POST /api/v1/sessions/
```
请求体：
```json
{
  "title": "患者主诉头痛",
  "llm_model": "kimi"
}
```
返回：
```json
{
  "id": "uuid-xxx",
  "title": "患者主诉头痛",
  "status": "active",
  "llm_model": "kimi"
}
```

**获取所有会话**
```
GET /api/v1/sessions/
```

**获取单个会话**
```
GET /api/v1/sessions/{session_id}
```

**更新会话**
```
PUT /api/v1/sessions/{session_id}
```

**删除会话**
```
DELETE /api/v1/sessions/{session_id}
```

---

### 2. Chat（聊天/问诊）

**发送消息（会自动调用AI返回回复）**
```
POST /api/v1/chat/
```
请求体：
```json
{
  "session_id": "上面创建会话返回的id",
  "content": "I have a headache and fever for 3 days"
}
```
返回：
```json
{
  "user_message": {
    "id": "xxx",
    "session_id": "xxx",
    "role": "user",
    "content": "I have a headache and fever for 3 days"
  },
  "ai_response": {
    "id": "xxx",
    "session_id": "xxx",
    "role": "assistant",
    "content": "Based on your symptoms..."
  },
  "citations": [
    {
      "source": "pubmed",
      "title": "论文标题",
      "url": "https://pubmed.ncbi.nlm.nih.gov/xxxxx/"
    }
  ],
  "reasoning_steps": [
    {"agent": "knowledge_agent", "action": "pubmed_search"},
    {"agent": "reasoning_agent", "action": "generate_response"},
    {"agent": "safety_agent", "action": "verify"},
    {"agent": "coordinator", "action": "compile_response"}
  ]
}
```

**获取聊天历史**
```
GET /api/v1/chat/{session_id}
```
返回该会话的所有消息列表。

---

### 3. MCP工具（外部医学API查询）

**查看可用工具**
```
GET /api/v1/tools/
```
返回：
```json
{
  "tools": ["pubmed", "drugbank", "icd11"]
}
```

**查询外部医学工具**
```
POST /api/v1/tools/query
```
请求体：
```json
{
  "tool_name": "pubmed",
  "query": "headache fever diagnosis"
}
```
返回真实的PubMed论文列表（标题、作者、链接）。

---

### 4. Agent配置

**查看Agent系统状态**
```
GET /api/v1/agents/status
```
返回可用模型列表和工具列表。

**切换LLM模型**
```
POST /api/v1/agents/config
```
请求体：
```json
{
  "session_id": "xxx",
  "model": "kimi"
}
```
支持的模型：`gpt-4`、`gpt-4o`、`gemini`、`kimi`

**获取Agent推理日志（给Dashboard用）**
```
GET /api/v1/agents/logs/{session_id}
```

---

### 5. WebSocket（实时通信）

```
WS ws://localhost:8000/ws/chat/{session_id}
```

前端发送：
```json
{
  "type": "user_message",
  "content": "患者的输入内容"
}
```

后端会实时推送：
```json
{"type": "agent_event", "agent": "knowledge_agent", "event": "thinking", "content": "Searching medical literature..."}
{"type": "agent_event", "agent": "reasoning_agent", "event": "thinking", "content": "Analyzing symptoms..."}
{"type": "agent_event", "agent": "safety_agent", "event": "thinking", "content": "Verifying safety..."}
{"type": "patient_response", "content": "最终回复", "citations": []}
```

目前WebSocket是echo模式，Sprint 2会接入真正的Agent推理流程。

---

## 数据库表结构

| 表名 | 用途 |
|------|------|
| users | 用户信息 |
| sessions | 诊断会话（标题、状态、使用的模型） |
| messages | 聊天记录（用户消息和AI回复，包含citations） |
| agent_logs | Agent推理日志（给Dashboard可视化用） |

---

## 前端对接要点

1. **所有接口都支持CORS**，前端 `localhost:3000` / `5173` / `8080` 都能直接调
2. **先创建session，再发chat**，chat接口需要session_id
3. **citations在chat返回里**，每条AI回复都可能带citations数组，前端可以渲染成引用链接
4. **reasoning_steps也在chat返回里**，可以用来展示Agent推理过程
5. **WebSocket地址是** `ws://localhost:8000/ws/chat/{session_id}`，用来做实时推送
6. 打开 http://localhost:8000/docs 可以直接测试所有接口

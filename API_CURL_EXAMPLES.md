# API cURL Examples

This document contains cURL examples for all API endpoints in the Browser Flow Backend.

**Base URL**: `http://localhost:8000` (adjust as needed)

**Required Header**: All endpoints require `X-User-Guest-ID` header with a valid UUID.

---

## Health Check

### GET /health
Check if the API is running.

```bash
curl -X GET "http://localhost:8000/health"
```

**Response:**
```json
{
  "status": "healthy"
}
```

---

## Tasks API

### 1. Create/Initiate a Task

#### POST /api/tasks
Create a new task. Supports two main task types: `add_to_context` and `create_action_from_context`.

**Example 1: Add to Context (with URLs)**
```bash
curl -X POST "http://localhost:8000/api/tasks" \
  -H "Content-Type: application/json" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{
    "task_type": "add_to_context",
    "urls": [
      "https://example.com/article1",
      "https://example.com/article2"
    ],
    "workflow_tools": ["notion", "trello"]
  }'
```

**Example 2: Add to Context (with selected text)**
```bash
curl -X POST "http://localhost:8000/api/tasks" \
  -H "Content-Type: application/json" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{
    "task_type": "add_to_context",
    "selected_text": "This is some important context that I want to save...",
    "user_context": "Additional notes about this context"
  }'
```

**Example 3: Create Action from Context**
```bash
curl -X POST "http://localhost:8000/api/tasks" \
  -H "Content-Type: application/json" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{
    "task_type": "create_action_from_context",
    "urls": ["https://example.com/research-paper"],
    "workflow_tools": ["notion", "trello", "miro"]
  }'
```

**Example 4: Other Task Types**
```bash
# Note Taking
curl -X POST "http://localhost:8000/api/tasks" \
  -H "Content-Type: application/json" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{
    "task_type": "note_taking",
    "selected_text": "Meeting notes from today...",
    "workflow_tools": ["notion"]
  }'

# Add to Knowledge Base
curl -X POST "http://localhost:8000/api/tasks" \
  -H "Content-Type: application/json" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{
    "task_type": "add_to_knowledge_base",
    "urls": ["https://example.com/documentation"]
  }'

# Create TODO
curl -X POST "http://localhost:8000/api/tasks" \
  -H "Content-Type: application/json" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{
    "task_type": "create_todo",
    "selected_text": "Tasks to complete this week",
    "workflow_tools": ["trello"]
  }'
```

**Response:**
```json
{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "task_type": "create_action_from_context",
  "context_ids": ["789e4567-e89b-12d3-a456-426614174001"],
  "context_result": {...},
  "actions_result": {...},
  "trello_metadata": "Trello task created successfully"
}
```

---

### 2. Get All Tasks

#### GET /api/tasks
Retrieve all tasks for the authenticated user with pagination and filtering.

**Basic Request (First Page)**
```bash
curl -X GET "http://localhost:8000/api/tasks?page=1&page_size=50" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000"
```

**With Pagination**
```bash
curl -X GET "http://localhost:8000/api/tasks?page=2&page_size=20" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000"
```

**Filter by Task Type**
```bash
curl -X GET "http://localhost:8000/api/tasks?task_type=create_action_from_context" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000"
```

**Search in Tasks**
```bash
curl -X GET "http://localhost:8000/api/tasks?search=research" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000"
```

**Combined Filters**
```bash
curl -X GET "http://localhost:8000/api/tasks?page=1&page_size=25&task_type=note_taking&search=meeting" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000"
```

**Response:**
```json
{
  "tasks": [
    {
      "task_id": "123e4567-e89b-12d3-a456-426614174000",
      "task_type": "create_action_from_context",
      "input": {
        "workflow_tools": ["notion", "trello"],
        "user_context": "..."
      },
      "output": {
        "response_tokens": "...",
        "response_file": "",
        "response_image": ""
      },
      "user_contexts": ["789e4567-e89b-12d3-a456-426614174001"],
      "timestamp": "2024-01-15T10:30:00Z",
      "context_count": 1
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 50
}
```

---

### 3. Get Task Details

#### GET /api/tasks/{task_id}
Get detailed information about a specific task.

**Basic Request**
```bash
curl -X GET "http://localhost:8000/api/tasks/123e4567-e89b-12d3-a456-426614174000" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000"
```

**With Context Details**
```bash
curl -X GET "http://localhost:8000/api/tasks/123e4567-e89b-12d3-a456-426614174000?include_contexts=true" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000"
```

**Response (without contexts):**
```json
{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "task_type": "create_action_from_context",
  "input": {
    "workflow_tools": ["notion", "trello"],
    "user_context": "..."
  },
  "output": {
    "response_tokens": "...",
    "response_file": "",
    "response_image": ""
  },
  "user_contexts": ["789e4567-e89b-12d3-a456-426614174001"],
  "timestamp": "2024-01-15T10:30:00Z",
  "context_count": 1
}
```

**Response (with contexts):**
```json
{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "task_type": "create_action_from_context",
  "input": {...},
  "output": {...},
  "user_contexts": ["789e4567-e89b-12d3-a456-426614174001"],
  "timestamp": "2024-01-15T10:30:00Z",
  "context_count": 1,
  "contexts": [
    {
      "context_id": "789e4567-e89b-12d3-a456-426614174001",
      "url": "https://example.com/article",
      "tags": ["research", "AI"],
      "content_preview": "This is a preview of the content...",
      "context_type": "text",
      "timestamp": "2024-01-15T10:25:00Z"
    }
  ]
}
```

---

## Contexts API

### 1. Get All Contexts (List View)

#### GET /api/contexts
Retrieve all contexts for the authenticated user in list format with pagination and filtering.

**Basic Request**
```bash
curl -X GET "http://localhost:8000/api/contexts?page=1&page_size=50" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000"
```

**Filter by Context Type**
```bash
# Text contexts only
curl -X GET "http://localhost:8000/api/contexts?context_type=text" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000"

# Image contexts only
curl -X GET "http://localhost:8000/api/contexts?context_type=image" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000"

# Video contexts only
curl -X GET "http://localhost:8000/api/contexts?context_type=video" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000"
```

**Filter by Tags**
```bash
curl -X GET "http://localhost:8000/api/contexts?tags=research,AI,machine-learning" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000"
```

**Search in Content**
```bash
curl -X GET "http://localhost:8000/api/contexts?search=neural networks" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000"
```

**Combined Filters**
```bash
curl -X GET "http://localhost:8000/api/contexts?page=1&page_size=25&context_type=text&tags=research&search=deep learning" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000"
```

**Response:**
```json
{
  "contexts": [
    {
      "context_id": "789e4567-e89b-12d3-a456-426614174001",
      "url": "https://example.com/article",
      "context_tags": ["research", "AI", "machine-learning"],
      "raw_content": "This is the content of the context (truncated to 500 chars)...",
      "user_defined_context": "Summary of the article",
      "context_type": "text",
      "timestamp": "2024-01-15T10:25:00Z",
      "parent_topic": null,
      "has_children": true
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 50
}
```

---

### 2. Get Contexts Graph (Hierarchical View)

#### GET /api/contexts/graph
Retrieve all contexts in hierarchical/graph format suitable for visualization.

**Basic Request**
```bash
curl -X GET "http://localhost:8000/api/contexts/graph" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000"
```

**With Max Depth Limit**
```bash
curl -X GET "http://localhost:8000/api/contexts/graph?max_depth=5" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000"
```

**Response:**
```json
{
  "nodes": [
    {
      "id": "789e4567-e89b-12d3-a456-426614174001",
      "label": "https://example.com/article",
      "url": "https://example.com/article",
      "tags": ["research", "AI"],
      "content_preview": "This is a preview of the content...",
      "context_type": "text",
      "timestamp": "2024-01-15T10:25:00Z",
      "parent_id": null,
      "children": [
        {
          "id": "789e4567-e89b-12d3-a456-426614174002",
          "label": "Related article",
          "url": "https://example.com/related",
          "tags": ["research"],
          "content_preview": "...",
          "context_type": "text",
          "timestamp": "2024-01-15T10:26:00Z",
          "parent_id": "789e4567-e89b-12d3-a456-426614174001",
          "children": []
        }
      ]
    }
  ],
  "edges": [
    {
      "source": "789e4567-e89b-12d3-a456-426614174001",
      "target": "789e4567-e89b-12d3-a456-426614174002"
    }
  ],
  "root_nodes": ["789e4567-e89b-12d3-a456-426614174001"]
}
```

---

### 3. Get Context Details

#### GET /api/contexts/{context_id}
Get detailed information about a specific context including parent and children.

**Basic Request**
```bash
curl -X GET "http://localhost:8000/api/contexts/789e4567-e89b-12d3-a456-426614174001" \
  -H "X-User-Guest-ID: 550e8400-e29b-41d4-a716-446655440000"
```

**Response:**
```json
{
  "context_id": "789e4567-e89b-12d3-a456-426614174001",
  "url": "https://example.com/article",
  "context_tags": ["research", "AI", "machine-learning"],
  "raw_content": "Full content of the context...",
  "user_defined_context": "Summary of the article",
  "context_type": "text",
  "timestamp": "2024-01-15T10:25:00Z",
  "parent_topic": null,
  "parent": null,
  "children": [
    {
      "context_id": "789e4567-e89b-12d3-a456-426614174002",
      "url": "https://example.com/related",
      "tags": ["research"],
      "content_preview": "Preview of child context..."
    }
  ]
}
```

---

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request
```json
{
  "detail": "X-User-Guest-ID header is required"
}
```

### 403 Forbidden
```json
{
  "detail": "Access denied"
}
```

### 404 Not Found
```json
{
  "detail": "Task not found"
}
```

---

## Task Types Reference

Available task types:
- `add_to_context`
- `create_action_from_context`
- `note_taking`
- `add_to_knowledge_base`
- `question_answer`
- `create_todo`
- `create_diagrams`
- `add_to_google_sheets`
- `create_location_map`
- `compare_shopping_prices`

## Context Types Reference

Available context types:
- `text`
- `image`
- `video`

---

## Notes

1. **User Guest ID**: Replace `550e8400-e29b-41d4-a716-446655440000` with your actual user guest ID UUID in all requests.

2. **Base URL**: Adjust `http://localhost:8000` to match your deployment URL if different.

3. **Pagination**: Default page size is 50, maximum is 100 for tasks and contexts.

4. **Search**: Search is case-insensitive and searches across multiple fields.

5. **Graph View**: The graph endpoint returns hierarchical data suitable for visualization libraries like D3.js, vis.js, or Cytoscape.js.

6. **Context Details**: Use `include_contexts=true` when fetching task details to get associated context information.

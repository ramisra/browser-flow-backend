# Notion API curl reference

Use placeholders: `NOTION_API_KEY` (e.g. from `.env`: `export NOTION_API_KEY=$NOTION_TOKEN`), `PARENT_PAGE_ID`, `PAGE_ID`, `BLOCK_ID`. Share a page with your integration for `PARENT_PAGE_ID` and `PAGE_ID`.

- **Base URL**: `https://api.notion.com/v1`
- **Headers**: `Authorization: Bearer $NOTION_API_KEY`, `Content-Type: application/json`, `Notion-Version: 2025-09-03`

---

## 1. Create a page

**POST** `https://api.notion.com/v1/pages`

```bash
curl -X POST https://api.notion.com/v1/pages \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Notion-Version: 2025-09-03" \
  --data '{
    "parent": { "type": "page_id", "page_id": "PARENT_PAGE_ID" },
    "properties": {
      "title": {
        "type": "title",
        "title": [{ "type": "text", "text": { "content": "A note from API" } }]
      }
    }
  }'
```

Create page with initial content (paragraph + to_do):

```bash
curl -X POST https://api.notion.com/v1/pages \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Notion-Version: 2025-09-03" \
  --data '{
    "parent": { "type": "page_id", "page_id": "PARENT_PAGE_ID" },
    "properties": {
      "title": {
        "type": "title",
        "title": [{ "type": "text", "text": { "content": "Page with content" } }]
      }
    },
    "children": [
      {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
          "rich_text": [{ "type": "text", "text": { "content": "First paragraph from API." } }]
        }
      },
      {
        "object": "block",
        "type": "to_do",
        "to_do": {
          "rich_text": [{ "type": "text", "text": { "content": "Todo item one" } }],
          "checked": false
        }
      }
    ]
  }'
```

Save the returned `id` from the response as `PAGE_ID` for the next operations.

---

## 2. Append block children

**PATCH** `https://api.notion.com/v1/blocks/{block_id}/children`

Use the **page ID** as `block_id`. Optional: `position` — `{"type": "end"}`, `{"type": "start"}`, or `{"type": "after_block", "after_block": {"id": "BLOCK_ID"}}`.

**Append paragraph:**

```bash
curl -X PATCH "https://api.notion.com/v1/blocks/PAGE_ID/children" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Notion-Version: 2025-09-03" \
  --data '{
    "children": [
      {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
          "rich_text": [{ "type": "text", "text": { "content": "Appended paragraph." } }]
        }
      }
    ]
  }'
```

**Append to_do:**

```bash
curl -X PATCH "https://api.notion.com/v1/blocks/PAGE_ID/children" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Notion-Version: 2025-09-03" \
  --data '{
    "children": [
      {
        "object": "block",
        "type": "to_do",
        "to_do": {
          "rich_text": [{ "type": "text", "text": { "content": "Finish docs" } }],
          "checked": false
        }
      }
    ]
  }'
```

**Append heading_1:**

```bash
curl -X PATCH "https://api.notion.com/v1/blocks/PAGE_ID/children" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Notion-Version: 2025-09-03" \
  --data '{
    "children": [{
      "object": "block",
      "type": "heading_1",
      "heading_1": {
        "rich_text": [{ "type": "text", "text": { "content": "Section title" } }]
      }
    }]
  }'
```

**Bulleted list, numbered list, quote, divider, code:** use `bulleted_list_item`, `numbered_list_item`, `quote`, `divider` (with `"divider": {}`), or `code` (with `"code": { "rich_text": [...], "language": "javascript" }`) in `children`.

---

## 3. Search (by title)

**POST** `https://api.notion.com/v1/search`

```bash
curl -X POST https://api.notion.com/v1/search \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Notion-Version: 2025-09-03" \
  --data '{
    "query": "meeting",
    "filter": { "property": "object", "value": "page" },
    "sort": { "direction": "descending", "timestamp": "last_edited_time" }
  }'
```

---

## 4. Retrieve block children

**GET** `https://api.notion.com/v1/blocks/{block_id}/children?page_size=100`

```bash
curl "https://api.notion.com/v1/blocks/PAGE_ID/children?page_size=100" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03"
```

---

## 5. Retrieve a page

**GET** `https://api.notion.com/v1/pages/{page_id}`

```bash
curl "https://api.notion.com/v1/pages/PAGE_ID" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03"
```

---

## 6. Update page properties

**PATCH** `https://api.notion.com/v1/pages/{page_id}`

```bash
curl -X PATCH "https://api.notion.com/v1/pages/PAGE_ID" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Notion-Version: 2025-09-03" \
  --data '{
    "properties": {
      "title": {
        "type": "title",
        "title": [{ "type": "text", "text": { "content": "Updated page title" } }]
      }
    }
  }'
```
